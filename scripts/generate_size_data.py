"""
STEP 5: 사이즈 배분 데이터 생성
- fw_size_data.xlsx 실데이터 기반
- 컬러레인지 그룹 매핑 (FNF_GROUP_COLOR_*.xlsx)
- 계층: SEX_NM > CLASS2 > CAT_NM > SUB_CAT_NM > COLOR_RANGE > SIZE_CD
- 당해/전년 분리 → JSON 출력
"""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config_loader

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'public', 'size_assortment_data.json'
)

HIERARCHY = ['SEX_NM', 'CLASS2', 'CAT_NM', 'SUB_CAT_NM', 'ITEM', 'ITEM_NM', 'SESN_SUB_NM', 'FIT_INFO1']
SIZE_ORDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL', '2XL']

# 카테고리 사이즈 분포 폴백 체인 (docs/STEP5_사이즈배분_운영가이드.md §8.2)
# L1: 가장 정밀 (FIT 포함) — FIT_INFO1 Null이면 키 제외
# L5: 최후 폴백 (CLASS2만)
CATEGORY_DIST_LEVELS = [
    ('by_l1', ['SEX_NM', 'CLASS2', 'ITEM', 'SESN_SUB_NM', 'FIT_INFO1']),
    ('by_l2', ['SEX_NM', 'CLASS2', 'ITEM', 'SESN_SUB_NM']),
    ('by_l3', ['SEX_NM', 'CLASS2', 'ITEM']),
    ('by_l4', ['SEX_NM', 'CLASS2']),
    ('by_l5', ['CLASS2']),
]

# 브랜드별 사이즈 체계가 달라서 하드코딩 불가 — 데이터 기반 자동 정렬
_SIZE_LETTER_ORDER = {'XS': 0, 'S': 1, 'M': 2, 'L': 3, 'XL': 4, 'XXL': 5, '2XL': 5, '3XL': 6}

def _size_sort_key(s):
    """숫자 사이즈(85/90/95...)는 숫자순, 영문(XS/S/M/L)은 표준 순."""
    s = str(s)
    if s.isdigit():
        return (0, int(s), '')
    return (1, _SIZE_LETTER_ORDER.get(s, 99), s)

# 실데이터 없을 때 폴백용 의류 샘플
SAMPLE_SALES = [
    {"SEX_NM": "공용", "CLASS2": "Outer", "CAT_NM": "패딩", "SUB_CAT_NM": "숏패딩", "ITEM": "PD", "ITEM_NM": "패딩",
     "SESN_SUB_NM": "Winter", "FIT_INFO1": "Regular",
     "COLOR_RANGE": "BLACK", "SIZE_CD": "M", "ORDER_QTY": 1200, "SALE_QTY": 890, "period": "당해"},
    {"SEX_NM": "공용", "CLASS2": "Outer", "CAT_NM": "패딩", "SUB_CAT_NM": "숏패딩", "ITEM": "PD", "ITEM_NM": "패딩",
     "SESN_SUB_NM": "Winter", "FIT_INFO1": "Regular",
     "COLOR_RANGE": "BLACK", "SIZE_CD": "L", "ORDER_QTY": 1500, "SALE_QTY": 1100, "period": "당해"},
    {"SEX_NM": "공용", "CLASS2": "Outer", "CAT_NM": "패딩", "SUB_CAT_NM": "숏패딩", "ITEM": "PD", "ITEM_NM": "패딩",
     "SESN_SUB_NM": "Winter", "FIT_INFO1": "Regular",
     "COLOR_RANGE": "WHITE", "SIZE_CD": "M", "ORDER_QTY": 800, "SALE_QTY": 550, "period": "당해"},
    {"SEX_NM": "공용", "CLASS2": "Inner", "CAT_NM": "맨투맨", "SUB_CAT_NM": "맨투맨", "ITEM": "MT", "ITEM_NM": "맨투맨",
     "SESN_SUB_NM": "Fall", "FIT_INFO1": "Over",
     "COLOR_RANGE": "GRAY", "SIZE_CD": "M", "ORDER_QTY": 800, "SALE_QTY": 600, "period": "당해"},
    {"SEX_NM": "공용", "CLASS2": "Inner", "CAT_NM": "맨투맨", "SUB_CAT_NM": "맨투맨", "ITEM": "MT", "ITEM_NM": "맨투맨",
     "SESN_SUB_NM": "Fall", "FIT_INFO1": "Over",
     "COLOR_RANGE": "GRAY", "SIZE_CD": "L", "ORDER_QTY": 900, "SALE_QTY": 700, "period": "당해"},
]

