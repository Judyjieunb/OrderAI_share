"""
Lite 전용 라우터 (담당자, 검토용 초안).

Step 5 본격 구현 — 13개 엔드포인트 (8 GET + 5 POST).
설계 결정 (Phase 1, 모델 A):
  1. GET: DuckDB(공용 baseline) + 본인 사물함 우선 fallback
     - dashboard / season-closing은 baseline only
     - style-mapping은 baseline + 본인 confirmed_mapping 합쳐 반환
     - order-recommendation / size-assortment / orders/excel은 본인 우선
  2. POST cascade: api.py 헬퍼 함수 재사용 (지연 import로 순환 회피),
     `services.order_calc.apply_budget_and_color(apply_budget=False)`.
  3. 사이즈 배분 cascade:
     - 매핑 확정 시 → baseline size_assortment를 본인 사물함에 1차 복사
     - 수량 확정 시 → ORDER_QTY 비례 스케일링 (단순 모델, Phase 1 한정)
     - confirmed-size 명시 저장 시 → 본인 사물함 덮어쓰기
  4. Excel 워터마크: "검토용 초안 (담당자 최종 확정 전, {email}, {timestamp})"
     첫 행에 워터마크 row 삽입 + 시트명 prefix.
  5. 권한: 모든 엔드포인트 `Depends(require_brand_access)` 부착 (brand 미지정 → 422).

규칙: routers/full.py를 직접 import하지 않는다 (양쪽 격리). 공통 로직은 server/services/ 경유.
"""

import io
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from server.db import (
    get_db, query_seasons, query_meta,
    query_season_summary, query_dashboard, query_style_mapping,
    query_order_recommendation, query_size_assortment,
)
from server.permissions import list_user_brands_only, require_brand_access
from server.services import user_storage
from server.services.order_calc import apply_budget_and_color
from server.services.color_helpers_duckdb import (
    CAT_TO_CLASS2, COL_PART_CD, COL_ITEM_NM, COL_PRDT_NM, COL_PRICE,
    COL_TOTAL_ORDER, COL_TOTAL_SALE, COL_SELL_RATE, COL_AI_DIAG, COL_AI_ORDER,
    ceil_10, sex_from_style_cd,
    load_style_summary_duckdb, lookup_ref_summary_duckdb,
    load_color_detail_duckdb, calc_color_ratio_at_30pct_duckdb,
    load_go_colors_map_from_user_data,
)


# ───────────── Pydantic 모델 (api.py 모델과 동일 — 순환 import 회피용 복제) ─────────────

class LiteConfirmedMappingItem(BaseModel):
    new_part_cd: str
    new_item_nm: str
    new_prdt_nm: str = ""
    new_class2: str
    class2: Optional[str] = None
    selected_ref_part_cd: Optional[str] = None
    selected_ref_score: Optional[float] = None
    manual_order_qty: Optional[int] = None
    size_range: Optional[str] = None


class LiteConfirmedMappingRequest(BaseModel):
    season: str = ""
    mappings: List[LiteConfirmedMappingItem]


class LiteConfirmedOrderItem(BaseModel):
    class2: str = ""
    new_item_nm: str = ""
    new_part_cd: str
    color_cd: str
    confirmed_qty: int
    size_range: str = ""


class LiteConfirmedOrdersRequest(BaseModel):
    season: str = ""
    orders: List[LiteConfirmedOrderItem]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lite")


# ───────────── 마스터 ─────────────

@router.get("/brands")
async def get_brands(allowed: list[str] = Depends(list_user_brands_only)):
    """본인 권한 브랜드 목록. X-User-Email 기반."""
    return {"brands": allowed}


@router.get("/seasons")
async def get_seasons(
    brand: str,
    _email: str = Depends(require_brand_access),
    con=Depends(get_db),
):
    """해당 브랜드의 적재된 시즌 목록 (권한 체크 후)."""
    return {"brand": brand.upper(), "seasons": query_seasons(con, brand)}


# ───────────── 공용 조회 (baseline only) ─────────────

@router.get("/dashboard")
async def get_dashboard(
    brand: str,
    season: str,
    _email: str = Depends(require_brand_access),
    con=Depends(get_db),
):
    """시계열 대시보드 (운영팀 baseline). 담당자 변경 영역 없음."""
    return query_dashboard(con, brand, season)


