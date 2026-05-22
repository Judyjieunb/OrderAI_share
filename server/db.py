"""
DuckDB 접근 레이어 (Lite 전용, read-only).

배경:
  Phase 1 Step 4. Lite 모드는 운영팀이 시즌당 1회 dump한 단일 DuckDB 파일을 read-only로 조회한다.
  파일 경로는 환경변수 DUCKDB_PATH로 오버라이드 가능 (배포 환경별 마운트 경로 차이 대응).

사용:
  from fastapi import Depends
  from server.db import get_db, query_season_summary

  @router.get("/api/lite/season-closing")
  async def season_closing(brand: str, season: str, con = Depends(get_db)):
      return query_season_summary(con, brand, season)

규칙:
  - read_only=True 강제 (Lite는 읽기만)
  - 모든 헬퍼는 brand/season 필수 파라미터
  - 결과는 dashboard JSON 반환 형식과 호환되도록 reconstruct
"""

import json
import logging
import os
from contextlib import contextmanager
from typing import Optional

import duckdb

logger = logging.getLogger(__name__)

# 배포 환경에 따라 다름 — Docker는 /data/duckdb/order_ai.duckdb 같은 마운트 경로 사용
DEFAULT_DUCKDB_PATH = "data/production/order_ai.duckdb"


def get_duckdb_path() -> str:
    return os.getenv("DUCKDB_PATH", DEFAULT_DUCKDB_PATH)


# ───────────── 커넥션 ─────────────

def get_db():
    """FastAPI dependency. read-only 커넥션을 yield 후 자동 종료."""
    path = get_duckdb_path()
    if not os.path.exists(path):
        raise RuntimeError(f"DuckDB 파일이 없습니다: {path} (DUCKDB_PATH 환경변수 확인)")
    con = duckdb.connect(path, read_only=True)
    try:
        yield con
    finally:
        con.close()


@contextmanager
def open_db():
    """스크립트/테스트용 컨텍스트 매니저 (FastAPI 외부에서 사용)."""
    path = get_duckdb_path()
    con = duckdb.connect(path, read_only=True)
    try:
        yield con
    finally:
        con.close()


# ───────────── 마스터 ─────────────

def query_brands(con) -> list[dict]:
    rows = con.execute("SELECT brand_code, brand_name FROM brands ORDER BY brand_code").fetchall()
    return [{"brand_code": r[0], "brand_name": r[1]} for r in rows]


def query_seasons(con, brand: str) -> list[dict]:
    rows = con.execute(
        """
        SELECT season_code, base_season, pipeline_run_at, pipeline_version
        FROM seasons WHERE brand_code = ?
        ORDER BY season_code DESC
        """,
        [brand.lower()],
    ).fetchall()
    return [
        {
            "season_code": r[0],
            "base_season": r[1],
            "pipeline_run_at": r[2].isoformat() if r[2] else None,
            "pipeline_version": r[3],
        }
        for r in rows
    ]


def query_meta(con, brand: str, season: str) -> Optional[dict]:
    """seasons 테이블의 메타 (pipeline_version 등) — stale 검증에 사용."""
    row = con.execute(
        """
        SELECT base_season, pipeline_run_at, pipeline_version, source_meta
        FROM seasons WHERE brand_code = ? AND season_code = ?
        """,
        [brand.lower(), season.lower()],
    ).fetchone()
    if not row:
        return None
    return {
        "base_season": row[0],
        "pipeline_run_at": row[1].isoformat() if row[1] else None,
        "pipeline_version": row[2],
        "source_meta": json.loads(row[3]) if row[3] else None,
    }


# ───────────── 시즌마감 / 클래스·아이템 ─────────────

def query_season_summary(con, brand: str, season: str) -> Optional[dict]:
    """season_closing_data.json 형태로 reconstruct."""
    summary_row = con.execute(
        "SELECT summary_json FROM season_summary WHERE brand_code=? AND season_code=?",
        [brand.lower(), season.lower()],
    ).fetchone()
    if not summary_row:
        return None

    rows = con.execute(
        """
        SELECT level, key, data_json FROM class_item_analysis
        WHERE brand_code=? AND season_code=? ORDER BY level, key
        """,
        [brand.lower(), season.lower()],
    ).fetchall()

    class_analysis = []
    item_analysis = []
    extras = {}
    for level, _key, data_json in rows:
        data = json.loads(data_json)
        if level == "class":
            class_analysis.append(data)
        elif level == "item":
            item_analysis.append(data)
        else:
            extras[level] = data

    metadata = extras.pop("metadata", {})
    return {
        "metadata": metadata,
        "summary": json.loads(summary_row[0]),
        "class_analysis": class_analysis,
        "item_analysis": item_analysis,
        **extras,
    }


# ───────────── 시계열 (Dashboard) ─────────────

def query_dashboard(con, brand: str, season: str) -> dict:
    """dashboard_data.json 형태로 reconstruct (hit/normal/shortage/risk).

    당해 시즌(period='current')만 — 과거 시즌은 ref-style lookup 전용.
    """
    rows = con.execute(
        """
        SELECT part_cd, color_cd, ai_diagnosis, chart_data
        FROM style_timeseries
        WHERE brand_code=? AND season_code=? AND period='current'
        ORDER BY ai_diagnosis, part_cd, color_cd
        """,
        [brand.lower(), season.lower()],
    ).fetchall()

    # part_cd 단위로 묶어서 total + colors 형태로 만든다
    by_part: dict[str, dict] = {}
    diagnosis_by_part: dict[str, str] = {}
    for part_cd, color_cd, diagnosis, chart_data in rows:
        data = json.loads(chart_data)
        entry = by_part.setdefault(part_cd, {"total": None, "colors": {}})
        if color_cd == "ALL":
            entry["total"] = data
            diagnosis_by_part[part_cd] = diagnosis
        else:
            entry["colors"][color_cd] = data

    result: dict[str, list] = {"hit": [], "normal": [], "shortage": [], "risk": []}
    for part_cd, entry in by_part.items():
        diagnosis = diagnosis_by_part.get(part_cd)
        if diagnosis in result and entry["total"] is not None:
            result[diagnosis].append(entry)
    return result


