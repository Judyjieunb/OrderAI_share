# STEP 5: 사이즈 배분 운영 가이드

> Step 4에서 확정한 컬러별 수량(`confirmed_order_data.json`)을 Step 5에서 사이즈별로 배분하는 로직.
> 본 문서는 **현재 동작 + 변경 계획 + 합의 필요 사항**을 한 곳에 정리한 작업 문서.

---

## 1. 배경 및 목적

### 입력
- Step 4 산출물: `public/confirmed_order_data.json`
  - `class2`, `new_part_cd`, `new_item_nm`, `color_cd`, `confirmed_qty`, `size_range`, `sex`
- Step 5 데이터: `public/size_assortment_data.json` (당해+전년 SALE_QTY 풀)

### 출력
- 스타일×컬러 → 사이즈별 발주량 분배 결과
- UI: `SizeDistributionModal` 표시 + Excel 다운로드

---

## 2. 현재 동작과 한계

### 현재 매칭 흐름 (`SizeAssortment.jsx:150-251`)

```
① 컬러코드 → COLOR_RANGE 매핑 (color_mapping.json)
② new_part_cd[1] → 성별 (A=공용/F=여성/L=남성)
③ 풀 필터링: 성별 일치 우선, 없으면 전체 폴백
④ 계층 매칭 (Fallback Level)
   L1: CLASS2 × ITEM × COLOR_RANGE
   L2: CLASS2 × COLOR_RANGE
   L3: CLASS2 × ITEM
   L4: CLASS2
   NONE: warning
⑤ SIZE_CD별 SALE_QTY 합산 → 비중 → 배분
```

### 한계 (사이즈 분포 단계)

| 케이스 | 현재 동작 | 문제 |
|--------|----------|------|
| **과거 ⊃ 신규** (과거 1~5, 신규 1,3,5) | 빠진 2/4 수요를 모든 사이즈에 비례 흡수 | **중앙 사이즈에 부자연스럽게 몰림** |
| **신규 ⊃ 과거** (과거 2~4, 신규 1~5) | 1, 5에 0 배분 | **사용자 의도와 불일치 — 0 발주** |
| **단위 변환** (과거 235 mm, 신규 230/240) | 235 실적 제거(범위 밖) → 비례 흡수 | **5단위 수요가 균등 흡수** (인접에 흐르지 않음) |

---

## 3. 변경 후 동작 (목표)

### Before / After

| 케이스 | Before | After |
|--------|--------|-------|
| 과거 ⊃ 신규 | 비례 흡수 (중앙 몰림) | **인접 신규 사이즈에 5:5 분할** (정책 1) |
| 신규 ⊃ 과거 | 0 배분 | **카테고리 분포 참조해 가상 비중 채움** (정책 3) |
| 운영 사이즈 합 정규화 | ✅ 이미 동작 | 그대로 유지 (정책 2) |
| 단위 변환 | 미지원 | **5단위 실적을 10단위 양옆에 5:5 분할** (정책 1 특수형) |

---

## 4. 통합 흐름 (3단계)

> 단위 변환(5단위↔10단위)은 신발 카테고리 확장 계획이 없어 **미도입** (§9.4 확정).

```
[입력]
  past_size_sales: {SIZE_CD → SALE_QTY}   (매칭 후 집계)
  new_size_range:  [SIZE_CD, ...]         (신규 전개 사이즈)
  size_order:      [SIZE_CD, ...]         (정렬 순서)
  confirmed_qty:   int
  category_dist:   {SIZE_CD → ratio}       (정책 3용 — 사전 집계)

[처리 순서]

Step 1. 인접 분배 (정책 1)
        past_size_sales 중 new_size_range에 없는 사이즈 처리
        - 양쪽 인접이 신규에 둘 다 있음 → 5:5 분할
        - 한쪽만 있음 (끝단) → 그쪽에 100%
        - 양쪽 다 비어있음 → 한 단계 더 멀리 재귀 (§9.3)

Step 2. 빈자리 채우기 (정책 3)
        new_size_range 중 past_size_sales[s] = 0인 사이즈 처리
        - 카테고리 분포(category_dist)에서 그 사이즈의 비중 b% 가져오기
        - 나머지 (100-b)%를 기존 past_size_sales 비중대로 정규화
        - 카테고리 분포에서도 0 → 인접 비례 폴백 (정책 1과 동일 원리, α=0.5)

Step 3. 정규화 + 배분 (정책 2 + 기존 마무리)
        최종 past_size_sales → 합=100% 정규화 → confirmed_qty × 비중
        10단위 반올림 + 잔여분 최대 비중 사이즈에 가산
```

