-- plc_standard.sql
-- 표준 PLC 학습용 간소 데이터 (build_plc_standard.py 의 GT csv fallback).
--
-- GT csv 가 있으면 본 쿼리는 호출되지 않음. data/{BRAND}_GT_*.csv 부재 시에만 사용.
--
-- 파라미터:
--   {brand}: 단일자 브랜드 코드 (M=MLB, X=Discovery, V=Duvetica, ST=Sergio Tacchini, I=MLB KIDS)
--   {seasons_csv}: 작은 따옴표로 감싼 쉼표 구분 시즌 리스트 (예: '23F','24F','25F')
--
-- 출력 컬럼 (7개):
--   SSN_CD          시즌 코드
--   PROD_CD         스타일 코드 (= w.PART_CD)
--   COLOR_CD        컬러 코드
--   ITEM            아이템 분류 코드
--   WEEK_OF_YEAR    ISO 주차
--   SC_SALE_QTY_ALL 전체판매 (소비자 전체) = SUM(SALE_NML_QTY_CNS + SALE_RET_QTY_CNS)
--                   weekly_analysis.py 의 '총판매' 와 동일 정의 → Step 2 그래프 얼라인.
--   SC_SALE_QTY_TAX 순수 국내판매 (리테일) = SUM(SALE_NML_QTY_RTL + SALE_RET_QTY_RTL)
--                   면세 제외 국내 — predictor.py 가 사용.
--
-- 테이블:
--   FNF.PRCS.DB_SCS_W  주차별 판매/재고 실적
--   FNF.PRCS.DB_PRDT   상품 마스터 (ITEM lookup)

SELECT
    w.SESN                                                       AS SSN_CD,
    w.PART_CD                                                    AS PROD_CD,
    w.COLOR_CD,
    p.ITEM,
    EXTRACT(WEEK FROM w.END_DT)                                  AS WEEK_OF_YEAR,
    SUM(w.SALE_NML_QTY_CNS + w.SALE_RET_QTY_CNS)                 AS SC_SALE_QTY_ALL,
    SUM(w.SALE_NML_QTY_RTL + w.SALE_RET_QTY_RTL)                 AS SC_SALE_QTY_TAX
FROM FNF.PRCS.DB_SCS_W w
    LEFT JOIN FNF.PRCS.DB_PRDT p ON w.PART_CD = p.PART_CD
WHERE w.BRD_CD = '{brand}'
  AND w.SESN IN ({seasons_csv})
GROUP BY
    w.SESN,
    w.PART_CD,
    w.COLOR_CD,
    p.ITEM,
    EXTRACT(WEEK FROM w.END_DT)
ORDER BY
    w.SESN,
    w.PART_CD,
    w.COLOR_CD,
    WEEK_OF_YEAR
