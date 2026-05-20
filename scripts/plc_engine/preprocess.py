"""PLC 엔진 — 데이터 전처리."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class SFLookups:
    """Snowflake weekly_raw에서 추출한 lookup 딕셔너리 5종."""
    sales: dict        # (part_cd, color, week) -> sale_qty
    cum_intake: dict   # (part_cd, color, week) -> cum_intake
    cum_sale: dict     # (part_cd, color, week) -> cum_sale
    kpi_dict: dict     # (part_cd, color) -> {order, intake, sale}
    weekly_intake: dict  # (part_cd, color, week) -> intake_qty


def build_sf_lookups(weekly_df) -> SFLookups:
    """weekly_raw에서 PERIOD=='당해' 필터 후 SF lookup 5종 생성.

    Args:
        weekly_df: weekly_raw DataFrame (PERIOD, END_DT, PART_CD, COLOR_CD,
                   SALE_QTY_CNS, STOR_QTY_KR, ORDER_QTY_KR 포함)

    Returns:
        SFLookups
    """
    wr = weekly_df[weekly_df['PERIOD'] == '당해'].copy()
    wr['END_DT'] = pd.to_datetime(wr['END_DT'])
    wr['WEEK_OF_YEAR'] = wr['END_DT'].dt.isocalendar().week.astype(int)

    # 1. sf_sales
    sales = {}
    for _, r in wr.groupby(['PART_CD', 'COLOR_CD', 'WEEK_OF_YEAR'])['SALE_QTY_CNS'].sum().reset_index().iterrows():
        sales[(r['PART_CD'], r['COLOR_CD'], int(r['WEEK_OF_YEAR']))] = int(r['SALE_QTY_CNS'])

    # 2. sf_cum_intake, sf_cum_sale
    cum_intake = {}
    cum_sale = {}
    wr_sorted = wr.sort_values(['PART_CD', 'COLOR_CD', 'END_DT']).copy()
    wr_sorted['cum_intake'] = wr_sorted.groupby(['PART_CD', 'COLOR_CD'])['STOR_QTY_KR'].cumsum()
    wr_sorted['cum_sale'] = wr_sorted.groupby(['PART_CD', 'COLOR_CD'])['SALE_QTY_CNS'].cumsum()
    for _, r in wr_sorted.iterrows():
        key = (r['PART_CD'], r['COLOR_CD'], int(r['WEEK_OF_YEAR']))
        cum_intake[key] = int(r['cum_intake'])
        cum_sale[key] = int(r['cum_sale'])

    # 3. sf_kpi_dict
    sf_kpi = wr.groupby(['PART_CD', 'COLOR_CD']).agg(
        sf_order=('ORDER_QTY_KR', 'sum'),
        sf_intake=('STOR_QTY_KR', 'sum'),
        sf_sale=('SALE_QTY_CNS', 'sum'),
    ).reset_index()
    kpi_dict = {
        (r['PART_CD'], r['COLOR_CD']): {
            'order': int(r['sf_order']),
            'intake': int(r['sf_intake']),
            'sale': int(r['sf_sale']),
        }
        for _, r in sf_kpi.iterrows()
    }

    # 4. sf_weekly_intake
    weekly_intake = {}
    for _, r in wr.groupby(['PART_CD', 'COLOR_CD', 'WEEK_OF_YEAR'])['STOR_QTY_KR'].sum().reset_index().iterrows():
        weekly_intake[(r['PART_CD'], r['COLOR_CD'], int(r['WEEK_OF_YEAR']))] = int(r['STOR_QTY_KR'])

    return SFLookups(
        sales=sales,
        cum_intake=cum_intake,
        cum_sale=cum_sale,
        kpi_dict=kpi_dict,
        weekly_intake=weekly_intake,
    )


def build_sc_scale(gt_df, sf_kpi_dict, sale_col='SC_SALE_QTY_TAX'):
    """SC별 스케일업 비율 (SF 실판매 / GT 국내).

    Args:
        gt_df: GT DataFrame (현재 시즌, PROD_CD, COLOR_CD, sale_col 포함)
        sf_kpi_dict: {(part_cd, color) -> {sale: int, ...}}
        sale_col: GT 국내 판매 컬럼명

    Returns:
        dict: {(prod_cd, color) -> scale_ratio}
    """
    sc_scale = {}
    for (prod, color), grp in gt_df.groupby(['PROD_CD', 'COLOR_CD']):
        t_tax = grp[sale_col].sum()
        sf_total = sf_kpi_dict.get((prod, color), {}).get('sale', 0)
        sc_scale[(prod, color)] = sf_total / max(t_tax, 1) if t_tax > 0 else 1.0
    return sc_scale


def build_rst_num_sizes(restored_df):
    """복원 NUM_SIZES lookup 생성.

    Args:
        restored_df: 복원 DataFrame (PROD_CD, COLOR_CD, WEEK_OF_YEAR, NUM_SIZES 포함)
                     WEEK_OF_YEAR가 없으면 WEEK_START에서 파생

    Returns:
        dict: {(prod_cd, color, week) -> num_sizes}
    """
    df = restored_df.copy()
    if 'WEEK_OF_YEAR' not in df.columns:
        df['WEEK_START'] = pd.to_datetime(df['WEEK_START'])
        df['WEEK_OF_YEAR'] = df['WEEK_START'].dt.isocalendar().week.astype(int)

    rst_num_sizes = {}
    for _, r in df.iterrows():
        rst_num_sizes[(r['PROD_CD'], r['COLOR_CD'], int(r['WEEK_OF_YEAR']))] = int(r['NUM_SIZES'])
    return rst_num_sizes


def build_week_frame(gt_df, weekly_df):
    """GT + weekly_raw 8주 버퍼 union으로 전체 주차 프레임 생성.

    Args:
        gt_df: GT DataFrame (WEEK_OF_YEAR, WEEK_START 포함)
        weekly_df: weekly_raw DataFrame (END_DT 포함)

    Returns:
        tuple: (all_week_list, all_week_start) — 주차 번호 리스트, 주차 시작일 문자열 리스트
    """
    gt_weeks = gt_df[['WEEK_OF_YEAR', 'WEEK_START']].drop_duplicates()
    gt_weeks['WEEK_START'] = pd.to_datetime(gt_weeks['WEEK_START'])
    gt_min, gt_max = gt_weeks['WEEK_START'].min(), gt_weeks['WEEK_START'].max()

    wr = weekly_df[weekly_df['PERIOD'] == '당해'].copy()
    wr_weeks = wr[['END_DT']].drop_duplicates().copy()
    wr_weeks['WEEK_START'] = pd.to_datetime(wr_weeks['END_DT']) - pd.Timedelta(days=6)
    wr_weeks['WEEK_OF_YEAR'] = wr_weeks['WEEK_START'].dt.isocalendar().week.astype(int)
    wr_weeks = wr_weeks[
        (wr_weeks['WEEK_START'] >= gt_min - pd.Timedelta(days=56)) &
        (wr_weeks['WEEK_START'] <= gt_max + pd.Timedelta(days=56))
    ]

    all_weeks = pd.concat([
        gt_weeks[['WEEK_OF_YEAR', 'WEEK_START']],
        wr_weeks[['WEEK_OF_YEAR', 'WEEK_START']],
    ]).drop_duplicates(subset='WEEK_OF_YEAR').sort_values('WEEK_START').reset_index(drop=True)
    all_weeks['WEEK_START'] = all_weeks['WEEK_START'].dt.strftime('%Y-%m-%d')

    all_week_list = all_weeks['WEEK_OF_YEAR'].tolist()
    all_week_start = all_weeks['WEEK_START'].tolist()
    return all_week_list, all_week_start