---

## 5. 단계별 상세

### Step 1. 인접 분배

**트리거**: `past_size_sales` 중 `new_size_range`에 없는 사이즈

**규칙**: `size_order` 기준 좌우 인접 검색
- 양쪽 다 신규에 있음 → 5:5 분할
- 한쪽만 있음 → 그쪽 100%
- 양쪽 다 비어 있음 → 한 단계 더 멀리 (사이즈 순서로 한 칸씩 이동, 단순 전이)

**예시**: 과거 `1=100, 2=200, 3=400, 4=200, 5=100`, 신규 `[1, 3, 5]`
- 2의 200 → 1, 3에 100/100
- 4의 200 → 3, 5에 100/100
- 결과: `1=200, 3=600, 5=200`

### Step 2. 빈자리 채우기

**트리거**: `new_size_range`에 있는데 `past_size_sales[s] = 0`인 사이즈

**참조 단위**: 단계적 폴백 (구체화는 §9에서)

**규칙**:
1. 카테고리 분포에서 사이즈 s의 비중 `b%` 조회 (없으면 표본 큰 단계로 폴백)
2. 가상 비중 부여 → 나머지 `(100-b)%` 는 기존 `past_size_sales` 비중대로 정규화

**예시**:
- `past_size_sales = {230:300, 240:400, 250:200}`, 신규 `[220, 230, 240, 250]`
- 카테고리 분포에서 220 = 8%
- 220 가상 비중 = 8%, 나머지 92% → 230:240:250 = 300:400:200 비율로 배분

### Step 3. 정규화 + 배분

기존 코드 그대로:
1. 보정된 `past_size_sales` 합으로 비중 계산
2. `confirmed_qty × 비중` → 10단위 반올림
3. 잔여분 → 최대 비중 사이즈에 가산

---

## 6. 시나리오 예시 (단위 테스트 후보)

### 시나리오 A: 과거 ⊃ 신규 (홀수만 전개)
- 과거: `1=100, 2=200, 3=400, 4=200, 5=100`
- 신규: `[1, 3, 5]`, qty=1000
- 기대: `1=200, 3=600, 5=200`

### 시나리오 B: 신규 ⊃ 과거 (양 끝 누락)
- 과거: `230=300, 240=400, 250=200`
- 신규: `[220, 230, 240, 250, 260]`, qty=1000
- 카테고리 분포: `220=8%, 230=25%, 240=35%, 250=22%, 260=10%`
- 기대: 220과 260에 가상 비중 부여 → 220 ≈ 80, 260 ≈ 100 …

### 시나리오 C: 중간 누락
- 과거: `XS=50, S=200, M=400, L=200, XL=50`
- 신규: `[XS, S, L, XL]` (M 빠짐)
- M 수요 400 → S와 L에 200/200 분배
- 기대: `XS=50, S=400, L=400, XL=50`

### 시나리오 D: 양쪽 인접 없음 (먼 끝단 누락)
- 과거: `M=400, L=300` (XS, S, XL, XXL 모두 없음)
- 신규: `[XS, S, M, L, XL, XXL]`
- XS, S, XL, XXL 모두 빈자리 → 정책 3로 카테고리 분포 참조

### 시나리오 E: 카테고리 분포에서도 0 (최후 폴백)
- 모든 폴백 단계에서 빈 사이즈 비중 = 0
- 인접 비례 폴백 발동 (정책 1과 동일 원리, α=0.5)

