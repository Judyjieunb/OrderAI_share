"""
PLC 표준 곡선 빌드 도구 — 자기 브랜드의 GT CSV 로 PLC 표준 생성.

원본 로직: test/plc_analysis/plc_forecast_gt.py::calc_plc 100% 이식
  - 피크 정규화 → 다개년 평균 (이상치 제거) → forecast_index = ratio of ratios → 3주 rolling MA

이식 시 변경:
  - 하드코딩 상수 (SEASONS, ITEM_NM_MAP, FW_ORDER_RANGE 등) → config 에서 로드
  - season_type 자동 도출 (brand_config.targetSeason 마지막 글자 F→fw, S→ss)
  - SS 분기 지원 (specs.py::fw_order 메서드 이용)
  - 출력 경로 = config_loader.get_plc_forecast_path()
  - 차트/snowflake 비교 코드 미포함 (별도 분석 도구 책임)

CLI:
  .venv/bin/python scripts/plc_engine/build_plc_standard.py
  .venv/bin/python scripts/plc_engine/build_plc_standard.py --from-csv data/MLB_GT_23F+24F+25F.csv

자세한 정책: docs/PLC_GUIDE.md
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

# scripts/ 를 sys.path 에 추가 (직접 실행 시 import 호환)
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from plc_engine.specs import BrandSpec, SeasonSpec  # noqa: E402
from plc_engine.utils import remove_outliers  # noqa: E402
from config_loader import (  # noqa: E402
    PLC_ENGINE_CONFIG_PATH,
    get_base_season,
    get_brand,
    get_plc_forecast_path,
    get_target_season,
)

_BASE_DIR = os.path.dirname(_SCRIPTS_DIR)


# ── ISO WEEK_NUM → 캘린더 월 (FW/SS 공통) ──
MONTH_MAP = {
    1: 1, 2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 2, 8: 2, 9: 3,
    10: 3, 11: 3, 12: 3, 13: 3, 14: 4, 15: 4, 16: 4, 17: 4,
    18: 5, 19: 5, 20: 5, 21: 5, 22: 5,
    23: 6, 24: 6, 25: 6, 26: 7, 27: 7, 28: 7, 29: 7, 30: 7,
    31: 8, 32: 8, 33: 8, 34: 8, 35: 9, 36: 9, 37: 9, 38: 9,
    39: 10, 40: 10, 41: 10, 42: 10, 43: 10,
    44: 11, 45: 11, 46: 11, 47: 11,
    48: 12, 49: 12, 50: 12, 51: 12, 52: 1,
}


# ── 브랜드명 → DB_SCS_W::BRD_CD 단일자 코드 (Snowflake fallback 용) ──
BRAND_CODE_MAP = {
    'MLB': 'M',
    'DISCOVERY': 'X',
    'DUVETICA': 'V',
    'SERGIO': 'ST',
    'MLBKIDS': 'I',
}


# ── 유틸 ──

def derive_season_type(target_season: str) -> str:
    """targetSeason 마지막 글자로 season_type 도출."""
    if not target_season:
        raise RuntimeError("brand_config.json::targetSeason 누락")
    last = target_season[-1].upper()
    if last == 'F':
        return 'fw'
    if last == 'S':
        return 'ss'
    raise RuntimeError(
        f"targetSeason {target_season!r} 마지막 글자가 F/S 가 아님. "
        "지원 형식: '25F', '26S' 등."
    )


def find_gt_csv(brand: str, seasons_for_plc: list[str]) -> str:
    """data/{BRAND}_GT_*.csv 중 seasons_for_plc 를 모두 포함하는 파일 자동 탐색."""
    pattern = os.path.join(_BASE_DIR, 'data', f'{brand.upper()}_GT_*.csv')
    candidates = sorted(glob.glob(pattern))
    if not candidates:
        raise FileNotFoundError(
            f"GT CSV 없음: {pattern}\n"
            f"  배치: data/{brand.upper()}_GT_*.csv (예: data/MLB_GT_23F+24F+25F.csv)\n"
            f"  또는 --from-csv 로 직접 지정."
        )

    needed = set(seasons_for_plc)
    for path in candidates:
        try:
            df = pd.read_csv(path, usecols=['SSN_CD'])
            seasons_in_file = set(df['SSN_CD'].dropna().unique())
            if needed.issubset(seasons_in_file):
                return path
        except Exception:
            continue

    raise FileNotFoundError(
        f"GT CSV 후보 {len(candidates)}개 중 seasons_for_plc={seasons_for_plc} 를 "
        f"모두 포함하는 파일 없음.\n"
        f"  후보: {[os.path.basename(p) for p in candidates]}\n"
        f"  또는 --from-csv 로 직접 지정."
    )


def query_snowflake_for_plc(brand: str, seasons_for_plc: list[str]) -> pd.DataFrame:
    """GT csv 미발견 시 Snowflake 에서 PLC 학습용 7컬럼 직접 조회.

    Args:
        brand: brand_config 의 brand 이름 (예: 'MLB'). BRAND_CODE_MAP 으로 단일자 변환.
        seasons_for_plc: 조회 시즌 리스트 (예: ['23F','24F','25F']).

    Returns:
        DataFrame with cols: SSN_CD, PROD_CD, COLOR_CD, ITEM, WEEK_OF_YEAR,
                             SC_SALE_QTY_ALL, SC_SALE_QTY_TAX.
    """
    from snowflake_client import execute_query

    brand_code = BRAND_CODE_MAP.get(brand.upper())
    if not brand_code:
        raise RuntimeError(
            f"BRAND_CODE_MAP 에 {brand!r} 없음. "
            f"build_plc_standard.py 의 BRAND_CODE_MAP 에 추가하세요.\n"
            f"  현재 등록: {sorted(BRAND_CODE_MAP.keys())}"
        )

    sql_path = os.path.join(_BASE_DIR, 'queries', 'plc_standard.sql')
    if not os.path.exists(sql_path):
        raise FileNotFoundError(f"SQL 파일 없음: {sql_path}")
    with open(sql_path, encoding='utf-8') as f:
        sql_template = f.read()

    seasons_csv = ", ".join(f"'{s}'" for s in seasons_for_plc)
    sql = sql_template.replace('{brand}', brand_code).replace('{seasons_csv}', seasons_csv)

    print(f"[Snowflake] PLC 표준 데이터 조회: brand={brand_code}, seasons={seasons_for_plc}")
    df = execute_query(sql)
    if df is None:
        raise RuntimeError(
            "Snowflake 조회 실패. 확인:\n"
            "  1. .env 의 SNOWFLAKE_* 환경변수 (SETUP.md §4 참조)\n"
            "  2. SSO 모드면 브라우저 팝업 완료\n"
            "  3. 본 service account 의 FNF.PRCS.DB_SCS_W SELECT 권한"
        )
    if df.empty:
        raise RuntimeError(
            f"Snowflake 조회 결과 0행. brand_code={brand_code!r}, seasons={seasons_for_plc!r}.\n"
            "  브랜드 코드 / 시즌 코드가 DB_SCS_W 에 존재하는지 확인."
        )
    print(f"[Snowflake] PLC 표준 데이터: {len(df):,}행")
    return df


# ── 학습 로직 (원본 plc_forecast_gt.py::load_and_prepare + calc_plc 이식) ──

def prepare_weekly(
    df_raw: pd.DataFrame,
    seasons_for_plc: list[str],
    plc_exclude_prods: list[str],
    item_nm_map: dict,
    fwo_range: tuple,
    sale_col: str,
    fw_order_callable,
) -> pd.DataFrame:
    """원본 load_and_prepare(mode='avg') 이식: SC 평균 판매 집계.

    입력 DataFrame 은 GT csv (pd.read_csv) 또는 Snowflake 쿼리 결과 둘 다 가능.
    필요 컬럼: SSN_CD, PROD_CD, ITEM, WEEK_OF_YEAR, sale_col.
    """
    df = df_raw[df_raw['SSN_CD'].isin(seasons_for_plc)].copy()
    if plc_exclude_prods:
        before = len(df)
        df = df[~df['PROD_CD'].isin(plc_exclude_prods)]
        print(f"PLC 제외: {plc_exclude_prods} ({before}→{len(df)}행)")
    df['ITEM_NM'] = df['ITEM'].map(item_nm_map).fillna(df['ITEM'])
    df['FW_ORDER'] = df['WEEK_OF_YEAR'].apply(fw_order_callable)
    df = df[(df['FW_ORDER'] >= fwo_range[0]) & (df['FW_ORDER'] <= fwo_range[1])]

    agg = df.groupby(['SSN_CD', 'ITEM', 'ITEM_NM', 'WEEK_OF_YEAR', 'FW_ORDER']).agg(
        SALE_QTY_SUM=(sale_col, 'sum'),
        SC_COUNT=('PROD_CD', 'nunique'),
    ).reset_index()
    agg['SALE_QTY'] = agg['SALE_QTY_SUM'] / agg['SC_COUNT']  # mode='avg'

    weekly = agg[['SSN_CD', 'ITEM', 'ITEM_NM', 'WEEK_OF_YEAR', 'FW_ORDER', 'SALE_QTY', 'SC_COUNT']]
    print(f"시즌: {seasons_for_plc}, 총 행: {len(df):,} → 집계 후: {len(weekly):,}")
    return weekly


def calc_plc(weekly: pd.DataFrame) -> pd.DataFrame:
    """원본 calc_plc 이식: 피크 정규화 + 이상치 제거 + forecast_index smoothing."""
    # 1. 피크 정규화
    peaks = (weekly.groupby(['SSN_CD', 'ITEM'])['SALE_QTY'].max()
             .reset_index().rename(columns={'SALE_QTY': 'PEAK_QTY'}))
    normed = weekly.merge(peaks, on=['SSN_CD', 'ITEM'])
    normed['NORM_RATIO'] = np.where(
        normed['PEAK_QTY'] > 0, normed['SALE_QTY'] / normed['PEAK_QTY'], 0,
    )

    # 2. 다개년 평균 비율 (이상치 제거)
    plc_records = []
    for (item, item_nm, wn, fwo), grp in normed.groupby(['ITEM', 'ITEM_NM', 'WEEK_OF_YEAR', 'FW_ORDER']):
        vals = grp['NORM_RATIO'].dropna().values
        if len(vals) == 0:
            continue
        filtered = remove_outliers(vals)
        plc_records.append({
            'ITEM': item, 'ITEM_NM': item_nm, 'WEEK_NUM': wn, 'FW_ORDER': fwo,
            'PLC_RATIO': float(np.mean(filtered)), 'N_USED': len(filtered),
        })
    plc = pd.DataFrame(plc_records)

    # 3. 예측용 지수: PLC 비율의 주차간 변화율
    plc_sorted = plc.sort_values(['ITEM', 'FW_ORDER']).copy()
    plc_sorted['PREV_FW_ORDER'] = plc_sorted['FW_ORDER'] - 1
    prev = plc_sorted[['ITEM', 'FW_ORDER', 'PLC_RATIO', 'N_USED']].rename(
        columns={'FW_ORDER': 'PREV_FW_ORDER', 'PLC_RATIO': 'PREV_RATIO', 'N_USED': 'PREV_N'},
    )
    forecast = plc_sorted.merge(prev, on=['ITEM', 'PREV_FW_ORDER'], how='left')
    forecast['RAW_INDEX'] = np.where(
        (forecast['PREV_RATIO'] > 0) & (forecast['N_USED'] >= 2) & (forecast['PREV_N'] >= 2),
        forecast['PLC_RATIO'] / forecast['PREV_RATIO'], np.nan,
    )

    # 4. FORECAST_INDEX 스무딩 — 아이템별 3주 이동평균
    forecast = forecast.sort_values(['ITEM', 'FW_ORDER'])
    forecast['FORECAST_INDEX'] = (
        forecast.groupby('ITEM')['RAW_INDEX']
        .transform(lambda s: s.rolling(3, min_periods=1, center=True).mean())
    )
    return forecast


def save_csv(forecast: pd.DataFrame, out_path: str):
    """원본 save_csv 이식: 출력 컬럼 순서/내용 동일."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    output = (
        forecast[forecast['FORECAST_INDEX'].notna()]
        [['ITEM', 'ITEM_NM', 'WEEK_NUM', 'FW_ORDER', 'PLC_RATIO', 'FORECAST_INDEX', 'N_USED']]
        .sort_values(['ITEM', 'FW_ORDER'])
        .copy()
    )
    output['MONTH'] = output['WEEK_NUM'].map(MONTH_MAP)
    output.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"\n저장: {out_path}")
    print(f"  행 수: {len(output):,}, 아이템 수: {output['ITEM'].nunique()}")


