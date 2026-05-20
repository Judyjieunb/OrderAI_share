"""
발주 추천 계산 (api.py::_apply_budget_and_save에서 추출)

매핑 확정 시 호출되는 핵심 계산 로직:
1. (apply_budget=True) 카테고리 예산 ceiling 적용 — Full 전용. Lite는 False.
2. 컬러 배분 (color_allocation 호출 + ST 30% 캐시)
3. 카테고리별 budget summary 생성

저장(JSON/Excel)은 라우터에서 처리.
ref_at30 조회는 callback 주입 (호출자가 제공 — 데이터 로드 의존 분리).
"""

from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from server.services.color_allocation import get_color_breakdown


# CAT_NM_ENG/CAT_NM(한국어) → CLASS2 (복종) 매핑 — api.py와 동일 (변경 시 동기 필요)
_CAT_TO_CLASS2 = {
    # English
    "T-shirts": "Inner", "Sweater": "Inner", "Sweatshirts/Hoodie": "Inner",
    "Shirt": "Inner", "Sleeveless": "Inner", "Sweatsuit": "Inner",
    "Denim": "Bottom", "Pants": "Bottom", "Shorts": "Bottom",
    "Skirt": "Bottom", "Leggings": "Bottom",
    "Outerwear": "Outer", "Padded Jacket": "Outer", "Fleece": "Outer",
    # Korean (CAT_NM)
    "티셔츠": "Inner", "스웨터": "Inner", "맨투맨/후드": "Inner",
    "셔츠": "Inner", "트레이닝셋업": "Inner",
    "데님": "Bottom", "팬츠": "Bottom", "스커트": "Bottom", "레깅스": "Bottom",
    "아우터": "Outer", "패딩": "Outer", "후리스": "Outer",
    "모자": "Outer", "기타용품": "Outer",
}


def _ceil_10(x):
    """10단위 반올림 (api.py::_ceil_10 동일)"""
    if x is None or x != x or x <= 0:
        return 0
    return int(round(x / 10) * 10)