---

## 7. 영향받는 파일

| 파일 | 변경 내용 | 비고 |
|------|----------|------|
| `src/utils/sizeDistribution.js` (신규) | 4단계 통합 함수 | UI/Excel 공유 모듈 |
| `src/components/SizeAssortment.jsx:150-251` | `computeDistribution` → 신규 모듈 호출로 교체 | UI 표시 |
| `src/components/SizeAssortment.jsx:484-541` | `handleDirectExcelExport` 내부 중복 제거 | 동기화 비용 제거 |
| `scripts/generate_size_data.py` | **카테고리 사이즈 분포 사전 집계** 추가 | `size_assortment_data.json`에 `category_size_dist` 키 추가 |
| `docs/STEP5_사이즈배분_운영가이드.md` | (본 문서) | |

---

## 8. 합의 완료 사항

### 8.1 통합 로직

| 항목 | 결정 |
|------|------|
| 운영 범위 밖 과거 실적 처리 | **정책 1 (인접 분배)** — 비례 흡수 폐기 |
| 단위 변환 (5단위 ↔ 10단위) | **미도입** (§9.4 — 신발 카테고리 확장 계획 없음) |
| 빈자리 채우기 | **카테고리 분포 참조 (정책 3)** |
| 정규화 시점 | **모든 보정 끝난 후 마지막** |
| 카테고리 분포도 0일 때 | **인접 비례 폴백** (정책 1과 동일 원리) |

### 8.2 사이즈 매칭 통합 폴백 체인 (✅ §9.1+§9.2 검증 후 확정)

신규 스타일이 참조할 ref 실적 표본을 좁히는 단일 통합 매칭 체계.
표본은 두 목적에 공유됨:
1. 사이즈 비중 계산 (기존 L1~L4 매칭의 역할 대체)
2. 빈자리 채울 카테고리 분포 산출 (정책 3 역할)

분포에 영향을 주는 변수 (영향력 순): **SEX > ITEM ≈ CLASS2 > SESN_SUB_NM > FIT_INFO1**
**COLOR_RANGE는 제외** (사이즈 분포와 독립 — 변수 영향력 표에서 확정).

| Level | 키 조합 | 폴백 시 제외 변수 |
|-------|---------|----------------|
| **L1** | SEX × CLASS2 × ITEM × SESN_SUB_NM × FIT_INFO1 | (가장 정밀) |
| **L2** | SEX × CLASS2 × ITEM × SESN_SUB_NM | FIT 제외 (영향력 최소) |
| **L3** | SEX × CLASS2 × ITEM | SESN_SUB 제외 |
| **L4** | SEX × CLASS2 | ITEM 제외 (SEX 보존) |
| **L5** | CLASS2 | SEX 제외 (최후) |

### 8.3 폴백 트리거 및 임계치

| 트리거 | 동작 |
|--------|------|
| **A. 매칭 SC 0건** | → 다음 Level로 폴백 |
| **B. 표본 부족 (SC < 10)** | → 다음 Level로 폴백 |
| **C. 해당 사이즈 비중 0%** | → 그 Level 내에서 **인접 비례 배분** (다음 Level 안 감) |
| **L5도 표본 부족** | → **인접 비례 폴백** (정책 1 원리) |

- **SC 임계치**: **≥ 10** (검증 §9.1 근거)
- **FIT_INFO1 Null 처리**: **Level 1 스킵, Level 2부터 매칭** (Duvetica 50% Null 케이스 대응)

### 8.4 사전 집계 위치