@router.get("/season-closing")
async def get_season_closing(
    brand: str,
    season: str,
    _email: str = Depends(require_brand_access),
    con=Depends(get_db),
):
    """시즌마감 분석 (운영팀 baseline). 담당자 변경 영역 없음."""
    data = query_season_summary(con, brand, season)
    if data is None:
        raise HTTPException(status_code=404, detail="해당 브랜드/시즌 데이터 없음")
    return data


# ───────────── 본인 사물함 우선 + baseline fallback ─────────────


def _apply_go_list_filter(base: dict, go_data: dict) -> dict:
    """baseline style_mapping을 본인 GO list로 필터링 + 메타 보강 + unmatched manual entry.

    Full /api/go-list cascade(server/api.py:1076-1116)의 Lite 등가 —
    similarity_mapping/step4_integration 외부 의존 없이 DuckDB baseline 안에서만 처리.
    """
    go_styles = {str(s).strip() for s in (go_data.get("styles") or []) if str(s).strip()}
    if not go_styles:
        return base

    go_info: dict[str, dict] = {}
    for row in (go_data.get("detail") or []):
        sc = str(row.get("STYLE_CD", "")).strip()
        if not sc:
            continue
        entry = go_info.setdefault(sc, {
            "class2": "", "item": "", "colors": [], "size_range": "",
        })
        if not entry["class2"]:
            entry["class2"] = str(row.get("CLASS2", "")).strip()
        if not entry["item"]:
            entry["item"] = str(row.get("ITEM", "")).strip()
        color = str(row.get("COLOR_CD", "")).strip()
        if color and color not in entry["colors"]:
            entry["colors"].append(color)
        if not entry["size_range"]:
            sr = str(row.get("SIZE_RANGE", "")).strip()
            if sr:
                entry["size_range"] = sr

    filtered: list[dict] = []
    matched_set: set[str] = set()
    for s in base.get("styles", []):
        npc = str(s.get("new_part_cd", "")).strip()
        if npc not in go_styles:
            continue
        info = go_info.get(npc)
        if info:
            if info["class2"]:     s["go_class2"]     = info["class2"]
            if info["item"]:       s["go_item"]       = info["item"]
            if info["colors"]:     s["go_colors"]     = info["colors"]
            if info["size_range"]: s["go_size_range"] = info["size_range"]
        filtered.append(s)
        matched_set.add(npc)

    unmatched_count = 0
    for sc in sorted(go_styles - matched_set):
        info = go_info.get(sc, {})
        entry = {
            "new_part_cd": sc,
            "new_item_nm": info.get("item", ""),
            "new_class2": info.get("class2", ""),
            "class2": info.get("class2", ""),
            "go_class2": info.get("class2", ""),
            "go_item": info.get("item", ""),
            "go_colors": info.get("colors", []),
            "references": [],
        }
        if info.get("size_range"):
            entry["go_size_range"] = info["size_range"]
        filtered.append(entry)
        unmatched_count += 1

    base["styles"] = filtered
    meta = base.setdefault("metadata", {})
    meta["total_styles"] = len(filtered)
    meta["go_list"] = True
    meta["go_total_styles"] = len(go_styles)
    meta["go_matched_styles"] = len(matched_set)
    meta["go_unmatched_styles"] = unmatched_count
    return base


@router.get("/style-mapping")
async def get_style_mapping(
    brand: str,
    season: str,
    email: str = Depends(require_brand_access),
    con=Depends(get_db),
):
    """매핑 baseline + 본인 go_list 필터 + 본인 confirmed_mapping 병합.

    Cascade:
      1. baseline (DuckDB): 시즌 전체 후보 매핑 + Top 3 references 사전계산
      2. 본인 go_list.json 있으면 → STYLE_CD 필터 + go 메타 보강 + unmatched manual entry
      3. 본인 confirmed_mapping.json 있으면 → user_confirmed 부착
    """
    base = query_style_mapping(con, brand, season)

    go_data = await user_storage.read_user_only(email, brand, season, "go_list.json")
    if go_data and go_data.get("styles"):
        base = _apply_go_list_filter(base, go_data)

    user_data = await user_storage.read_user_only(email, brand, season, "confirmed_mapping.json")
    if user_data:
        base["user_confirmed"] = user_data
    return base


