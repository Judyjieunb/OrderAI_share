"""
Lite 컨테이너용 매핑/컬러배분 cascade 헬퍼 (DuckDB 기반).

server.api의 헬퍼는 Excel(`output/*_TimeSeries_Analysis_Result.xlsx`),
Snowflake(d1/d2), public/go_list.json에 의존하기 때문에 Phase 1 Lite 컨테이너에서
사용할 수 없다 (`config_loader` 모듈 자체가 컨테이너에 미포함).

본 모듈은 DuckDB `style_timeseries.chart_data`(JSON) + 본인 사물함 go_list.json만으로
Lite confirmed-mapping cascade에 필요한 모든 데이터를 산출한다.

server.api의 다음 헬퍼와 동등:
  _load_color_detail            → load_color_detail_duckdb
  _calc_color_ratio_at_30pct    → calc_color_ratio_at_30pct_duckdb
  _load_go_colors_map           → load_go_colors_map_from_user_data
  _load_style_summary           → load_style_summary_duckdb
  _lookup_ref_from_d1           → lookup_ref_summary_duckdb (Lite는 DuckDB만 사용)
"""

from __future__ import annotations

import json
import math
from typing import Optional

import pandas as pd


# server.services.color_allocation / order_calc과 호환되도록 동일 컬럼명 사용
COL_PART_CD = "PART_CD"
COL_COLOR_CD = "COLOR_CD"
COL_ITEM_NM = "ITEM_NM"
COL_PRDT_NM = "PRDT_NM"
COL_PRICE = "판매가"
COL_TOTAL_ORDER = "총발주"
COL_TOTAL_INBOUND = "총입고"
COL_TOTAL_SALE = "총판매"
COL_SELL_RATE = "최종판매율"
COL_AI_DIAG = "AI_진단"
COL_AI_ORDER = "AI제안 발주량"

# 내부용 alias (기존 함수 호환)
_COL_PART_CD = COL_PART_CD
_COL_COLOR_CD = COL_COLOR_CD
_COL_AI_ORDER = COL_AI_ORDER
_COL_PRICE = COL_PRICE


# CAT_NM_ENG/한글 → CLASS2 매핑 (server.api._CAT_TO_CLASS2와 동일)
CAT_TO_CLASS2 = {
    "T-shirts": "Inner", "Sweater": "Inner", "Sweatshirts/Hoodie": "Inner",
    "Shirt": "Inner", "Sleeveless": "Inner", "Sweatsuit": "Inner",
    "Denim": "Bottom", "Pants": "Bottom", "Shorts": "Bottom",
    "Skirt": "Bottom", "Leggings": "Bottom",
    "Outerwear": "Outer", "Padded Jacket": "Outer", "Fleece": "Outer",
    "티셔츠": "Inner", "스웨터": "Inner", "맨투맨/후드": "Inner",
    "셔츠": "Inner", "트레이닝셋업": "Inner",
    "데님": "Bottom", "팬츠": "Bottom", "스커트": "Bottom", "레깅스": "Bottom",
    "아우터": "Outer", "패딩": "Outer", "후리스": "Outer",
    "모자": "Outer", "기타용품": "Outer",
}


def ceil_10(x) -> int:
    """10단위 반올림 (server.api._ceil_10 동등)"""
    if x is None:
        return 0
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0
    if math.isnan(v) or v <= 0:
        return 0
    return int(round(v / 10) * 10)


def sex_from_style_cd(part_cd: str) -> str:
    """스타일코드 2번째 문자로 성별 판별 (server.api._sex_from_style_cd 동등)"""
    if len(part_cd) >= 2:
        code = part_cd[1].upper()
        return {"A": "공용", "F": "여성", "L": "남성"}.get(code, "")
    return ""


