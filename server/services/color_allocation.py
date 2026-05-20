"""
컬러배분 — Anchor 기반 Level 3 + 동적 role 분류 (5/12 옵션 B 통일)

매칭 (Level 1/2a/2b/3):
  Level 1 (정확매칭): alpha 일치 (CRS == CRS) → ref 비중 그대로
  Level 2a (유사매칭): 같은 'final' 그룹 (BLACK/WHITE/GRAY... 14개) + prefix 우선
  Level 2b (prefix 안전망): 매핑에 없는 신규 코드도 prefix만으로 매칭
  Level 3 (Anchor 기반):
    anchor 탐색 (BLACK → WHITE → ref max 비중)
    anchor 발견 시: anchor의 ref 비중 × class2_anchor_ratios[gc_final]
    anchor/표본 없음: class2_sales_share_final 회사 평균 fallback

가중치 (옵션 B, 4/27):
  - 1순위: ref 컬러의 ST 30% 도달 시점 누계판매 비중 (결품 노이즈 제거)
  - 2순위 fallback: ref 컬러의 마감 AI발주량 비중

Role 분류 (5/12, 동적):
  분배 결과 비중 기반:
    basic   : 비중 max (1개, 무조건)
    sub     : 비중 2위 이하, ratio ≥ 15%
    accent  : sub 이후, ratio ≥ 5%
    그 외   : role 미부여 (None)

공용 API:
  - get_color_breakdown: 메인 함수
  - load_color_mapping:  color_mapping.json 로드 헬퍼
  - strip_color_prefix:  컬러코드 숫자 접두사 제거 (50BKS → BKS)
"""

import json
import os
import re
import sys
from typing import Optional

import pandas as pd

# ───────────── 모듈 상수 ─────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PUBLIC_DIR = os.path.join(_BASE_DIR, "public")

_COL_PART_CD = "PART_CD"
_COL_AI_ORDER = "AI제안 발주량"

# Role 임계값
_ROLE_SUB_MIN_RATIO = 15.0
_ROLE_ACCENT_MIN_RATIO = 5.0

# 미등록 컬러코드 로깅 캐시 (반복 출력 방지, 프로세스 단위)
_UNKNOWN_COLOR_CACHE: set = set()


# ───────────── 내부 유틸 ─────────────

def _ceil_10(x):
    """10단위 반올림"""
    if x is None or x != x or x <= 0:
        return 0
    return int(round(x / 10) * 10)


def _log_unknown_color(code: str, alpha: str):
    """매핑 파일에 없는 컬러코드 발견 시 1회 stderr 경고 출력."""
    if alpha not in _UNKNOWN_COLOR_CACHE:
        _UNKNOWN_COLOR_CACHE.add(alpha)
        print(
            f"[color-allocation] Unknown color code: {code} (alpha={alpha}) — "
            f"fallback to Level 2b/3",
            file=sys.stderr,
        )


# ───────────── 공용 API ─────────────

def load_color_mapping() -> dict:
    """public/color_mapping.json 로드"""
    path = os.path.join(_PUBLIC_DIR, "color_mapping.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "color_to_final": {},
        "color_to_name_kr": {},
        "class2_sales_share_final": {},
        "class2_anchor_ratios": {},
    }


def strip_color_prefix(color_cd: str) -> str:
    """컬러코드에서 숫자 접두사 제거 (50BKS → BKS)"""
    return re.sub(r"^[0-9]+", "", str(color_cd).strip())