@router.get("/ref-style")
async def lookup_ref_style(
    brand: str,
    part_cd: str,
    email: str = Depends(require_brand_access),
    con=Depends(get_db),
):
    """과거 3시즌 안의 ref 스타일 정보 lookup (수기 직접 입력용).

    Step 3 StyleMapping에서 운영자가 PART_CD 직접 입력 시 호출.
    DuckDB style_timeseries chart_data JSON 파싱하여 컬러별 analysis 집계 → 스타일 단위 반환.

    DuckDB style_timeseries에는 baseSeason(예: 25F) 기준으로 적재된 PART_CD가 들어있고,
    weekly_raw가 3시즌(당해/전년/재작년)을 fetch하므로 분석 결과의 PART_CD도 3시즌 모두 포함.
    → 별도 시즌 필터 없이 DuckDB에서 PART_CD 일치 검색하면 자연스럽게 3시즌 lookup.
    """
    pc = (part_cd or "").strip().upper()
    if not pc:
        raise HTTPException(status_code=400, detail="part_cd가 필요합니다.")

    rows = con.execute(
        """
        SELECT season_code, color_cd, chart_data
        FROM style_timeseries
        WHERE brand_code = ? AND UPPER(part_cd) = ? AND color_cd != 'ALL'
        """,
        [brand.lower(), pc],
    ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"{pc}: 과거 3시즌 데이터에서 찾을 수 없습니다.",
        )

    total_order, total_stock, total_sale, ai_order = 0, 0, 0, 0
    prdt_nm, item_nm, season_found = "", "", rows[0][0]

    for _season, _color_cd, chart_data_json in rows:
        cd = json.loads(chart_data_json) if isinstance(chart_data_json, str) else chart_data_json
        analysis = (cd.get("analysis") or {}) if isinstance(cd, dict) else {}
        info = (cd.get("itemInfo") or {}) if isinstance(cd, dict) else {}

        def _num(v):
            try:
                return float(v or 0)
            except (TypeError, ValueError):
                return 0.0

        total_order += int(_num(analysis.get("총발주")))
        total_stock += int(_num(analysis.get("총입고")))
        total_sale += int(_num(analysis.get("총판매")))
        ai_order += int(_num(analysis.get("AI제안 발주량")))
        if not prdt_nm:
            prdt_nm = (info.get("prdt_nm") or "").strip()
        if not item_nm:
            item_nm = (info.get("item_nm") or info.get("name") or "").strip()

    sell_rate = round(total_sale / total_stock * 100, 1) if total_stock > 0 else 0.0

    return {
        "found": True,
        "part_cd": pc,
        "season": season_found,
        "prdt_nm": prdt_nm,
        "item_nm": item_nm,
        "총발주": total_order,
        "총입고": total_stock,
        "총판매": total_sale,
        "판매율": sell_rate,
        "AI발주량": ai_order,
    }


@router.get("/order-recommendation")
async def get_order_recommendation(
    brand: str,
    season: str,
    email: str = Depends(require_brand_access),
    con=Depends(get_db),
):
    """본인 사물함 only — Step 3 미확정이면 204 No Content.

    baseline의 자동 매핑(Top1) 발주 추천은 의미 없는 데이터라 노출 안 함.
    본인이 Step 3에서 매핑 확정해야 cascade로 발주 추천 생성됨.
    """
    user_data = await user_storage.read_user_only(
        email, brand, season, "order_recommendation_data.json"
    )
    if user_data is not None:
        return user_data
    return Response(status_code=204)


@router.get("/size-assortment")
async def get_size_assortment(
    brand: str,
    season: str,
    email: str = Depends(require_brand_access),
    con=Depends(get_db),
):
    """본인 사물함 우선 → baseline fallback.

    SizeAssortment 화면은 기본적으로 baseline의 과거 + 당해 실판매 데이터를 표시.
    본인이 시뮬레이션 결과를 확정 저장하면 그것이 우선.
    (order-recommendation과 달리 baseline 자체가 의미 있는 실데이터)
    """
    user_data = await user_storage.read_user_only(
        email, brand, season, "size_assortment_data.json"
    )
    if user_data:
        return user_data
    return query_size_assortment(con, brand, season)