def load_color_detail_duckdb(con, brand: str) -> pd.DataFrame:
    """style_timeseries의 컬러 단위 row를 chart_data JSON 파싱해 DataFrame으로 반환.

    `_load_color_detail`(Excel 기반)과 동일한 컬럼 스키마를 제공해 apply_budget_and_color가
    그대로 동작하도록 한다. brand별 격리 — brand_code 필터 필수.

    Returns:
        DataFrame[PART_CD, COLOR_CD, AI제안 발주량, 판매가, 총발주, 총입고, 총판매,
                 최종판매율, ITEM_NM, PRDT_NM]
    """
    rows = con.execute(
        """
        SELECT part_cd, color_cd, chart_data
        FROM style_timeseries
        WHERE brand_code = ? AND color_cd != 'ALL'
        """,
        [brand.lower()],
    ).fetchall()

    out: list[dict] = []
    for part_cd, color_cd, chart_data_json in rows:
        cd = json.loads(chart_data_json) if isinstance(chart_data_json, str) else chart_data_json
        if not isinstance(cd, dict):
            continue
        analysis = cd.get("analysis") or {}
        info = cd.get("itemInfo") or {}

        def _num(v):
            try:
                return float(v or 0)
            except (TypeError, ValueError):
                return 0.0

        out.append({
            _COL_PART_CD: part_cd,
            _COL_COLOR_CD: color_cd,
            _COL_AI_ORDER: _num(analysis.get("AI제안 발주량")),
            _COL_PRICE: _num(info.get("price")),
            "총발주": _num(analysis.get("총발주")),
            "총입고": _num(analysis.get("총입고")),
            "총판매": _num(analysis.get("총판매")),
            "최종판매율": _num(analysis.get("최종판매율")),
            "ITEM_NM": str(info.get("name") or info.get("item_nm") or ""),
            "PRDT_NM": str(info.get("prdt_nm") or ""),
        })
    return pd.DataFrame(out)


def calc_color_ratio_at_30pct_duckdb(con, brand: str, ref_part_cd: str) -> dict:
    """ref 스타일의 판매율 30% 도달 시점 컬러별 판매비중 계산 (DuckDB 기반).

    chart_data.chartData (weekly increment in/sale) 누계로 30% 도달 시점 탐색.

    Returns: {color_cd: {qty, ratio}} 합계 ~100%. 빈 dict면 데이터 부족/30% 미도달.
    """
    if not ref_part_cd:
        return {}

    rows = con.execute(
        """
        SELECT color_cd, chart_data
        FROM style_timeseries
        WHERE brand_code = ? AND part_cd = ? AND color_cd != 'ALL'
        """,
        [brand.lower(), ref_part_cd],
    ).fetchall()
    if not rows:
        return {}

    # color_cd → [(date, in, sale), ...]
    color_weekly: dict[str, list[tuple[str, float, float]]] = {}
    weeks_set: set[str] = set()
    for color_cd, chart_data_json in rows:
        cd = json.loads(chart_data_json) if isinstance(chart_data_json, str) else chart_data_json
        if not isinstance(cd, dict):
            continue
        cdata = cd.get("chartData") or []
        series: list[tuple[str, float, float]] = []
        for p in cdata:
            date = str(p.get("date") or "")
            if not date:
                continue
            try:
                in_qty = float(p.get("in") or 0)
                sale_qty = float(p.get("sale") or 0)
            except (TypeError, ValueError):
                continue
            series.append((date, in_qty, sale_qty))
            weeks_set.add(date)
        if series:
            color_weekly[color_cd] = series

    if not color_weekly:
        return {}

    # 전체 누계 inbound/sale 시계열 — 시즌 첫 주부터 정렬 가정 (chart_data 생성 시 정렬됨)
    # 각 color의 series는 동일 주차 순서를 가짐. 첫 row의 주차 순서를 사용.
    sample_series = next(iter(color_weekly.values()))
    weeks_in_order = [w for w, _, _ in sample_series]

    cum_inbound = 0.0
    cum_sale = 0.0
    target_idx: Optional[int] = None
    # 주차별 합산: 모든 color의 같은 인덱스 row 합
    n = len(weeks_in_order)
    color_keys = list(color_weekly.keys())
    for i in range(n):
        week_in = sum(color_weekly[c][i][1] for c in color_keys if i < len(color_weekly[c]))
        week_sale = sum(color_weekly[c][i][2] for c in color_keys if i < len(color_weekly[c]))
        cum_inbound += week_in
        cum_sale += week_sale
        if cum_inbound > 0 and (cum_sale / cum_inbound) >= 0.30:
            target_idx = i
            break

    if target_idx is None:
        return {}

    # 30% 도달 시점까지의 컬러별 누적 판매
    color_sales: dict[str, float] = {}
    for c in color_keys:
        s = sum(color_weekly[c][j][2] for j in range(target_idx + 1) if j < len(color_weekly[c]))
        if s > 0:
            color_sales[c] = s

    total = sum(color_sales.values())
    if total <= 0:
        return {}

    return {
        str(k): {"qty": int(v), "ratio": round(float(v / total * 100), 1)}
        for k, v in color_sales.items()
    }


