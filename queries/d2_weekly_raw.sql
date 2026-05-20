-- d2_weekly_raw.sql
-- 주차별실적: 스타일×컬러별 주차 단위 입고/판매/재고 시계열
--
-- 파라미터: {brand}, {base_season}, {prev_season}, {prev2_season}
--   brand: 브랜드코드 (M=MLB, X=Discovery 등)
--   base_season: 당해 시즌 (예: 25F) ← config_loader.get_base_season()
--   prev_season: 전년 시즌 (예: 24F) ← config_loader.get_prev_season()
--   prev2_season: 재작년 시즌 (예: 23F) ← config_loader.get_prev2_season()
--
-- 테이블:
--   FNF.PRCS.DB_SCS_W  — 주차별 판매/재고 실적 (Weekly)
--   FNF.PRCS.DB_PRDT   — 상품 마스터
--
-- 사용처: weekly_analysis.py (Step 2), ai_sales_loss_v2.py (Step 3), generate_color_mapping.py
-- 예상 행수: 15,000~200,000 (3개 시즌)
-- 캐시: data/{brand}/{season}/weekly_raw.csv
--
-- 3시즌 조회: 당해 + 전년 + 재작년 (D1과 동일 패턴)
-- PERIOD 컬럼으로 시즌 구분: '당해' / '전년' / '재작년'
--
-- 코드 적용 필터 (쿼리 후 Python에서 처리):
--   PERIOD == '당해' → 당해 시즌만 (weekly_analysis.py, ai_sales_loss_v2.py)
--   CLASS1 contains '의류' → 용품/신발 제외
--   STOR_QTY_KR > 0 (스타일 단위 합산) → 입고 실적 없는 품번 제외
--   EXCLUDE_STYLES 하드코딩 아웃라이어 제거

SELECT
    CASE w.SESN
        WHEN '{base_season}' THEN '당해'
        WHEN '{prev_season}' THEN '전년'
        WHEN '{prev2_season}' THEN '재작년'
    END                                                        AS PERIOD,
    w.END_DT,
    p.PARENT_PRDT_KIND_NM                                      AS CLASS1,
    p.PRDT_KIND_NM                                             AS CLASS2,
    p.ITEM,
    p.ITEM_NM,
    p.PRDT_NM,
    w.PART_CD,
    w.COLOR_CD,
    p.TAG_PRICE,
    SUM(w.ORD_QTY)                                             AS ORDER_QTY,
    SUM(w.ORD_QTY_KOR)                                         AS ORDER_QTY_KR,
    SUM(w.STOR_QTY_KOR)                                        AS STOR_QTY_KR,
    SUM(w.SALE_NML_QTY_CNS + w.SALE_RET_QTY_CNS)              AS SALE_QTY_CNS,
    SUM(w.SALE_NML_QTY_CHN + w.SALE_NML_QTY_GVL)              AS SALE_QTY_GLB,
    SUM(w.DELV_NML_QTY_WSL + w.DELV_RET_QTY_WSL)              AS WH_QTY,
    -- 재고: 누적 기준 (해당 주차 말 기준 재고)
    SUM(w.AC_STOR_QTY_KOR)
        - SUM(w.AC_SALE_NML_QTY_CNS + w.AC_SALE_RET_QTY_CNS)
        - SUM(w.AC_DELV_NML_QTY_WSL + w.AC_DELV_RET_QTY_WSL)  AS STOCK_QTY_KR
FROM FNF.PRCS.DB_SCS_W w
    LEFT JOIN FNF.PRCS.DB_PRDT p ON w.PART_CD = p.PART_CD
WHERE w.BRD_CD = '{brand}'
  AND (
    (w.SESN = '{base_season}'  AND w.END_DT <= DATE '{base_end_date_buffered}') OR
    (w.SESN = '{prev_season}'  AND w.END_DT <= DATE '{prev_end_date_buffered}') OR
    (w.SESN = '{prev2_season}' AND w.END_DT <= DATE '{prev2_end_date_buffered}')
  )
GROUP BY
    w.SESN,
    w.END_DT,
    p.PARENT_PRDT_KIND_NM,
    p.PRDT_KIND_NM,
    p.ITEM,
    p.ITEM_NM,
    p.PRDT_NM,
    w.PART_CD,
    w.COLOR_CD,
    p.TAG_PRICE
ORDER BY
    PERIOD,
    w.END_DT,
    w.PART_CD,
    w.COLOR_CD