# 본인 사물함 단순 read 화이트리스트 (confirmed_order_data 등 baseline에 없는 사용자 전용 데이터)
_USER_FILE_WHITELIST = {
    "confirmed_order_data.json",
    "confirmed_mapping.json",
    "go_list.json",
}


@router.get("/user-file")
async def get_user_file(
    brand: str,
    season: str,
    name: str = Query(..., description="파일명 (화이트리스트만 허용)"),
    email: str = Depends(require_brand_access),
):
    """본인 사물함 화이트리스트 파일 read. 없으면 204 No Content."""
    if name not in _USER_FILE_WHITELIST:
        raise HTTPException(
            status_code=400,
            detail=f"허용되지 않은 파일명: {name}. 허용: {sorted(_USER_FILE_WHITELIST)}",
        )
    data = await user_storage.read_user_only(email, brand, season.lower(), name)
    if data is None:
        return Response(status_code=204)
    return data


# ───────────── Excel 다운로드 ─────────────

_DRAFT_WATERMARK_TEMPLATE = "검토용 초안 (담당자 최종 확정 전, {email}, {timestamp})"


def _build_order_excel(
    order_data: dict,
    email: str,
    season: str,
) -> bytes:
    """발주 Excel 생성 + 워터마크.

    구조:
      1행: 워터마크 (병합 셀)
      2행: 빈 행
      3행: 컬럼 헤더
      4행~: 데이터
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    watermark = _DRAFT_WATERMARK_TEMPLATE.format(email=email, timestamp=timestamp)

    excel_rows = []
    for rec in order_data.get("recommendations", []):
        for c in rec.get("colors", []):
            excel_rows.append({
                "NEW_PART_CD": rec.get("new_part_cd", ""),
                "NEW_ITEM_NM": rec.get("new_item_nm", ""),
                "NEW_CLASS2": rec.get("new_class2", ""),
                "COLOR_CD": c.get("color_cd", ""),
                "비중(%)": c.get("ratio", 0),
                "AI추천수량": c.get("qty", 0),
                "스타일합계": rec.get("추천발주량", 0),
            })
    if not excel_rows:
        excel_rows = [{"안내": "추천 데이터가 없습니다 (Step 3에서 매핑 확정 후 생성)"}]

    df = pd.DataFrame(excel_rows)
    sheet_name = f"{season} 검토용 초안"[:31]  # Excel 시트명 31자 제한

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # startrow=2: 1행 워터마크 + 2행 빈 행 + 3행부터 컬럼 헤더
        df.to_excel(writer, sheet_name=sheet_name, startrow=2, index=False)
        ws = writer.sheets[sheet_name]
        # 워터마크 (A1)
        ws.cell(row=1, column=1, value=watermark)
        # A1을 마지막 컬럼까지 병합
        if len(df.columns) > 1:
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
    buf.seek(0)
    return buf.getvalue()


@router.get("/orders/excel")
async def download_orders_excel(
    brand: str,
    season: str,
    email: str = Depends(require_brand_access),
    con=Depends(get_db),
):
    """발주 Excel 다운로드 ("검토용 초안" 워터마크).

    조건: 본인 사물함에 confirmed_mapping/order_recommendation/size_assortment 중
          1건 이상 존재 (없으면 409 Conflict).
    """
    files_to_check = [
        "confirmed_mapping.json",
        "order_recommendation_data.json",
        "size_assortment_data.json",
    ]
    has_user_data = False
    for fn in files_to_check:
        if await user_storage.read_user_only(email, brand, season, fn) is not None:
            has_user_data = True
            break

    if not has_user_data:
        raise HTTPException(
            status_code=409,
            detail=(
                "발주서 다운로드를 위해 Step 3~5 중 한 곳 이상에서 검토 후 "
                "확정 버튼을 눌러주세요."
            ),
        )

    # 본인 발주 추천 우선 → 없으면 baseline
    order_data = await user_storage.read_user_only(
        email, brand, season, "order_recommendation_data.json"
    )
    if order_data is None:
        order_data = query_order_recommendation(con, brand, season)

    excel_bytes = _build_order_excel(order_data, email, season)
    filename = f"{season}_OrderRecommendation_DRAFT_{email.split('@')[0]}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ───────────── 본인 사물함 쓰기 (POST) ─────────────

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_mapping_results(req: LiteConfirmedMappingRequest, season: str,
                           con, brand: str) -> list[dict]:
    """매핑 확정 → 발주 추천 results 리스트 구성 (예산/컬러배분 적용 전).

    Phase 1 Lite: DuckDB만 사용 (Excel/Snowflake 의존성 0). server.api 의존을 끊어
    Lite 컨테이너에서 config_loader 없이 동작.
    """
    style_summary = load_style_summary_duckdb(con, brand)

    results: list[dict] = []
    for m in req.mappings:
        cls2 = m.class2 or CAT_TO_CLASS2.get(m.new_class2, "")

        # 매칭 불가 스타일의 수동 입력
        if m.manual_order_qty is not None:
            rec = {
                "new_part_cd": m.new_part_cd,
                "new_item_nm": m.new_item_nm,
                "new_prdt_nm": m.new_prdt_nm,
                "new_class2": m.new_class2,
                "class2": cls2,
                "추천발주량": ceil_10(m.manual_order_qty),
                "budget_scaled": False,
                "manual_input": True,
            }
            if m.size_range:
                rec["size_range"] = m.size_range
            sex = sex_from_style_cd(m.new_part_cd)
            if sex:
                rec["sex"] = sex
            results.append(rec)
            continue

        # 유사스타일 기반 발주량
        ref_info: dict = {}
        ai_order = 0
        if m.selected_ref_part_cd:
            ref_match = style_summary[style_summary[COL_PART_CD] == m.selected_ref_part_cd] \
                if not style_summary.empty else style_summary
            if not ref_match.empty:
                row = ref_match.iloc[0]
                ai_order = int(row.get(COL_AI_ORDER, 0))
                ref_info = {
                    "ref_part_cd": m.selected_ref_part_cd,
                    "ref_item_nm": str(row.get(COL_ITEM_NM, "")),
                    "ref_prdt_nm": str(row.get(COL_PRDT_NM, "")),
                    "ref_score": m.selected_ref_score,
                    "ref_총판매": int(row.get(COL_TOTAL_SALE, 0)),
                    "ref_총발주": int(row.get(COL_TOTAL_ORDER, 0)),
                    "ref_판매율": float(row.get(COL_SELL_RATE, 0)),
                    "ref_진단": str(row.get(COL_AI_DIAG, "-")),
                    "ref_AI발주량": ai_order,
                    "판매가": int(row.get(COL_PRICE, 0)),
                }
            else:
                d_info = lookup_ref_summary_duckdb(con, brand, m.selected_ref_part_cd)
                ref_info = {
                    "ref_part_cd": m.selected_ref_part_cd,
                    "ref_item_nm": d_info.get("ref_item_nm", m.new_item_nm),
                    "ref_prdt_nm": d_info.get("ref_prdt_nm", ""),
                    "ref_score": m.selected_ref_score,
                    "ref_총판매": d_info.get("ref_총판매", 0),
                    "ref_총발주": d_info.get("ref_총발주", 0),
                    "ref_판매율": d_info.get("ref_판매율", 0),
                    "ref_진단": "-",
                    "ref_AI발주량": 0,
                    "판매가": d_info.get("판매가", 0),
                }

        rec = {
            "new_part_cd": m.new_part_cd,
            "new_item_nm": m.new_item_nm,
            "new_prdt_nm": m.new_prdt_nm,
            "new_class2": m.new_class2,
            "class2": cls2,
            "추천발주량": ceil_10(ai_order),
            "budget_scaled": False,
            **ref_info,
        }
        if m.size_range:
            rec["size_range"] = m.size_range
        sex = sex_from_style_cd(m.new_part_cd)
        if sex:
            rec["sex"] = sex
        results.append(rec)

    return results


@router.post("/confirmed-mapping")
async def post_confirmed_mapping(
    req: LiteConfirmedMappingRequest,
    brand: str,
    season: str,
    email: str = Depends(require_brand_access),
    con=Depends(get_db),
):
    """매핑 확정 → 본인 사물함 저장 + 발주 추천 자동 재계산 (cascade).

    Cascade 정책 (Phase 1, DuckDB-only):
      - 발주 추천: 자동 재계산 (apply_budget=False) 후 본인 사물함 저장
      - 사이즈 배분: cascade 없음 (사용자가 confirmed-size로 명시 저장)
      - 데이터 소스: DuckDB style_timeseries + 본인 사물함 go_list.json (외부 의존 0)
    """
    # URL의 season(baseSeason, BrandSeasonContext 기반)을 권위적으로 사용.
    # frontend가 body에 targetSeason(26f)을 함께 보내면 GET 사물함 키(25f)와 mismatch되어
    # POST는 저장되지만 GET이 못 찾는 silent fail이 발생함.
    season_norm = season.lower()
    mapping_count = len(req.mappings)
    logger.info(
        f"[confirmed-mapping] email={email} brand={brand} season={season_norm} "
        f"mappings_count={mapping_count} body_season={req.season}"
    )

    # 1. 본인 사물함에 confirmed_mapping 저장
    confirmed = {
        "season": season_norm,
        "confirmed_at": _utc_now_iso(),
        "mappings": [m.model_dump() for m in req.mappings],
    }
    ok_cm = await user_storage.write_user_file(
        email, brand, season_norm, "confirmed_mapping.json", confirmed
    )
    if not ok_cm:
        logger.error(f"[confirmed-mapping] confirmed_mapping.json 로컬 파일 저장 실패 — email={email}")
        raise HTTPException(
            status_code=500,
            detail="confirmed_mapping 로컬 파일 저장 실패 — 파일 시스템 권한 점검 필요",
        )

    # 2. results 구성 (DuckDB 기반)
    results = _build_mapping_results(req, season_norm, con, brand)
    logger.info(f"[confirmed-mapping] _build_mapping_results 결과 results={len(results)}건")

    # 3. 컬러배분 + summary (DuckDB chart_data 기반, apply_budget=False)
    color_df = load_color_detail_duckdb(con, brand)
    go_data = await user_storage.read_user_only(email, brand, season_norm, "go_list.json")
    go_colors_map = load_go_colors_map_from_user_data(go_data)
    results, _category_budgets = apply_budget_and_color(
        results, color_df, go_colors_map,
        ref_at30_lookup=lambda ref_pc: calc_color_ratio_at_30pct_duckdb(con, brand, ref_pc),
        apply_budget=False,
        budget_config=None,
    )
    logger.info(
        f"[confirmed-mapping] apply_budget_and_color 후 results={len(results)}건 "
        f"colors_filled={sum(1 for r in results if r.get('colors'))}"
    )

    # 4. 본인 사물함에 order_recommendation 저장
    total = len(results)
    matched = sum(1 for r in results if r.get("추천발주량", 0) > 0)
    total_qty = sum(r.get("추천발주량", 0) for r in results)
    output_json = {
        "metadata": {
            "season": season_norm,
            "confirmed_at": confirmed["confirmed_at"],
            "total_styles": total,
            "matched_styles": matched,
            "total_recommendation_qty": total_qty,
            "scaled_count": 0,        # Lite는 예산 스케일링 없음
            "category_budgets": [],   # Lite는 예산 미포함
            "lite_mode": True,
        },
        "recommendations": results,
    }
    ok_or = await user_storage.write_user_file(
        email, brand, season_norm, "order_recommendation_data.json", output_json
    )
    if not ok_or:
        logger.error(f"[confirmed-mapping] order_recommendation_data.json 로컬 파일 저장 실패 — email={email}")
        raise HTTPException(
            status_code=500,
            detail="order_recommendation 로컬 파일 저장 실패 — 파일 시스템 권한 점검 필요",
        )

    return {
        "status": "ok",
        "total_styles": total,
        "matched_styles": matched,
        "total_recommendation_qty": total_qty,
        "lite_mode": True,
    }


@router.post("/confirmed-orders")
async def post_confirmed_orders(
    req: LiteConfirmedOrdersRequest,
    brand: str,
    season: str,
    email: str = Depends(require_brand_access),
):
    """확정수량 저장 (본인 사물함 only, cascade 없음)."""
    # URL season(baseSeason)을 권위적으로 사용 — GET 사물함 키와 일관.
    season_norm = season.lower()
    output = {
        "season": season_norm,
        "confirmed_at": _utc_now_iso(),
        "orders": [o.model_dump() for o in req.orders],
    }
    await user_storage.write_user_file(
        email, brand, season_norm, "confirmed_order_data.json", output
    )
    return {"status": "ok", "total_orders": len(req.orders)}


@router.post("/confirmed-size")
async def post_confirmed_size(
    body: dict,
    brand: str,
    season: str,
    email: str = Depends(require_brand_access),
):
    """사이즈 배분 mirroring 결과를 본인 사물함에 명시 저장 (덮어쓰기).

    body는 size_assortment_data.json 구조 (salesData, prevData, colorMapping, meta).
    """
    if not isinstance(body, dict) or "salesData" not in body:
        raise HTTPException(
            status_code=400,
            detail="size_assortment_data.json 구조가 필요합니다 (salesData 필수).",
        )
    payload = {**body, "confirmed_at": _utc_now_iso()}
    await user_storage.write_user_file(
        email, brand, season.lower(), "size_assortment_data.json", payload
    )
    return {"status": "ok"}


@router.post("/go-list")
async def post_go_list(
    brand: str,
    season: str,
    file: UploadFile = File(...),
    email: str = Depends(require_brand_access),
):
    """GO list 엑셀 업로드 → 본인 사물함에 저장.

    Phase 1 단순화: GO list 저장만 수행. 본인 매핑/수량 cascade는 향후
    (현재는 운영팀 baseline의 style_mapping을 그대로 사용).
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="엑셀 파일(.xlsx)만 업로드 가능합니다.")

    contents = await file.read()
    go_df = pd.read_excel(io.BytesIO(contents))
    if "STYLE_CD" not in go_df.columns:
        raise HTTPException(
            status_code=400,
            detail="필수 컬럼 STYLE_CD가 없습니다.",
        )

    go_styles = go_df["STYLE_CD"].dropna().astype(str).str.strip().unique().tolist()
    go_data = {
        "uploaded_at": _utc_now_iso(),
        "total_styles": len(go_styles),
        "total_rows": len(go_df),
        "styles": go_styles,
        "detail": go_df.fillna("").to_dict(orient="records"),
    }
    await user_storage.write_user_file(
        email, brand, season.lower(), "go_list.json", go_data
    )
    return {
        "status": "ok",
        "total_styles": len(go_styles),
        "total_rows": len(go_df),
    }