`size_assortment_data.json`에 임베드:
```json
{
  "category_size_dist": {
    "by_l1": { "남성|Outer|DJ|Winter|Over": {"M": 0.18, "L": 0.32, ...}, ... },
    "by_l2": { "남성|Outer|DJ|Winter":      {"M": 0.20, "L": 0.30, ...}, ... },
    "by_l3": { "남성|Outer|DJ":             {"M": 0.22, "L": 0.28, ...}, ... },
    "by_l4": { "남성|Outer":                {"M": 0.20, "L": 0.30, ...}, ... },
    "by_l5": { "Outer":                     {"M": 0.18, "L": 0.32, ...}, ... }
  },
  "category_sample_count": {
    "by_l1": { "남성|Outer|DJ|Winter|Over": 24, ... },
    ...
  }
}
```

---

## 9. 폴백 로직 구체화

> §9.1~9.5 ✅ 확정 완료.

### 9.1 정책 3 카테고리 분포 참조 단계 (✅ 확정)

**결정**: SEX > ITEM ≈ CLASS2 > SESN_SUB_NM > FIT_INFO1 영향력 순으로 5단계 폴백 체인 (§8.2 참조).
**SC 임계치**: ≥ 10 (3개 브랜드 실데이터 검증 결과 §8.3 참조).

#### 검증 결과 (3개 브랜드 25F, 당해+전년)

| 지표 | Duvetica | MLB | Discovery |
|------|---------|-----|-----------|
| 행수 | 2,750 | 10,533 | 9,768 |
| SC unique | 337 | 780 | 775 |
| FIT_INFO1 Null | **50%** | 0% | 1.4% |
| SESN_SUB_NM Null | 0% | 0% | 0% |
| 특이 | 럭셔리 다운 전문 | 공용 사이즈 압도적 | 아동 라인 별도 |

#### SC ≥ 10 임계치 통과율

| Level | Duvetica | MLB | Discovery | 해석 |
|-------|---------|-----|-----------|------|
| L1 | 6% | 11% | 8% | 좁아서 어차피 폴백 — 통과 시 정확도 매우 높음 |
| L2 | 18% | 39% | 24% | 일부 매칭 — 의미 있음 |
| L3 | 22% | 50% | 38% | **충분히 매칭** — 정확도 이득 |
| L4 | 100% | 100% | 85% | 거의 항상 매칭 — 안전망 |
| L5 | 100% | 100% | 75%* | 최후 안전망 |

*Discovery `Wear_etc` 클래스(5 SC)는 L5에서도 ≥10 미달 → 인접 비례 폴백 발동

#### 검증 스크립트

- `test/ml_experiment/check_size_dist_levels.py` (Duvetica, brand_config 기준)
- `test/ml_experiment/check_size_dist_levels_mlb.py` (MLB, 직접 SQL)
- `test/ml_experiment/check_size_dist_levels_discovery.py` (Discovery, 직접 SQL)

#### 다른 임계치 후보 (참고)

| 임계치 | 평가 |
|--------|-----|
| SC ≥ 30 | ❌ MLB L3에서도 15%만 통과 — L1~L3 효용 거의 손실 |
| SC ≥ 20 | ⚠ L2~L3 절반 이상 폴백 |
| **SC ≥ 10** | ✅ **확정** — 3개 브랜드 일관된 동작 |
| SC ≥ 5 | ❌ 끝단 표본 0~1건 — 통계 노이즈 큼 |

### 9.2 매칭 레벨과의 관계 (✅ 확정 — 통합)

**결정**: 사이즈 매칭과 카테고리 분포 참조를 **단일 통합 폴백 체인**으로 운영.
§8.2의 L1~L5가 두 목적을 모두 담당.

#### 통합 vs 분리 비교

| 옵션 | 동작 | 평가 |
|------|------|------|
| **(a) 통합 ✅** | 매칭 폴백 = 분포 참조 폴백, 동일 키 패밀리 | 단순 + 일관 — **확정** |
| (b) 분리 | 매칭은 컬러 기반(기존), 분포 참조는 신규 키 | 두 시스템 병행 — 코드 복잡 |
| (c) 부분 결합 | 매칭에 SEX/SESN/FIT만 추가 | 분포 참조에 COLOR 들어가 무의미 |

#### COLOR_RANGE 제거 이유

