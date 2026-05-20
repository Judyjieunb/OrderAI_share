-- d3_r2_similarity_gtm_image.sql
-- 유사스타일매핑 (2차): GTM 이미지 기반 ML 유사도 매핑 결과
-- R1(DB_PRDT_SIMILAR_INFO_ML)에서 매칭되지 않은 스타일 보완용
--
-- 파라미터: {brand}, {target_season}
--   brand: 브랜드코드 (M=MLB 등)
--   target_season: 차시즌 (예: 26F) ← config_loader.get_target_season()
--
-- 테이블:
--   FNF.DEV.DB_PRDT_SIMILAR_GTM_IMAGE_ML  — GTM 이미지 기반 ML 유사도
--   FNF.PRCS.DB_PRDT                      — 상품 마스터 (ITEM, CAT_NM JOIN)
--
-- 사용처: step4_integration.py (Step 4) — R1 미매칭 스타일 폴백
-- 출력 컬럼: R1(d3_similarity_mapping.sql)과 동일 + IMAGE_YN, SIMILAR_IMAGE_YN

SELECT
    a.BRD_CD,
    CASE
        WHEN SUBSTR(a.PART_CD, -2, 1) = '6' AND SUBSTR(a.PART_CD, -1) IN ('4', '6') THEN '26F'
        WHEN SUBSTR(a.PART_CD, -2, 1) = '6' AND SUBSTR(a.PART_CD, -1) = 'N' THEN '26N'
        WHEN SUBSTR(a.PART_CD, -2, 1) = '5' AND SUBSTR(a.PART_CD, -1) IN ('4', '6') THEN '25F'
        WHEN SUBSTR(a.PART_CD, -2, 1) = '5' AND SUBSTR(a.PART_CD, -1) = 'N' THEN '25N'
        ELSE SUBSTR(a.PART_CD, -2)
    END                                                     AS NEW_SEASON,
    a.PART_CD                                               AS NEW_STYLE,
    b.PRDT_NM,
    a.SIMILAR_PART_CD                                       AS SIMILAR_STYLE,
    CASE
        WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '6' AND SUBSTR(a.SIMILAR_PART_CD, -1) IN ('4', '6') THEN '26F'
        WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '5' AND SUBSTR(a.SIMILAR_PART_CD, -1) IN ('4', '6') THEN '25F'
        WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '4' AND SUBSTR(a.SIMILAR_PART_CD, -1) IN ('4', '6') THEN '24F'
        WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '3' AND SUBSTR(a.SIMILAR_PART_CD, -1) IN ('4', '6') THEN '23F'
        WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '6' AND SUBSTR(a.SIMILAR_PART_CD, -1) = 'N' THEN '26N'
        WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '5' AND SUBSTR(a.SIMILAR_PART_CD, -1) = 'N' THEN '25N'
        WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '4' AND SUBSTR(a.SIMILAR_PART_CD, -1) = 'N' THEN '24N'
        ELSE SUBSTR(a.SIMILAR_PART_CD, -2)
    END                                                     AS SIMILAR_STYLE_SEASON,
    b.ITEM,
    b.CAT_NM,
    a.RANKING,
    a.IMAGE_YN,
    a.SIMILAR_IMAGE_YN
FROM FNF.DEV.DB_PRDT_SIMILAR_GTM_IMAGE_ML a
    JOIN FNF.PRCS.DB_PRDT b
      ON b.PRDT_CD = a.BRD_CD
           || CASE
                WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '6' AND SUBSTR(a.SIMILAR_PART_CD, -1) IN ('4', '6') THEN '26F'
                WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '5' AND SUBSTR(a.SIMILAR_PART_CD, -1) IN ('4', '6') THEN '25F'
                WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '4' AND SUBSTR(a.SIMILAR_PART_CD, -1) IN ('4', '6') THEN '24F'
                WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '3' AND SUBSTR(a.SIMILAR_PART_CD, -1) IN ('4', '6') THEN '23F'
                WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '6' AND SUBSTR(a.SIMILAR_PART_CD, -1) = 'N' THEN '26N'
                WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '5' AND SUBSTR(a.SIMILAR_PART_CD, -1) = 'N' THEN '25N'
                WHEN SUBSTR(a.SIMILAR_PART_CD, -2, 1) = '4' AND SUBSTR(a.SIMILAR_PART_CD, -1) = 'N' THEN '24N'
                ELSE SUBSTR(a.SIMILAR_PART_CD, -2)
              END
           || a.SIMILAR_PART_CD
WHERE a.BRD_CD = '{brand}'
  AND a.RANKING <= 3
ORDER BY
    NEW_SEASON,
    a.PART_CD,
    a.RANKING ASC