def load_style_summary_duckdb(con, brand: str) -> pd.DataFrame:
    """DuckDB style_timeseries에서 스타일(PART_CD) 레벨 집계 DataFrame.

    server.api._load_style_summary(Excel 기반)와 동일 컬럼 스키마. AI진단은 ALL row의 값을
    사용 (대표 진단). AI제안 발주량은 컬러 단위 row 합산 (ALL row에는 없음).
    """
    rows = con.execute(
        """
        SELECT part_cd, color_cd, chart_data
        FROM style_timeseries
        WHERE brand_code = ?
        """,
        [brand.lower()],
    ).fetchall()

    def _num(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    # PART_CD → {집계 필드}
    style_agg: dict[str, dict] = {}
    for part_cd, color_cd, chart_data_json in rows:
        cd = json.loads(chart_data_json) if isinstance(chart_data_json, str) else chart_data_json
        if not isinstance(cd, dict):
            continue
        analysis = cd.get("analysis") or {}
        info = cd.get("itemInfo") or {}
        bucket = style_agg.setdefault(part_cd, {
            COL_PART_CD: part_cd,
            COL_ITEM_NM: "",
            COL_PRDT_NM: "",
            COL_PRICE: 0.0,
            COL_TOTAL_ORDER: 0.0,
            COL_TOTAL_INBOUND: 0.0,
            COL_TOTAL_SALE: 0.0,
            COL_SELL_RATE: 0.0,
            COL_AI_DIAG: "-",
            COL_AI_ORDER: 0.0,
        })
        if color_cd == "ALL":
            bucket[COL_TOTAL_ORDER] = _num(analysis.get("총발주"))
            bucket[COL_TOTAL_INBOUND] = _num(analysis.get("총입고"))
            bucket[COL_TOTAL_SALE] = _num(analysis.get("총판매"))
            bucket[COL_SELL_RATE] = _num(analysis.get("최종판매율"))
            diag = analysis.get("AI_진단")
            if diag:
                bucket[COL_AI_DIAG] = str(diag)
            bucket[COL_PRICE] = _num(info.get("price"))
            if not bucket[COL_ITEM_NM]:
                bucket[COL_ITEM_NM] = str(info.get("name") or info.get("item_nm") or "")
            if not bucket[COL_PRDT_NM]:
                bucket[COL_PRDT_NM] = str(info.get("prdt_nm") or "")
        else:
            bucket[COL_AI_ORDER] += _num(analysis.get("AI제안 발주량"))
            if not bucket[COL_PRICE]:
                bucket[COL_PRICE] = _num(info.get("price"))
            if not bucket[COL_ITEM_NM]:
                bucket[COL_ITEM_NM] = str(info.get("name") or info.get("item_nm") or "")
            if not bucket[COL_PRDT_NM]:
                bucket[COL_PRDT_NM] = str(info.get("prdt_nm") or "")

    return pd.DataFrame(list(style_agg.values()))


def lookup_ref_summary_duckdb(con, brand: str, ref_part_cd: str) -> dict:
    """ref PART_CD의 마감실적 lookup (server.api._lookup_ref_from_d1의 Lite 대체).

    Lite는 d1(season_raw)이 없으므로 DuckDB style_timeseries ALL row를 fallback으로 사용.
    DuckDB에 없는 ref는 빈 dict (Lite의 ref는 모두 baseline에 사전계산되어 있음).
    """
    if not ref_part_cd:
        return {}
    row = con.execute(
        """
        SELECT chart_data
        FROM style_timeseries
        WHERE brand_code = ? AND part_cd = ? AND color_cd = 'ALL'
        LIMIT 1
        """,
        [brand.lower(), ref_part_cd],
    ).fetchone()
    if not row:
        return {}
    cd = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    if not isinstance(cd, dict):
        return {}
    analysis = cd.get("analysis") or {}
    info = cd.get("itemInfo") or {}

    def _num(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    return {
        "ref_총판매": int(_num(analysis.get("총판매"))),
        "ref_총발주": int(_num(analysis.get("총발주"))),
        "ref_판매율": float(_num(analysis.get("최종판매율"))),
        "판매가": int(_num(info.get("price"))),
        "ref_item_nm": str(info.get("name") or info.get("item_nm") or ""),
        "ref_prdt_nm": str(info.get("prdt_nm") or ""),
    }


def load_go_colors_map_from_user_data(go_data: Optional[dict]) -> dict:
    """본인 사물함 go_list.json → {style_cd: [color_cd, ...]}.

    Lite Phase 1 정책: GO list는 본인 사물함에만 존재한다.
    Full의 public/go_list.json 글로벌 의존을 제거.
    """
    go_colors_map: dict[str, list[str]] = {}
    if not go_data:
        return go_colors_map
    for row in (go_data.get("detail") or []):
        sc = str(row.get("STYLE_CD", "")).strip()
        cc = str(row.get("COLOR_CD", "")).strip()
        if not (sc and cc):
            continue
        bucket = go_colors_map.setdefault(sc, [])
        if cc not in bucket:
            bucket.append(cc)
    return go_colors_map