- 변수 영향력 평가표(§8.2 위쪽 합의)에서 "사이즈 분포와 독립 — 제외"로 확정
- 현재 사이즈 매칭(L1: CLASS2 × ITEM × COLOR_RANGE)에서 COLOR_RANGE 키 제거
- 컬러 매칭은 Step 4(컬러 배분)의 책임이고, Step 5(사이즈 배분)는 사이즈 영향 변수만 사용

#### 기존 매칭과의 차이

| 구분 | 기존 (`SizeAssortment.jsx:172-200`) | 통합 후 |
|------|----------------------------------|---------|
| L1 | CLASS2 × ITEM × COLOR_RANGE | **SEX × CLASS2 × ITEM × SESN_SUB × FIT** |
| L2 | CLASS2 × COLOR_RANGE | **SEX × CLASS2 × ITEM × SESN_SUB** |
| L3 | CLASS2 × ITEM | **SEX × CLASS2 × ITEM** |
| L4 | CLASS2 | **SEX × CLASS2** |
| L5 | (없음, NONE warning) | **CLASS2** |
| 표본 임계치 | 없음 (단순 매칭 여부) | **SC ≥ 10** (없으면 다음 Level) |
| FIT Null 처리 | 미지원 | **Level 1 스킵, Level 2부터 매칭** |

#### 영향받는 코드

- `src/components/SizeAssortment.jsx:172-200` (`computeDistribution`의 Level 매칭부)
- `src/components/SizeAssortment.jsx:496-511` (`handleDirectExcelExport` 중복 로직)
- `scripts/generate_size_data.py`: HIERARCHY에 `SESN_SUB_NM`, `FIT_INFO1` 추가
- `size_assortment_data.json` 스키마: `SESN_SUB_NM`, `FIT_INFO1` 컬럼 추가

### 9.3 인접 분배 끝단 처리 (✅ 확정 — 재귀적 동일 규칙)

#### 적용 대상

두 케이스에 동일 알고리즘:
1. **정책 1**: 신규에 없는 과거 사이즈의 수요를 인접 신규 사이즈에 분배
2. **정책 3**: 그 Level의 카테고리 분포에서 사이즈 비중이 0%일 때 인접 비례 폴백

#### 알고리즘 — 양쪽 빔 처리

```
function distribute_to_adjacent(missing_size, qty, new_size_range):
    distance = 1
    while distance < max_size_steps:
        left  = missing_size 기준 왼쪽으로 distance만큼 떨어진 사이즈
        right = missing_size 기준 오른쪽으로 distance만큼 떨어진 사이즈
        
        left_in_range  = left ∈ new_size_range
        right_in_range = right ∈ new_size_range
        
        if left_in_range and right_in_range:
            return {left: qty/2, right: qty/2}   # 거리 동일, 5:5
        elif left_in_range:
            return {left: qty}                    # 한쪽만 있음 → 100%
        elif right_in_range:
            return {right: qty}
        else:
            distance += 1                         # 한 칸 더 멀리 재귀
    
    return {first(new_size_range): qty}          # 안전망 (극단 케이스)
```

#### 정책 1 vs 정책 3의 차이

| 정책 | 출력 | 결합 방식 |
|------|------|----------|
| **정책 1** | 수요량(qty) 보존 — 합계 유지 | 인접 사이즈에 절대값 가산 |
| **정책 3** | 가상 비중 부여 | 가장 가까운 비어있지 않은 사이즈 비중 × **α=0.5** (양쪽이면 평균 × α) |

> α는 하드코딩 0.5로 시작, 운영 결과에 따라 조정. 코드에 상수로 노출.

#### 적용 예시

**정책 1**: 신규 `[1, 5]`, 과거 `[1,2,3,4,5]` (각 100건)

| 빠진 사이즈 | 거리 | 처리 | 분배 |
|------------|------|------|------|
| 2 | 1 | 1(✓), 3(✗) | 1에 100 |
| 3 | 1→2 | 2(✗), 4(✗) → 1(✓), 5(✓) | 1에 50, 5에 50 |
| 4 | 1 | 3(✗), 5(✓) | 5에 100 |