_RESET_FILES = {
    # Step3 매핑 리셋: GO list + 매핑 + 발주 + 사이즈 cascade 삭제 → 사용자가 GO list부터 새로 시작.
    "mapping": [
        "go_list.json",
        "confirmed_mapping.json",
        "order_recommendation_data.json",
        "size_assortment_data.json",
    ],
    "orders":  ["confirmed_order_data.json", "order_recommendation_data.json"],
    "size":    ["size_assortment_data.json"],
    "go":      ["go_list.json"],
    "all":     [
        "confirmed_mapping.json",
        "confirmed_order_data.json",
        "order_recommendation_data.json",
        "size_assortment_data.json",
        "go_list.json",
    ],
}


@router.post("/reset")
async def post_reset(
    brand: str,
    season: str,
    scope: str = Query(..., description="mapping | orders | size | go | all"),
    email: str = Depends(require_brand_access),
):
    """본인 사물함 영역 리셋 (scope별 파일 삭제). 팀 디폴트로 fallback."""
    if scope not in _RESET_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"잘못된 scope: {scope}. 허용: {list(_RESET_FILES.keys())}",
        )
    deleted: list[str] = []
    for fn in _RESET_FILES[scope]:
        ok = await user_storage.delete_user_file(email, brand, season.lower(), fn)
        if ok:
            deleted.append(fn)
    return {"status": "ok", "scope": scope, "deleted": deleted}