# ── 검증 / 리포트 ──

def check_sufficiency(weekly: pd.DataFrame, seasons_for_plc: list[str]):
    """≥2 시즌 데이터 필수. 부족 시 cold-start guidance + RuntimeError."""
    actual = set(weekly['SSN_CD'].unique())
    needed = set(seasons_for_plc)
    found = actual & needed
    if len(found) < 2:
        raise RuntimeError(
            f"최소 2 시즌의 데이터 필요. 발견: {sorted(found)}, 필요: {sorted(needed)}.\n"
            "Cold-start 브랜드 대응:\n"
            "  1. AX팀에 seed PLC 요청 (1회 한정).\n"
            f"  2. {get_plc_forecast_path()} 에 받은 파일 배치.\n"
            "  3. 시즌 종료 후 자체 데이터로 본 스크립트 재실행 → 자체 PLC 로 전환.\n"
            "자세히: docs/PLC_GUIDE.md §Cold-start 브랜드 대응"
        )


def print_coverage(weekly: pd.DataFrame, forecast: pd.DataFrame, seasons_for_plc: list[str]):
    print("\n=== Coverage Report ===")
    print(f"PLC 입력 시즌: {seasons_for_plc}")
    counts = weekly.groupby('SSN_CD')['ITEM'].nunique()
    for ssn in seasons_for_plc:
        print(f"  {ssn}: 아이템 {counts.get(ssn, 0)}개")
    valid = forecast[forecast['FORECAST_INDEX'].notna()]['ITEM'].nunique() if not forecast.empty else 0
    total = forecast['ITEM'].nunique() if not forecast.empty else 0
    print(f"\n학습 결과:")
    print(f"  PLC 추출 아이템: {valid}")
    print(f"  Insufficient data (fallback): {total - valid}")