SAMPLE_PREV = [
    {"SEX_NM": "공용", "CLASS2": "Outer", "CAT_NM": "패딩", "SUB_CAT_NM": "숏패딩", "ITEM": "PD", "ITEM_NM": "패딩",
     "SESN_SUB_NM": "Winter", "FIT_INFO1": "Regular",
     "COLOR_RANGE": "BLACK", "SIZE_CD": "M", "ORDER_QTY": 1100, "SALE_QTY": 800, "period": "전년"},
    {"SEX_NM": "공용", "CLASS2": "Outer", "CAT_NM": "패딩", "SUB_CAT_NM": "숏패딩", "ITEM": "PD", "ITEM_NM": "패딩",
     "SESN_SUB_NM": "Winter", "FIT_INFO1": "Regular",
     "COLOR_RANGE": "BLACK", "SIZE_CD": "L", "ORDER_QTY": 1400, "SALE_QTY": 1000, "period": "전년"},
    {"SEX_NM": "공용", "CLASS2": "Outer", "CAT_NM": "패딩", "SUB_CAT_NM": "숏패딩", "ITEM": "PD", "ITEM_NM": "패딩",
     "SESN_SUB_NM": "Winter", "FIT_INFO1": "Regular",
     "COLOR_RANGE": "WHITE", "SIZE_CD": "M", "ORDER_QTY": 700, "SALE_QTY": 480, "period": "전년"},
]

SAMPLE_MAPPING = [
    {"컬러코드": "BKS", "컬러명": "블랙", "COLOR_RANGE": "BLACK"},
    {"컬러코드": "WHM", "컬러명": "화이트 멜란지", "COLOR_RANGE": "WHITE"},
    {"컬러코드": "DGD", "컬러명": "다크 그레이3", "COLOR_RANGE": "GRAY"},
]


def _load_color_mapping():
    """컬러레인지 그룹 매핑 로드: 상세코드(3자리) → 최종(그룹) — JSON 기반"""
    color_map = config_loader.get_color_mapping()
    if not color_map:
        print(f"  ! 컬러 매핑 없음")
        return {}, []

    # mapping_data: 프론트엔드용 컬러 매핑 리스트
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'public', 'color_mapping.json'
    )
    mapping_data = []
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # color_to_group에서 컬러명 정보 추출
        ctg = data.get('color_to_group', {})
        for code, final in color_map.items():
            mapping_data.append({
                '컬러코드': code,
                '컬러명': ctg.get(code, final),
                'COLOR_RANGE': final,
            })

    print(f"  * 컬러 매핑 로드: {len(color_map)}개 코드 → {len(set(color_map.values()))}개 그룹")
    return color_map, mapping_data


def _aggregate(df):
    """계층+컬러레인지+사이즈별 집계 후 판매 0 제거"""
    group_cols = HIERARCHY + ['COLOR_RANGE', 'SIZE_CD']
    agg = df.groupby(group_cols, as_index=False, dropna=False).agg(
        ORDER_QTY=('ORDER_QTY_KR', 'sum'),
        SALE_QTY=('SALE_QTY_KR', 'sum'),
    )
    agg = agg[agg['SALE_QTY'] > 0].copy()
    return agg