def get_color_breakdown(
    ref_part_cd: str,
    color_df: pd.DataFrame,
    total_qty: int,
    go_colors: list = None,
    class2: str = "",
    ref_at30_data: dict = None,
) -> list:
    """
    Anchor 기반 3단계 계층 컬러배분.

    Args:
      ref_at30_data: {color_cd: {qty, ratio}} — _calc_color_ratio_at_30pct 결과.
                     None이면 마감 AI발주량 비중만 사용.
    """
    color_mapping = load_color_mapping()
    code_to_final = color_mapping.get("color_to_final", {})
    name_kr_map = color_mapping.get("color_to_name_kr", {})
    anchor_ratios_all = color_mapping.get("class2_anchor_ratios", {})
    sales_share_final = color_mapping.get("class2_sales_share_final", {})

    anchor_ratios_class2 = anchor_ratios_all.get(class2, {})
    sales_share_class2 = sales_share_final.get(class2, sales_share_final.get("_all", {}))

    def _classify(color_cd: str) -> str:
        """알파 코드 → final 그룹"""
        alpha = strip_color_prefix(color_cd)
        return code_to_final.get(alpha, "Unknown")

    # ref 컬러 정보 수집
    rows = color_df[color_df[_COL_PART_CD] == ref_part_cd]
    ref_color_orders: dict = {}    # color_cd -> ai_order
    ref_color_meta: dict = {}      # color_cd -> meta
    if not rows.empty and _COL_AI_ORDER in rows.columns:
        for _, r in rows.iterrows():
            ccd = str(r.get("COLOR_CD", ""))
            if not ccd:
                continue
            ai_order = float(r.get(_COL_AI_ORDER, 0))
            final = _classify(ccd)
            alpha = strip_color_prefix(ccd)
            ref_color_orders[ccd] = ai_order
            ref_color_meta[ccd] = {
                "color_cd": ccd,
                "final": final,
                "alpha": alpha,
                "prefix2": alpha[:2] if len(alpha) >= 2 else alpha,
                "총발주": int(r.get("총발주", 0)),
                "총판매": int(r.get("총판매", 0)),
                "판매율": float(r.get("최종판매율", 0)),
                "AI발주량": int(ai_order),
            }

    total_ref_ai = sum(v for v in ref_color_orders.values() if v > 0)

    def _ref_pct(ref_cd: str) -> float:
        """ref 컬러의 비중 percentage (옵션 B: 30% 시점 우선, AI발주량 fallback)"""
        if ref_at30_data:
            at30 = ref_at30_data.get(ref_cd)
            if isinstance(at30, dict):
                r = at30.get("ratio", 0)
                if r > 0:
                    return float(r)
        if total_ref_ai <= 0:
            return 0.0
        return ref_color_orders.get(ref_cd, 0) / total_ref_ai * 100

    def _anchor_weight(gc_final: str) -> Optional[float]:
        """Level 3 anchor 기반 가중치.
        BLACK → WHITE → max 순으로 anchor 탐색. anchor 발견 + (class2, gc_final)
        조합이 anchor_ratios에 있으면 가중치 산출. 없으면 None.
        """
        # BLACK/WHITE 순 탐색
        for anchor_final in ("BLACK", "WHITE"):
            anchor_cd = next(
                (cd for cd, m in ref_color_meta.items()
                 if m["final"] == anchor_final and ref_color_orders.get(cd, 0) > 0),
                None,
            )
            if anchor_cd:
                ratio = anchor_ratios_class2.get(gc_final)
                if ratio is not None:
                    return _ref_pct(anchor_cd) * ratio
        # max fallback
        if ref_color_orders:
            max_cd = max(ref_color_orders, key=ref_color_orders.get)
            if ref_color_orders[max_cd] > 0:
                ratio = anchor_ratios_class2.get(gc_final)
                if ratio is not None:
                    return _ref_pct(max_cd) * ratio
        return None

    # GO list 컬러 없으면: ref 컬러 비율 그대로
    if not go_colors or len(go_colors) == 0:
        colors = _fallback_ref_ratio(
            ref_color_orders, ref_color_meta, total_qty, total_ref_ai, name_kr_map
        )
        _classify_role(colors)
        return colors

    # === 3단계 매칭 ===
    weighted = []
    matched_ref_codes: set = set()

    for gc in go_colors:
        gc_final = _classify(gc)
        gc_alpha = strip_color_prefix(gc)
        gc_prefix2 = gc_alpha[:2] if len(gc_alpha) >= 2 else gc_alpha
        if gc_final == "Unknown":
            _log_unknown_color(gc, gc_alpha)

        match_level = "3"
        matched_ref_cd = None
        weight = 0.0

        # Level 1: alpha 정확매칭
        exact_ref = next(
            (cd for cd, m in ref_color_meta.items()
             if m["alpha"] == gc_alpha and ref_color_orders.get(cd, 0) > 0),
            None,
        )
        if exact_ref:
            match_level = "1"
            matched_ref_cd = exact_ref
            weight = _ref_pct(exact_ref)
        else:
            # Level 2a: 같은 'final' 그룹 + prefix 우선
            same_final = []
            if gc_final != "Unknown":
                same_final = [
                    cd for cd, m in ref_color_meta.items()
                    if m["final"] == gc_final
                    and m["final"] != "Unknown"
                    and ref_color_orders.get(cd, 0) > 0
                ]
            if same_final:
                prefix_match = [
                    cd for cd in same_final
                    if ref_color_meta[cd]["prefix2"] == gc_prefix2
                ]
                if prefix_match:
                    matched_ref_cd = max(prefix_match, key=lambda cd: ref_color_orders[cd])
                else:
                    matched_ref_cd = max(same_final, key=lambda cd: ref_color_orders[cd])
                match_level = "2a"
                weight = _ref_pct(matched_ref_cd)
            else:
                # Level 2b: prefix 안전망
                prefix_only = [
                    cd for cd, m in ref_color_meta.items()
                    if m["prefix2"] == gc_prefix2
                    and ref_color_orders.get(cd, 0) > 0
                ]
                if prefix_only:
                    matched_ref_cd = max(prefix_only, key=lambda cd: ref_color_orders[cd])
                    match_level = "2b"
                    weight = _ref_pct(matched_ref_cd)
                else:
                    # Level 3: Anchor 기반 → 회사 평균 fallback
                    match_level = "3"
                    anchor_w = _anchor_weight(gc_final)
                    if anchor_w is not None:
                        weight = anchor_w
                    else:
                        # 안전망: anchor/표본 없음 → 회사 평균 (final 기준)
                        weight = sales_share_class2.get(gc_final, 0.1)

        if matched_ref_cd:
            matched_ref_codes.add(matched_ref_cd)

        weighted.append({
            "color_cd": gc,
            "final": gc_final,
            "weight": max(weight, 0.1),
            "match_level": match_level,
            "matched_ref_cd": matched_ref_cd,
        })

    # === 정규화 + 80% 캡 + 10단위 보정 ===
    total_weight = sum(w["weight"] for w in weighted) or 1
    n_colors = len(weighted)

    raw_ratios = [w["weight"] / total_weight for w in weighted]

    MAX_RATIO = 0.80
    if n_colors > 1:
        capped = [min(r, MAX_RATIO) for r in raw_ratios]
        overflow = sum(raw_ratios) - sum(capped)
        if overflow > 0:
            uncapped_idx = [i for i, r in enumerate(raw_ratios) if r < MAX_RATIO]
            uncapped_sum = sum(capped[i] for i in uncapped_idx) or 1
            for i in uncapped_idx:
                capped[i] += overflow * (capped[i] / uncapped_sum)
        raw_ratios = capped

    raw_qtys = [int(round(total_qty * r / 10) * 10) for r in raw_ratios]
    diff = total_qty - sum(raw_qtys)
    if diff != 0 and n_colors > 0:
        max_qty = max(raw_qtys)
        candidates = [i for i in range(n_colors) if raw_qtys[i] == max_qty]
        level_rank = {"1": 0, "2a": 1, "2b": 2, "3": 3}
        if diff < 0:
            target = max(candidates, key=lambda i: level_rank.get(str(weighted[i]["match_level"]), 3))
        else:
            target = min(candidates, key=lambda i: level_rank.get(str(weighted[i]["match_level"]), 3))
        raw_qtys[target] += diff

    # === 결과 행 생성 ===
    colors = []
    for i, w in enumerate(weighted):
        qty = max(raw_qtys[i], 0)
        ratio = round((qty / total_qty * 100) if total_qty > 0 else 0, 1)
        ref_meta = ref_color_meta.get(w["matched_ref_cd"]) if w["matched_ref_cd"] else None
        entry = {
            "color_cd": w["color_cd"],
            "color_range": w["final"],          # final 통일
            "color_final": w["final"],          # 유지 (기존 소비자 호환)
            "color_name_kr": name_kr_map.get(w["final"], ""),
            "match_level": w["match_level"],
            "ratio": ratio,
            "qty": qty,
        }
        if ref_meta:
            entry["ref_color_cd"] = ref_meta["color_cd"]
            entry["ref_총발주"] = ref_meta["총발주"]
            entry["ref_총판매"] = ref_meta["총판매"]
            entry["ref_판매율"] = ref_meta["판매율"]
        colors.append(entry)

    # ref-only 행 추가 (GO에 매칭되지 않은 ref 컬러)
    for ccd, meta in ref_color_meta.items():
        if ccd in matched_ref_codes:
            continue
        if meta["총발주"] <= 0:
            continue
        colors.append({
            "color_cd": None,
            "color_range": meta["final"],
            "color_final": meta["final"],
            "color_name_kr": name_kr_map.get(meta["final"], ""),
            "match_level": None,
            "ratio": 0,
            "qty": 0,
            "ref_color_cd": meta["color_cd"],
            "ref_총발주": meta["총발주"],
            "ref_총판매": meta["총판매"],
            "ref_판매율": meta["판매율"],
            "ref_only": True,
        })

    _classify_role(colors)
    return colors