# ── Drift Report ──

def compute_drift(old_df: pd.DataFrame, new_df: pd.DataFrame) -> dict:
    """기존 PLC vs 새 PLC 의 평균 변화율 (MAPE) 계산.

    (ITEM, WEEK_NUM) 단위로 매칭. old=0 row 는 분모 0 회피 위해 skip.

    Returns:
        dict: mape_pct, n_matched, n_new, top_items (list of (item, item_mape_pct)), merged_df
    """
    cols = ['ITEM', 'WEEK_NUM', 'PLC_RATIO']
    merged = old_df[cols].merge(
        new_df[cols],
        on=['ITEM', 'WEEK_NUM'],
        suffixes=('_old', '_new'),
    )
    valid = merged[merged['PLC_RATIO_old'] > 0].copy()
    valid['abs_diff'] = (valid['PLC_RATIO_new'] - valid['PLC_RATIO_old']).abs()
    valid['pct_diff'] = valid['abs_diff'] / valid['PLC_RATIO_old']
    mape_pct = float(valid['pct_diff'].mean() * 100) if len(valid) > 0 else 0.0
    item_mape = (
        valid.groupby('ITEM')['pct_diff'].mean()
        .sort_values(ascending=False)
        .head(5)
    )
    top_items = [(item, float(v * 100)) for item, v in item_mape.items()]
    return {
        'mape_pct': mape_pct,
        'n_matched': len(valid),
        'n_new': len(new_df),
        'top_items': top_items,
        'merged_df': merged,
    }