def _build_ref_meta(df):
    """PART_CD → {SESN_SUB_NM, FIT_INFO1} 메타 매핑 (정책 3 ref 폴백용).

    각 PART_CD가 갖는 메타 정보를 lookup용으로 추출.
    동일 PART_CD에 여러 행이 있으면 첫 번째 값 사용 (보통 일관됨).
    """
    if 'PART_CD' not in df.columns:
        return {}
    cols = ['PART_CD', 'SESN_SUB_NM', 'FIT_INFO1']
    avail = [c for c in cols if c in df.columns]
    if 'PART_CD' not in avail:
        return {}
    meta_df = df[avail].drop_duplicates('PART_CD')
    ref_meta = {}
    for _, row in meta_df.iterrows():
        pc = row.get('PART_CD')
        if not pc or pd.isna(pc):
            continue
        entry = {}
        if 'SESN_SUB_NM' in avail:
            v = row.get('SESN_SUB_NM')
            entry['SESN_SUB_NM'] = None if pd.isna(v) else str(v)
        if 'FIT_INFO1' in avail:
            v = row.get('FIT_INFO1')
            entry['FIT_INFO1'] = None if pd.isna(v) else str(v)
        ref_meta[str(pc)] = entry
    return ref_meta


def _compute_category_size_dist(df):
    """L1~L5 단위 사이즈 비중 + SC 카운트 사전 집계 (정책 3 빈자리 채우기용).

    Returns:
        (dist, counts): 각 Level별 그룹 라벨 → 사이즈 비중 dict / SC 카운트
        - Null 키 그룹은 제외 (FIT_INFO1 Null 처리 — §8.3)
        - 비중은 4자리 소수 (round 0.0000)
    """
    dist = {}
    counts = {}

    # SC 카운트용 unique 추출 (PART_CD 기준)
    sc_key_cols = list({c for _, keys in CATEGORY_DIST_LEVELS for c in keys} | {'PART_CD'})
    sc_df = df[sc_key_cols].drop_duplicates()

    for level_key, group_keys in CATEGORY_DIST_LEVELS:
        # ── 사이즈 비중 ──────────────────────────────
        size_agg = df.groupby(group_keys + ['SIZE_CD'], dropna=False, as_index=False)['SALE_QTY_KR'].sum()
        size_agg = size_agg[size_agg['SALE_QTY_KR'] > 0]

        level_dist = {}
        for group_vals, sub in size_agg.groupby(group_keys, dropna=False):
            vals = group_vals if isinstance(group_vals, tuple) else (group_vals,)
            if any(pd.isna(v) for v in vals):
                continue  # Null 키 그룹 제외
            group_label = '|'.join(str(v) for v in vals)
            total = sub['SALE_QTY_KR'].sum()
            if total > 0:
                level_dist[group_label] = {
                    str(row['SIZE_CD']): round(float(row['SALE_QTY_KR'] / total), 4)
                    for _, row in sub.iterrows()
                }

        # ── SC 카운트 ────────────────────────────────
        sc_counts = sc_df.groupby(group_keys, dropna=False).size()
        level_counts = {}
        for group_vals, cnt in sc_counts.items():
            vals = group_vals if isinstance(group_vals, tuple) else (group_vals,)
            if any(pd.isna(v) for v in vals):
                continue
            group_label = '|'.join(str(v) for v in vals)
            level_counts[group_label] = int(cnt)

        dist[level_key] = level_dist
        counts[level_key] = level_counts

    return dist, counts