→ 최종 보정: 1에 250(원본 100 + 50 + 100), 5에 250

**정책 3**: 신규 `[XS, S, M, L, XL]`, 카테고리 분포 `XS=0%, S=0%, M=40%, L=35%, XL=20%`

| 빈자리 | 거리 | 처리 | 가상 비중 |
|--------|------|------|----------|
| XS | 1→2→3 | S(0%), M(40%) → 거리 3 한쪽 | M × 0.5 = 20% |
| S | 1 | XS(0%), M(40%) → M만 있음 | M × 0.5 = 20% |

→ 후 정규화하여 비중 합 100% 맞춤

### 9.4 단위 변환 트리거 조건 (✅ 확정 — 미도입)

**결정**: 현재 d4 데이터가 `PARENT_PRDT_KIND_NM = '의류'` 필터로 한정돼 있고, **신발 카테고리 확장 계획이 없어** 단위 변환 로직 자체를 도입하지 않음.

- 의류 사이즈는 영문(XS~XXL) 또는 한국 숫자(85~105) 위주 → 5단위/10단위 구분 무의미
- 추후 신발/가방 카테고리 확장 시 별도 검토

### 9.5 양 단위 혼재 (✅ 확정 — 미도입)

**결정**: §9.4 단위 변환 미도입 결정에 따라 자동 미도입.
신규 `size_range`에 다양한 단위가 섞여 들어오더라도 단위 변환 로직 없이 그대로 매칭에 사용.

---

## 10. 후속 작업 순서

1. ✅ §9.1~9.5 합의 완료 → §8 반영
2. `scripts/generate_size_data.py` 변경
   - HIERARCHY에 `SESN_SUB_NM`, `FIT_INFO1` 추가
   - 카테고리 분포 사전 집계(§8.4 스키마) 추가 — L1~L5 단위
3. `src/utils/sizeDistribution.js` 신규 모듈
   - Step 1 인접 분배 (§5.Step1)
   - Step 2 빈자리 채우기 (§5.Step2)
   - Step 3 정규화 + 배분 (§5.Step3)
   - 단위 테스트 (시나리오 A~E)
4. `SizeAssortment.jsx` 통합
   - `computeDistribution` → 신규 모듈 호출로 교체
   - 기존 L1~L4 매칭(COLOR_RANGE 포함) → §8.2 통합 폴백 체인으로 대체
   - `handleDirectExcelExport` 중복 제거 (모듈 공유)
5. UI 매칭 디버그 표시 (어느 Level/트리거가 적용됐는지)

---

## 11. 트러블슈팅

### 11.1 DuckDB 스키마 마이그레이션 (Phase 3-1)

이 변경은 `size_assortment` 테이블에 **컬럼 2개 추가** (`sesn_sub_nm`, `fit_info1`) +
`size_assortment_meta` 테이블 **신규** 생성을 포함합니다.

**기본적으로 자동 처리됩니다.** `scripts/dump_to_duckdb.py` 의 `_ensure_size_assortment_schema()`
가 dump 시점마다 기존 테이블 컬럼 수를 검사 → 구 스키마(<15컬럼) 발견 시 자동 DROP 후
재생성합니다. Idempotent — 신 스키마면 noop, fresh DB 면 noop. 운영자 손 불필요.

**안전망: 자동 처리 실패 시 수동 reset:**

```bash
# 1회성 baseline DB 재생성 — 데이터는 다음 run_all 이 재생성하므로 손실 없음
rm data/production/order_ai.duckdb
.venv/bin/python scripts/run_all.py
```

**증상:** `INSERT INTO size_assortment` 에서 컬럼 mismatch / "table size_assortment has 13 columns
but 15 values were supplied" 류 에러. 자동 마이그레이션이 안 돈 환경 (예: 외부에서 직접 만든 DB)
에서 발생할 수 있음.