def print_drift_report(drift: dict, has_old: bool):
    """분기별 메시지 출력 (<5% / 5-30% / >30%)."""
    print("\n=== Drift Report ===")
    if not has_old:
        print("[INFO] 첫 생성 — 비교할 기존 PLC 없음.")
        return
    if drift['n_matched'] == 0:
        print("[WARNING] 매칭된 (ITEM, WEEK_NUM) 짝 0건 — 비교 불가. "
              "기존 csv 와 새 csv 의 ITEM/WEEK_NUM 범위 점검.")
        return

    mape = drift['mape_pct']
    print(f"평균 변화율 (기존 PLC 대비): {mape:.1f}%")
    print(f"  비교 대상: {drift['n_matched']}/{drift['n_new']} row 매칭 (같은 아이템·주차 짝)")

    if mape < 5:
        print("[INFO] 변화 미미 — 재생성 효과 없음. 기존 PLC 유지 권장. 새 csv 출시 보류 검토.")
    elif mape <= 30:
        print("[INFO] 정상적인 PLC 적응. 새 표준을 다음 시즌부터 사용.")
        if drift['top_items']:
            top_str = ", ".join(f"{item} ({v:.0f}%)" for item, v in drift['top_items'])
            print(f"  Top 5 변화 큰 아이템: {top_str}")
    else:
        print("[WARNING] 큰 변화 — 외부 요인 또는 데이터 오류 의심. raw 데이터 검증 후 재실행 권장.")
        if drift['top_items']:
            top_str = ", ".join(f"{item} ({v:.0f}%)" for item, v in drift['top_items'])
            print(f"  Top 5 변화 큰 아이템: {top_str}")