def main():
    print("=" * 60)
    print("Step 5: 사이즈 배분 데이터 생성")
    print("=" * 60)

    base_season = config_loader.get_base_season()

    # 데이터 로드 (Snowflake 3-tier → xlsx 폴백 → 샘플 폴백)
    df = None
    try:
        from config_loader import load_data as _load_data
        df = _load_data("d4")
        print(f"  * 데이터 로드 완료: {len(df)}행")
    except Exception as e:
        print(f"  ! 데이터 로드 실패: {e}")
        data_path = config_loader.get_size_data_path()
        if os.path.exists(data_path):
            print(f"    → xlsx 폴백: {data_path}")
            df = pd.read_excel(data_path, sheet_name='Result 1')

    if df is None or df.empty:
        print("  → 샘플 데이터로 폴백")
        output = {
            "salesData": SAMPLE_SALES,
            "prevData": SAMPLE_PREV,
            "colorMapping": SAMPLE_MAPPING,
            "meta": {
                "sizeOrder": SIZE_ORDER,
                "baseSeason": base_season,
                "hierarchy": HIERARCHY,
            },
            "category_size_dist": {lk: {} for lk, _ in CATEGORY_DIST_LEVELS},
            "category_sample_count": {lk: {} for lk, _ in CATEGORY_DIST_LEVELS},
            "ref_meta": {},
        }
    else:

        # 첫 컬럼 → period (따옴표 포함 컬럼명 처리)
        df.rename(columns={df.columns[0]: 'period'}, inplace=True)
        print(f"  * 전체 행수: {len(df)}")

        # 컬러레인지 매핑
        color_map, mapping_data = _load_color_mapping()
        if color_map:
            df['COLOR_RANGE'] = df['COLOR_CD'].str[-3:].map(color_map)
            unmatched = df['COLOR_RANGE'].isna().sum()
            if unmatched > 0:
                print(f"  ! 컬러 매핑 실패: {unmatched}행 → 'UNKNOWN' 처리")
                df['COLOR_RANGE'] = df['COLOR_RANGE'].fillna('UNKNOWN')
        else:
            df['COLOR_RANGE'] = 'UNKNOWN'
            mapping_data = []

        # 당해/전년 분리
        df_current = df[df['period'] == '당해'].copy()
        df_prev = df[df['period'] == '전년'].copy()
        print(f"  * 당해: {len(df_current)}행, 전년: {len(df_prev)}행")

        # 계층별 집계
        agg_current = _aggregate(df_current)
        agg_current['period'] = '당해'

        agg_prev = _aggregate(df_prev)
        agg_prev['period'] = '전년'

        print(f"  * 집계 후 — 당해: {len(agg_current)}행, 전년: {len(agg_prev)}행")

        # 실제 존재하는 사이즈 전체 포함 + 데이터 기반 정렬 (숫자순, 영문순)
        all_sizes = set(agg_current['SIZE_CD'].unique()) | set(agg_prev['SIZE_CD'].unique())
        size_order = sorted(all_sizes, key=_size_sort_key)

        # 카테고리 분포 사전 집계 (정책 3 빈자리 채우기용 — 당해+전년 통합)
        cat_dist, cat_counts = _compute_category_size_dist(df)

        # ref_meta: PART_CD → {SESN_SUB_NM, FIT_INFO1} (ref 폴백용)
        ref_meta = _build_ref_meta(df)

        # NaN → None 변환 (표준 JSON 호환 — JavaScript JSON.parse 호환)
        # astype(object)로 dtype 통일 후 None 대체 (float dtype에선 None이 NaN으로 되돌아감)
        agg_current = agg_current.astype(object).where(pd.notna(agg_current), None)
        agg_prev = agg_prev.astype(object).where(pd.notna(agg_prev), None)

        output = {
            "salesData": agg_current.to_dict(orient='records'),
            "prevData": agg_prev.to_dict(orient='records'),
            "colorMapping": mapping_data,
            "meta": {
                "sizeOrder": size_order,
                "baseSeason": base_season,
                "hierarchy": HIERARCHY,
            },
            "category_size_dist": cat_dist,
            "category_sample_count": cat_counts,
            "ref_meta": ref_meta,
        }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        # allow_nan=False — 표준 JSON 강제. NaN/Inf 발견 시 ValueError로 즉시 인지
        json.dump(output, f, ensure_ascii=False, indent=2, allow_nan=False)

    print(f"  * salesData: {len(output['salesData'])}건")
    print(f"  * prevData: {len(output['prevData'])}건")
    print(f"  * colorMapping: {len(output.get('colorMapping', []))}건")
    print(f"  * sizeOrder: {output['meta']['sizeOrder']}")
    print(f"  * categoryDist:")
    for lk, _ in CATEGORY_DIST_LEVELS:
        n_groups = len(output.get('category_size_dist', {}).get(lk, {}))
        print(f"      {lk}: {n_groups}그룹")
    print(f"  * 저장 완료: {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
