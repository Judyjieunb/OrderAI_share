"""PLC 엔진 — DTW/PLC 빌더 함수."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .specs import EngineParams


def dtw_distance(s, t, window=2):
    """Sakoe-Chiba 밴드 제약 DTW 거리."""
    n, m = len(s), len(t)
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(max(1, i - window), min(m + 1, i + window + 1)):
            d = (s[i - 1] - t[j - 1]) ** 2
            cost[i, j] = d + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
    return np.sqrt(cost[n, m])


def build_sell_through_plc(df_all, sale_col, seasons, exclude_prods,
                           fwo_range, fw_order_fn, min_cum_intake, min_sc_for_plc):
    """아이템별 주차별 평균 판매율 PLC 산출 (단조증가).

    Args:
        df_all: 전체 GT/복원 DataFrame (SSN_CD, PROD_CD, COLOR_CD, ITEM, WEEK_OF_YEAR, CUM_INTAKE 포함)
        sale_col: 판매 컬럼명 (e.g. 'ADJ_SC_SALE_QTY_TAX')
        seasons: PLC 산출 대상 시즌 리스트
        exclude_prods: PLC 산출 제외 PROD_CD 리스트
        fwo_range: (min_fwo, max_fwo) 튜플
        fw_order_fn: WEEK_OF_YEAR → FW_ORDER 변환 함수
        min_cum_intake: 판매율 계산 시 최소 누적입고량
        min_sc_for_plc: PLC 산출 최소 SC 수

    Returns:
        dict: {item: ndarray of sell-through values indexed by fwo_range}
    """
    df = df_all[df_all['SSN_CD'].isin(seasons)].copy()
    if exclude_prods:
        df = df[~df['PROD_CD'].isin(exclude_prods)]
    df['FW_ORDER'] = df['WEEK_OF_YEAR'].apply(fw_order_fn)
    df = df[(df['FW_ORDER'] >= fwo_range[0]) & (df['FW_ORDER'] <= fwo_range[1])]

    records = []
    for (ssn, prod, color), grp in df.groupby(['SSN_CD', 'PROD_CD', 'COLOR_CD']):
        grp = grp.sort_values('FW_ORDER')
        item = grp['ITEM'].iloc[0]
        cum_sale = grp[sale_col].cumsum().values
        cum_intake = grp['CUM_INTAKE'].values
        prev_str = 0.0
        for i, (_, r) in enumerate(grp.iterrows()):
            ci = cum_intake[i]
            if ci < min_cum_intake:
                continue
            str_val = max(cum_sale[i] / ci, prev_str)
            prev_str = str_val
            records.append({'ITEM': item, 'FW_ORDER': int(r['FW_ORDER']), 'SELL_THROUGH': str_val})

    if not records:
        return {}
    str_df = pd.DataFrame(records)
    avg = str_df.groupby(['ITEM', 'FW_ORDER'])['SELL_THROUGH'].agg(['mean', 'count']).reset_index()

    result = {}
    fwo_full = range(fwo_range[0], fwo_range[1] + 1)
    for item in avg['ITEM'].unique():
        item_df = avg[avg['ITEM'] == item]
        if item_df['count'].max() < min_sc_for_plc:
            continue
        item_df = item_df.set_index('FW_ORDER')
        vals = [float(item_df.loc[f, 'mean']) if f in item_df.index else np.nan for f in fwo_full]
        arr = pd.Series(vals).interpolate(limit_direction='both').fillna(0).values.copy()
        for i in range(1, len(arr)):
            arr[i] = max(arr[i], arr[i - 1])
        result[item] = arr
    return result


def build_sc_sell_through(cdf, broken_pos, min_cum_intake):
    """SC별 판매율 곡선 (시즌 시작 ~ 브로큰 전, 단조증가)."""
    if broken_pos is None:
        return []
    curve, prev_str = [], 0.0
    for _, r in cdf[cdf.index < broken_pos].iterrows():
        ci = int(r['CUM_INTAKE'])
        if ci < min_cum_intake:
            continue
        str_val = max(int(r['CUM_SALE']) / ci, prev_str)
        prev_str = str_val
        curve.append(str_val)
    return curve


def find_plc_position(sc_curve, plc_curve, actual_broken_fwo, params: EngineParams):
    """DTW 슬라이딩 매칭 → (matched_end_fwo, shift, dist)."""
    W = len(sc_curve)
    if W < params.dtw_min_window:
        return None, 0, float('inf')

    sc_arr = np.array(sc_curve, dtype=float)
    plc_arr = np.array(plc_curve, dtype=float)
    if np.std(sc_arr) < 0.01:
        return None, 0, float('inf')

    actual_start = actual_broken_fwo - W
    lo = max(0, actual_start - params.dtw_shift_high)
    hi = min(len(plc_arr) - W + 1, actual_start + params.dtw_shift_high + 1)

    best_dist, best_start = float('inf'), None
    for s in range(lo, hi):
        seg = plc_arr[s: s + W]
        if np.any(np.isnan(seg)):
            continue
        d = dtw_distance(sc_arr, seg, window=params.dtw_warp_band)
        if d < best_dist:
            best_dist, best_start = d, s

    if best_start is None:
        return None, 0, float('inf')
    matched_end = best_start + W
    return matched_end, matched_end - actual_broken_fwo, best_dist


def dtw_confidence(dist, shift, params: EngineParams):
    """DTW 거리 + 시프트 → 신뢰도 + 보정된 시프트."""
    conf = 'High' if dist < params.dtw_dist_high else ('Medium' if dist < params.dtw_dist_medium else 'Low')
    if conf == 'High' and abs(shift) == params.dtw_shift_high:
        conf = 'Low'
    if conf == 'Low':
        shift = 0
    elif conf == 'Medium':
        shift = int(np.clip(shift, -params.dtw_shift_medium, params.dtw_shift_medium))
    return conf, shift


def asymmetric_smooth(arr, bp_idx):
    """브로큰 이후 구간 3주 centered MA 스무딩 (브로큰 전 원본 유지)."""
    smooth_start = max(0, bp_idx - 1)
    smoothed = arr[:smooth_start]
    post = arr[smooth_start:]
    for i in range(len(post)):
        vals = []
        if i - 1 >= 0:
            vals.append(post[i - 1])
        vals.append(post[i])
        if i + 1 < len(post):
            vals.append(post[i + 1])
        smoothed.append(round(sum(vals) / len(vals), 1))
    return smoothed
