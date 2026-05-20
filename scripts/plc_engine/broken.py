"""PLC 엔진 — 상업적 결품 감지."""

from __future__ import annotations

from typing import Optional

from .specs import BrokenPoint


def detect_commercial_stockout(
    cdf,
    threshold: int,
    min_sale_weeks: int,
    rst_num_sizes: dict,
    prod_cd: str,
    color: str,
) -> Optional[BrokenPoint]:
    """상업적 결품 감지 (복원 NUM_SIZES + 임계값).

    Args:
        cdf: SC DataFrame (BOW_STOCK, NUM_SIZES, CUM_INTAKE, CUM_SALE, WEEK_OF_YEAR 포함, reindexed)
        threshold: 사이즈당 평균재고 임계값
        min_sale_weeks: 입고 후 최소 경과 주수
        rst_num_sizes: {(prod_cd, color, week) -> num_sizes} 복원 사이즈 수 lookup
        prod_cd: 스타일 코드
        color: 컬러 코드

    Returns:
        BrokenPoint or None
    """
    # 복원 NUM_SIZES 적용
    rst_ns = cdf['WEEK_OF_YEAR'].map(lambda w: rst_num_sizes.get((prod_cd, color, int(w))))
    num_sizes_rst = rst_ns.fillna(cdf['NUM_SIZES']).astype(int)
    avg_size_stock_rst = cdf['BOW_STOCK'] / num_sizes_rst.clip(lower=1)

    # 브로큰 판정
    has_intake = cdf['CUM_INTAKE'] > 0
    has_sale = cdf['CUM_SALE'] > 0
    eligible = cdf[has_intake & has_sale]
    first_intake_pos = eligible.index[0] if len(eligible) > 0 else None
    if first_intake_pos is not None:
        eligible = eligible[eligible.index >= first_intake_pos + min_sale_weeks]

    # BOW_STOCK=0인 주차는 "데이터 없음"(GT 범위 밖 reindexed)으로 간주, 결품 판정 제외
    has_stock_data = cdf['BOW_STOCK'] > 0
    broken = eligible[
        (avg_size_stock_rst.reindex(eligible.index) < threshold) &
        (has_stock_data.reindex(eligible.index))
    ]
    if len(broken) == 0:
        return None

    broken_week = int(broken['WEEK_OF_YEAR'].iloc[0])
    broken_pos = broken.index[0]
    avg_stock_val = float(avg_size_stock_rst.loc[broken_pos])
    return BrokenPoint(week=broken_week, pos=broken_pos, avg_size_stock=avg_stock_val)


def compute_broken_series(
    cdf,
    threshold: int,
    rst_num_sizes: dict,
    prod_cd: str,
    color: str,
) -> list[bool]:
    """주차별 결품 상태 bool 배열 반환 (cdf 전체 주차 순서).

    True: 해당 주차에 사이즈당 평균재고 < threshold 이고 재고 데이터 있음 (실결품)
    False: 그 외 (정상 재고 또는 데이터 없음)
    """
    rst_ns = cdf['WEEK_OF_YEAR'].map(lambda w: rst_num_sizes.get((prod_cd, color, int(w))))
    num_sizes_rst = rst_ns.fillna(cdf['NUM_SIZES']).astype(int)
    avg_size_stock_rst = cdf['BOW_STOCK'] / num_sizes_rst.clip(lower=1)
    has_stock_data = cdf['BOW_STOCK'] > 0
    series = (avg_size_stock_rst < threshold) & has_stock_data
    return [bool(x) for x in series.tolist()]