def _classify_role(colors: list) -> None:
    """분배 결과 비중 기반 동적 role 부여 (in-place).
    basic: ratio max (1개, 무조건)
    sub:   ratio 2위 이하, >= 15%
    accent: sub 이후, >= 5%
    그 외: role 미부여 (None)
    """
    # ref_only는 분류 제외 (qty=0)
    sortable = [c for c in colors if not c.get("ref_only") and c.get("qty", 0) > 0]
    if not sortable:
        return
    sortable.sort(key=lambda c: -c.get("ratio", 0))
    for i, c in enumerate(sortable):
        r = c.get("ratio", 0)
        if i == 0:
            c["role"] = "basic"
        elif r >= _ROLE_SUB_MIN_RATIO:
            c["role"] = "sub"
        elif r >= _ROLE_ACCENT_MIN_RATIO:
            c["role"] = "accent"
        else:
            c["role"] = None


def _fallback_ref_ratio(
    ref_color_orders: dict,
    ref_color_meta: dict,
    total_qty: int,
    total_ref_ai: float,
    name_kr_map: dict,
) -> list:
    """GO list 컬러 없을 때: ref 컬러 비율 그대로 사용 (manual_input 등)"""
    if not ref_color_orders or total_ref_ai <= 0:
        return []
    colors = []
    distributed = 0
    items = [(cd, q) for cd, q in ref_color_orders.items() if q > 0]
    for i, (ccd, ai_qty) in enumerate(items):
        ratio = ai_qty / total_ref_ai
        if i == len(items) - 1:
            qty = total_qty - distributed
        else:
            qty = _ceil_10(total_qty * ratio)
            distributed += qty
        meta = ref_color_meta.get(ccd, {})
        final = meta.get("final", "Unknown")
        colors.append({
            "color_cd": ccd,
            "color_range": final,
            "color_final": final,
            "color_name_kr": name_kr_map.get(final, ""),
            "match_level": "1",
            "ratio": round(ratio * 100, 1),
            "qty": max(qty, 0),
            "ref_color_cd": ccd,
            "ref_총발주": meta.get("총발주", 0),
            "ref_총판매": meta.get("총판매", 0),
            "ref_판매율": meta.get("판매율", 0),
        })
    return colors