def save_drift_detail_csv(merged_df: pd.DataFrame, out_dir: str, brand: str, season_type: str) -> str:
    """>30% 케이스 전용 상세 비교 csv. 같은 폴더에 {brand}_{type}_drift_report_{timestamp}.csv."""
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f'{brand.lower()}_{season_type}_drift_report_{timestamp}.csv'
    out_path = os.path.join(out_dir, fname)

    detail = merged_df[merged_df['PLC_RATIO_old'] > 0].copy()
    detail['ABS_DIFF'] = (detail['PLC_RATIO_new'] - detail['PLC_RATIO_old']).abs()
    detail['PCT_DIFF'] = detail['ABS_DIFF'] / detail['PLC_RATIO_old'] * 100
    detail = detail.rename(columns={
        'PLC_RATIO_old': 'OLD_PLC_RATIO',
        'PLC_RATIO_new': 'NEW_PLC_RATIO',
    })
    detail = detail[['ITEM', 'WEEK_NUM', 'OLD_PLC_RATIO', 'NEW_PLC_RATIO', 'ABS_DIFF', 'PCT_DIFF']]
    detail = detail.sort_values('PCT_DIFF', ascending=False)
    detail.to_csv(out_path, index=False, encoding='utf-8-sig')
    return out_path


# ── 메인 ──

def _load_season_cfg(base_season: str, season_type: str) -> dict:
    """SeasonSpec.from_json 으로 시즌 설정 로드. 미등록 시 자동 fallback (specs.py 에서 처리)."""
    spec = SeasonSpec.from_json(PLC_ENGINE_CONFIG_PATH, base_season)
    return {
        'season_code': spec.season_code,
        'season_type': spec.season_type,
        'seasons_for_plc': spec.seasons_for_plc,
        'fwo_range': list(spec.fwo_range),
        'sale_col': spec.sale_col,
    }


