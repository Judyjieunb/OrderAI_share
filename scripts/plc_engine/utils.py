"""PLC 엔진 유틸리티 함수."""

from __future__ import annotations

import numpy as np
import pandas as pd


def remove_outliers(vals, ratio=5.0):
    """동일 주차 시즌간 이상치 제거 — ratio배 이상 편차 시 해당 값 제외"""
    if len(vals) <= 1:
        return vals
    filtered = []
    for v in vals:
        others = [x for x in vals if x != v]
        if len(others) == 0:
            filtered.append(v)
            continue
        om = np.median(others)
        if om > 0 and (v / om > ratio or (v > 0 and om / v > ratio)):
            continue
        filtered.append(v)
    return filtered if filtered else list(vals)


def get_plc_ratio_decayed_factory(plc_ratio_df, tail_decay=0.7):
    """PLC_RATIO lookup 클로저. 범위 밖이면 지수감쇠."""
    plc_ratio = {}
    plc_item_max_fwo = {}
    plc_item_last_ratio = {}
    for _, r in plc_ratio_df.iterrows():
        if pd.notna(r['PLC_RATIO']):
            plc_ratio[(r['ITEM'], int(r['WEEK_NUM']))] = r['PLC_RATIO']
            fwo = int(r['FW_ORDER'])
            if fwo > plc_item_max_fwo.get(r['ITEM'], -1):
                plc_item_max_fwo[r['ITEM']] = fwo
                plc_item_last_ratio[r['ITEM']] = r['PLC_RATIO']

    def get_plc_ratio_decayed(item, wk):
        r = plc_ratio.get((item, wk))
        if r is not None:
            return r
        max_fwo = plc_item_max_fwo.get(item)
        last_r = plc_item_last_ratio.get(item)
        if max_fwo is None or last_r is None:
            return None
        cur_fwo = wk - 22 if wk >= 23 else wk + 30
        if cur_fwo <= max_fwo:
            return None
        return last_r * (tail_decay ** (cur_fwo - max_fwo))

    return get_plc_ratio_decayed