def apply_budget_and_color(
    results: List[Dict],
    color_df: pd.DataFrame,
    go_colors_map: Dict[str, List[str]],
    ref_at30_lookup: Optional[Callable[[str], Dict]] = None,
    apply_budget: bool = True,
    budget_config: Optional[Dict] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    매핑 확정 결과(results)에 예산 ceiling + 컬러 배분 적용.

    Args:
        results: 매핑 확정 결과 리스트 (각 dict에 "추천발주량", "ref_part_cd", "class2" 등)
        color_df: 컬러별 ref 실적 DataFrame (PART_CD, COLOR_CD, AI제안 발주량 등)
        go_colors_map: {new_part_cd: [color_cd, ...]} GO list 컬러
        ref_at30_lookup: ref_part_cd → {color_cd: {qty, ratio}} 함수 (호출자 주입)
        apply_budget: 예산 ceiling 적용 여부 (Lite=False, Full=True)
        budget_config: budget_config.json 내용 (apply_budget=True 시 필수)

    Returns:
        (processed_results, category_budgets)
        - processed_results: 컬러 배분/예산 스케일링 반영된 results
        - category_budgets: 카테고리별 합계 + 예산 (UI 표시용, budget 미적용 시 빈 리스트)
    """

    # Phase 4: 예산 천장 스케일링 (apply_budget=True일 때만)
    if apply_budget and budget_config:
        ceiling_map = {}
        for cat in budget_config.get("category_budgets", []):
            ceiling_map[cat["class2"]] = cat["budget_qty"]

        if ceiling_map:
            cat_totals: Dict[str, int] = {}
            for rec in results:
                cls2 = rec.get("class2") or _CAT_TO_CLASS2.get(rec.get("new_class2", ""), "")
                qty = rec.get("추천발주량", 0)
                if cls2 and qty > 0:
                    cat_totals[cls2] = cat_totals.get(cls2, 0) + qty

            scale_ratios: Dict[str, float] = {}
            for cls2, total_qty in cat_totals.items():
                ceiling = ceiling_map.get(cls2)
                if ceiling is not None and total_qty > ceiling and total_qty > 0:
                    scale_ratios[cls2] = ceiling / total_qty

            for rec in results:
                cls2 = rec.get("class2") or _CAT_TO_CLASS2.get(rec.get("new_class2", ""), "")
                ratio = scale_ratios.get(cls2)
                if ratio is not None and rec.get("추천발주량", 0) > 0:
                    rec["original_recommendation"] = rec["추천발주량"]
                    rec["추천발주량"] = _ceil_10(rec["추천발주량"] * ratio)
                    rec["budget_scaled"] = True

    # Phase 5: 컬러별 배분 + @30% 비중
    # 옵션 B: at30_data를 ref_part_cd별 한 번만 계산하여 가중치(get_color_breakdown)와 표시(ref_sale_at30/ratio_at30) 양쪽에 공유
    MOQ_WARNING_THRESHOLD = 300
    _at30_cache: Dict[str, dict] = {}

    def _get_at30(ref_cd: str) -> dict:
        if ref_cd not in _at30_cache:
            data = ref_at30_lookup(ref_cd) if ref_at30_lookup else None
            _at30_cache[ref_cd] = data or {}
        return _at30_cache[ref_cd]

    for rec in results:
        ref_cd = rec.get("ref_part_cd")
        qty = rec.get("추천발주량", 0)
        go_colors = go_colors_map.get(rec["new_part_cd"], [])
        cls2 = rec.get("class2") or rec.get("new_class2", "")
        at30_data = _get_at30(ref_cd) if ref_cd else {}
        if ref_cd and qty > 0:
            rec["colors"] = get_color_breakdown(
                ref_cd, color_df, qty, go_colors=go_colors, class2=cls2,
                ref_at30_data=at30_data,
            )
        elif rec.get("manual_input") and qty > 0:
            if go_colors:
                rec["colors"] = get_color_breakdown(
                    "", color_df, qty, go_colors=go_colors, class2=cls2,
                    ref_at30_data=None,
                )
            else:
                rec["colors"] = [{"color_cd": "-", "ratio": 100.0, "qty": qty}]
        else:
            rec["colors"] = []
        if any(c.get("qty", 0) > 0 and c["qty"] < MOQ_WARNING_THRESHOLD for c in rec["colors"] if not c.get("ref_only")):
            rec["moq_warning"] = True
        # @30% 시점 컬러비중 표시 필드 삽입 (이미 캐시된 데이터 사용)
        if ref_cd and at30_data:
            for c in rec["colors"]:
                ref_color = c.get("ref_color_cd") or c.get("color_cd")
                at30 = at30_data.get(ref_color, {})
                c["ref_sale_at30"] = at30.get("qty", 0) if isinstance(at30, dict) else 0
                c["ref_ratio_at30"] = at30.get("ratio", 0) if isinstance(at30, dict) else 0

    # Phase 6: 카테고리별 summary 생성
    cat_summary: Dict[str, Dict[str, int]] = {}
    for rec in results:
        cls2 = rec.get("class2") or _CAT_TO_CLASS2.get(rec.get("new_class2", ""), "")
        qty = rec.get("추천발주량", 0)
        orig = rec.get("original_recommendation", qty)
        if cls2:
            if cls2 not in cat_summary:
                cat_summary[cls2] = {"추천합계": 0, "스케일링전합계": 0}
            cat_summary[cls2]["추천합계"] += qty
            cat_summary[cls2]["스케일링전합계"] += orig

    category_budgets = []
    if budget_config:
        for cat in budget_config.get("category_budgets", []):
            cls2 = cat["class2"]
            cs = cat_summary.get(cls2, {"추천합계": 0, "스케일링전합계": 0})
            category_budgets.append({
                "class2": cls2,
                "budget_qty": cat["budget_qty"],
                "recommended_qty": cs["추천합계"],
                "pre_scale_qty": cs["스케일링전합계"],
            })

    return results, category_budgets