def main():
    parser = argparse.ArgumentParser(
        description="자기 브랜드 GT CSV 로 표준 PLC 곡선 생성",
    )
    parser.add_argument(
        '--from-csv',
        help='GT CSV 경로 직접 지정 (미지정 시 data/{BRAND}_GT_*.csv 자동 탐색)',
    )
    parser.add_argument(
        '--out',
        help='출력 csv 경로 (기본: config_loader.get_plc_forecast_path())',
    )
    args = parser.parse_args()

    # 1. 환경 + brand_config
    brand = get_brand()
    base_season = get_base_season()
    target_season = get_target_season()
    season_type = derive_season_type(target_season)

    print("=== Build PLC Standard ===")
    print(f"BRAND={brand}, baseSeason={base_season}, targetSeason={target_season}, type={season_type}")

    # 2. plc_engine_config 룩업
    season_cfg = _load_season_cfg(base_season, season_type)
    seasons_for_plc = season_cfg['seasons_for_plc']
    fwo_range = tuple(season_cfg['fwo_range'])
    sale_col = season_cfg['sale_col']

    if season_cfg.get('season_type') and season_cfg['season_type'] != season_type:
        raise RuntimeError(
            f"season_type 불일치: targetSeason='{target_season}' → '{season_type}', "
            f"plc_engine_config['{base_season}'].season_type='{season_cfg['season_type']}'.\n"
            f"  config 의 season_type 을 '{season_type}' 으로 맞추세요."
        )

    # 3. BrandSpec + item_nm_map
    brand_spec = BrandSpec.from_json(PLC_ENGINE_CONFIG_PATH, brand.lower())
    try:
        item_nm_map = brand_spec.load_item_nm_map()
    except FileNotFoundError:
        print(f"[INFO] item_nm_map_path 파일 없음 ({brand_spec.item_nm_map_path}) — ITEM 원본 코드 사용")
        item_nm_map = {}

    # 4. SeasonSpec (specs.py::fw_order 사용 — FW/SS 분기는 specs.py 안에서)
    season_spec = SeasonSpec(
        season_code=base_season,
        season_type=season_type,
        seasons_for_plc=seasons_for_plc,
        fwo_range=fwo_range,
        sale_col=sale_col,
    )

    # 5. 데이터 소스 결정 (CSV 우선, 실패 시 Snowflake fallback)
    df_raw = None
    if args.from_csv:
        if not os.path.exists(args.from_csv):
            raise FileNotFoundError(f"--from-csv 경로 없음: {args.from_csv}")
        print(f"GT CSV (지정): {args.from_csv}")
        df_raw = pd.read_csv(args.from_csv)
    else:
        try:
            csv_path = find_gt_csv(brand, seasons_for_plc)
            print(f"GT CSV (자동탐색): {csv_path}")
            df_raw = pd.read_csv(csv_path)
        except FileNotFoundError as e:
            print(f"[INFO] GT CSV 미발견 → Snowflake fallback 시도")
            print(f"  사유: {e}")
            df_raw = query_snowflake_for_plc(brand, seasons_for_plc)

    # 6. 학습 파이프라인
    weekly = prepare_weekly(
        df_raw, seasons_for_plc, brand_spec.plc_exclude_prods, item_nm_map,
        fwo_range, sale_col, season_spec.fw_order,
    )
    check_sufficiency(weekly, seasons_for_plc)
    forecast = calc_plc(weekly)

    # 7. Drift 비교 (기존 csv 있을 때만 — save 전에 로드)
    out_path = args.out or get_plc_forecast_path()
    has_old = os.path.exists(out_path)
    drift = None
    if has_old:
        old_df = pd.read_csv(out_path, encoding='utf-8-sig')
        new_for_drift = forecast[forecast['FORECAST_INDEX'].notna()][['ITEM', 'WEEK_NUM', 'PLC_RATIO']].copy()
        drift = compute_drift(old_df, new_for_drift)

    # 8. 출력 + Drift report
    save_csv(forecast, out_path)
    print_drift_report(drift or {}, has_old)
    if drift and drift['mape_pct'] > 30:
        detail_path = save_drift_detail_csv(
            drift['merged_df'], os.path.dirname(out_path), brand, season_type,
        )
        print(f"\n상세 비교: {detail_path}")
    print_coverage(weekly, forecast, seasons_for_plc)
    print("\n=== Done ===")


if __name__ == '__main__':
    main()
