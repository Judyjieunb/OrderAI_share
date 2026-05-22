-- d4_size_data.sql
-- 사이즈별실적: 스타일×컬러×사이즈 단위 발주/입고/판매 집계
--
-- 파라미터: {brand}, {base_season}, {prev_season}
--   brand: 브랜드코드 (M=MLB 등)
--   base_season: 당해 시즌 (예: 25F) ← config_loader.get_base_season()
--   prev_season: 전년 시즌 (예: 24F) ← config_loader.get_prev_season()
--
-- 테이블:
--   FNF.PRCS.DB_SCS_W  — 주차별 판매/재고 실적 (Weekly)
--   FNF.PRCS.DB_PRDT   — 상품 마스터
--
-- 사용처: generate_size_data.py (Step 5)
-- 예상 행수: 5,000~15,000 (2 시즌 × 계층 × 사이즈)
-- 캐시: data/{brand}/{season}/size_data.csv
--
-- 2시즌(당해/전년) 조회 — Step 5는 당해/전년만 사용
--
-- SQL 적용 필터:
--   CLASS1 = '의류' → 용품/신발/ACC 제외 (사이즈 배분 분석 대상)
--
-- 코드 적용 필터 (쿼리 후 Python에서 처리):
--   SALE_QTY_KR > 0 → 판매 없는 행 제외 (_aggregate)
--   COLOR_CD → COLOR_RANGE 매핑 (public/color_mapping.json)
--   GROUP BY: SEX_NM, CLASS2, CAT_NM, SUB_CAT_NM, ITEM, ITEM_NM, COLOR_RANGE, SIZE_CD

SELECT
    CASE w.SESN
        WHEN '{base_season}' THEN '당해'
        WHEN '{prev_season}' THEN '전년'
    END                                                        AS PERIOD,
    w.BRD_CD,
    p.PARENT_PRDT_KIND_NM                                      AS CLASS1,
    p.PRDT_KIND_NM                                             AS CLASS2,
    p.SEX_NM,
    p.CAT_NM,
    p.SUB_CAT_NM,
    p.ITEM,
    p.ITEM_NM,
    p.FIT_INFO1,
    p.SESN_SUB_NM,
    w.PART_CD,
    w.COLOR_CD,
    w.SIZE_CD,
    SUM(w.ORD_QTY_KOR)                                         AS ORDER_QTY_KR,
    SUM(w.STOR_QTY_KOR)                                        AS STOR_QTY_KR,
    SUM(w.SALE_NML_QTY_CNS + w.SALE_RET_QTY_CNS)               AS SALE_QTY_KR
FROM FNF.PRCS.DB_SCS_W w
    LEFT JOIN FNF.PRCS.DB_PRDT p ON w.PART_CD = p.PART_CD
WHERE w.BRD_CD = '{brand}'
  AND w.SESN IN ('{base_season}', '{prev_season}')
  AND p.PARENT_PRDT_KIND_NM = '의류'
GROUP BY
    w.SESN,
    w.BRD_CD,
    p.PARENT_PRDT_KIND_NM,
    p.PRDT_KIND_NM,
    p.SEX_NM,
    p.CAT_NM,
    p.SUB_CAT_NM,
    p.ITEM,
    p.ITEM_NM,
    p.FIT_INFO1,
    p.SESN_SUB_NM,
    w.PART_CD,
    w.COLOR_CD,
    w.SIZE_CD
ORDER BY
    PERIOD,
    CLASS2,
    ITEM_NM,
    PART_CD,
    SIZE_CD
