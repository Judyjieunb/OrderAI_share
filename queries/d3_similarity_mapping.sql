-- d3_similarity_mapping.sql
-- 유사스타일매핑: ML 모델 산출 신규↔유사 스타일 매핑 결과
--
-- 파라미터: {brand}, {target_season}
--   brand: 브랜드코드 (M=MLB 등)
--   target_season: 차시즌 (예: 26F) ← config_loader.get_target_season()
--
-- 테이블:
--   FNF.PRCS.DB_PRDT_SIMILAR_INFO_ML  — ML 유사도 매핑 결과
--   FNF.PRCS.DB_PRDT                  — 상품 마스터 (유사 스타일 정보 JOIN)
--
-- 사용처: step4_integration.py (Step 4)
-- 예상 행수: 100~500 (Top 3 × 신규 스타일 수)
-- 캐시: data/{brand}/{season}/similarity_mapping.parquet
--
-- 참고: 시즌코드는 PRDT_CD 끝자리에서 파생
--   끝 2번째 자리: 연도 (6=2026, 5=2025, 4=2024)
--   끝 1번째 자리: 시즌 (4=Fall, 6=Winter, N=연중)
--
-- 코드 적용 필터 (쿼리 후 Python에서 처리):
--   REF_SCORE >= 0.50 (MIN_SCORE) → 최소 유사도 필터
--   Long → Wide 피벗 변환 (step4_integration.py에 구현됨)

SELECT
    b.BRD_CD,
    CASE
        WHEN SUBSTR(a.PRDT_CD, -2, 1) = '6' AND SUBSTR(a.PRDT_CD, -1) IN ('4', '6') THEN '26F'
        WHEN SUBSTR(a.PRDT_CD, -2, 1) = '6' AND SUBSTR(a.PRDT_CD, -1) = 'N' THEN '26N'
        WHEN SUBSTR(a.PRDT_CD, -2, 1) = '5' AND SUBSTR(a.PRDT_CD, -1) IN ('4', '6') THEN '25F'
        WHEN SUBSTR(a.PRDT_CD, -2, 1) = '5' AND SUBSTR(a.PRDT_CD, -1) = 'N' THEN '25N'
        ELSE SUBSTR(a.PRDT_CD, -2)
    END                                                     AS NEW_SEASON,
    RIGHT(a.PRDT_CD, 9)                                     AS NEW_STYLE,
    n.PRDT_NM                                               AS NEW_PRDT_NM,
    n.PO_IMG                                                AS NEW_PO_IMG,
    b.PRDT_NM,
    b.PRDT_IMG                                              AS SIMILAR_PRDT_IMG,
    b.PO_IMG                                                AS SIMILAR_PO_IMG,
    RIGHT(a.SIMILAR_PRDT_CD, 9)                              AS SIMILAR_STYLE,
    CASE
        WHEN SUBSTR(a.SIMILAR_PRDT_CD, -2, 1) = '6' AND SUBSTR(a.SIMILAR_PRDT_CD, -1) IN ('4', '6') THEN '26F'
        WHEN SUBSTR(a.SIMILAR_PRDT_CD, -2, 1) = '5' AND SUBSTR(a.SIMILAR_PRDT_CD, -1) IN ('4', '6') THEN '25F'
        WHEN SUBSTR(a.SIMILAR_PRDT_CD, -2, 1) = '4' AND SUBSTR(a.SIMILAR_PRDT_CD, -1) IN ('4', '6') THEN '24F'
        WHEN SUBSTR(a.SIMILAR_PRDT_CD, -2, 1) = '3' AND SUBSTR(a.SIMILAR_PRDT_CD, -1) IN ('4', '6') THEN '23F'
        WHEN SUBSTR(a.SIMILAR_PRDT_CD, -2, 1) = '6' AND SUBSTR(a.SIMILAR_PRDT_CD, -1) = 'N' THEN '26N'
        WHEN SUBSTR(a.SIMILAR_PRDT_CD, -2, 1) = '5' AND SUBSTR(a.SIMILAR_PRDT_CD, -1) = 'N' THEN '25N'
        WHEN SUBSTR(a.SIMILAR_PRDT_CD, -2, 1) = '4' AND SUBSTR(a.SIMILAR_PRDT_CD, -1) = 'N' THEN '24N'
        ELSE SUBSTR(a.SIMILAR_PRDT_CD, -2)
    END                                                     AS SIMILAR_STYLE_SEASON,
    b.ITEM,
    b.CAT_NM,
    a.RANKING
FROM FNF.PRCS.DB_PRDT_SIMILAR_INFO_ML a
    JOIN FNF.PRCS.DB_PRDT b ON a.SIMILAR_PRDT_CD = b.PRDT_CD
    LEFT JOIN FNF.PRCS.DB_PRDT n ON a.PRDT_CD = n.PRDT_CD
WHERE b.BRD_CD = '{brand}'
  AND a.RANKING <= 3
ORDER BY
    NEW_SEASON,
    a.PRDT_CD,
    a.RANKING ASC