# ───────────── 매핑 ─────────────

def query_style_mapping(con, brand: str, season: str) -> dict:
    """style_mapping_data.json 형태로 reconstruct."""
    meta_row = con.execute(
        "SELECT metadata_json FROM style_mapping_meta WHERE brand_code=? AND season_code=?",
        [brand.lower(), season.lower()],
    ).fetchone()
    metadata = json.loads(meta_row[0]) if meta_row else {}

    rows = con.execute(
        """
        SELECT data_json FROM style_mapping
        WHERE brand_code=? AND season_code=? ORDER BY new_part_cd
        """,
        [brand.lower(), season.lower()],
    ).fetchall()
    styles = [json.loads(r[0]) for r in rows]
    return {"metadata": metadata, "styles": styles}


# ───────────── 발주 추천 ─────────────

def query_order_recommendation(con, brand: str, season: str) -> dict:
    meta_row = con.execute(
        """
        SELECT metadata_json FROM order_recommendation_meta
        WHERE brand_code=? AND season_code=?
        """,
        [brand.lower(), season.lower()],
    ).fetchone()
    metadata = json.loads(meta_row[0]) if meta_row else {}

    rows = con.execute(
        """
        SELECT data_json FROM order_recommendation
        WHERE brand_code=? AND season_code=? ORDER BY new_part_cd
        """,
        [brand.lower(), season.lower()],
    ).fetchall()
    recommendations = [json.loads(r[0]) for r in rows]
    return {"metadata": metadata, "recommendations": recommendations}


# ───────────── 사이즈 배분 ─────────────

def query_size_assortment(con, brand: str, season: str) -> dict:
    """size_assortment_data.json 형태로 reconstruct.

    반환: salesData / prevData / colorMapping / meta
          + category_size_dist / category_sample_count / ref_meta (Phase 3-1 신규)
    """
    import json as _json

    rows = con.execute(
        """
        SELECT period, sex_nm, class2, cat_nm, sub_cat_nm, item, item_nm,
               sesn_sub_nm, fit_info1, color_range, size_cd, order_qty, sale_qty
        FROM size_assortment WHERE brand_code=? AND season_code=?
        """,
        [brand.lower(), season.lower()],
    ).fetchall()

    sales: list[dict] = []
    prev: list[dict] = []
    for period, sex, c2, cat, scat, item, item_nm, sesn, fit, crange, sz, oq, sq in rows:
        record = {
            "SEX_NM": sex, "CLASS2": c2, "CAT_NM": cat, "SUB_CAT_NM": scat,
            "ITEM": item, "ITEM_NM": item_nm,
            "SESN_SUB_NM": sesn, "FIT_INFO1": fit,
            "COLOR_RANGE": crange, "SIZE_CD": sz,
            "ORDER_QTY": oq, "SALE_QTY": sq, "time_period": period,
        }
        (sales if period == "current" else prev).append(record)

    color_rows = con.execute(
        """
        SELECT color_cd, color_nm, color_range
        FROM size_color_mapping WHERE brand_code=? AND season_code=?
        """,
        [brand.lower(), season.lower()],
    ).fetchall()
    color_mapping = [
        {"컬러코드": cd, "컬러명": nm, "COLOR_RANGE": cr}
        for cd, nm, cr in color_rows
    ]

    base_season_row = con.execute(
        "SELECT base_season FROM seasons WHERE brand_code=? AND season_code=?",
        [brand.lower(), season.lower()],
    ).fetchone()
    base_season = base_season_row[0] if base_season_row else None

    # Phase 3-1: 카테고리 분포 + ref_meta + size_order
    meta_row = con.execute(
        """
        SELECT category_size_dist, category_sample_count, ref_meta, size_order
        FROM size_assortment_meta WHERE brand_code=? AND season_code=?
        """,
        [brand.lower(), season.lower()],
    ).fetchone()

    def _parse(v):
        if v is None:
            return None
        return _json.loads(v) if isinstance(v, str) else v

    if meta_row:
        category_size_dist = _parse(meta_row[0]) or {}
        category_sample_count = _parse(meta_row[1]) or {}
        ref_meta = _parse(meta_row[2]) or {}
        size_order = _parse(meta_row[3]) or ["XS", "S", "M", "L", "XL", "XXL"]
    else:
        category_size_dist = {}
        category_sample_count = {}
        ref_meta = {}
        size_order = ["XS", "S", "M", "L", "XL", "XXL"]

    return {
        "salesData": sales,
        "prevData": prev,
        "colorMapping": color_mapping,
        "meta": {
            "sizeOrder": size_order,
            "baseSeason": base_season,
            "hierarchy": ["SEX_NM", "CLASS2", "CAT_NM", "SUB_CAT_NM", "ITEM", "ITEM_NM",
                          "SESN_SUB_NM", "FIT_INFO1"],
        },
        "category_size_dist": category_size_dist,
        "category_sample_count": category_sample_count,
        "ref_meta": ref_meta,
    }
