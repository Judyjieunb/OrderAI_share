# PLC Guide — order-ai-share

> 본 fork 의 핵심 설계: **각 브랜드는 자기 raw 데이터로 PLC 표준 곡선을 직접 생성** 합니다 (cross-brand 평균 사용 X).

---

## PLC 란?

**P**roduct **L**ife **C**ycle. 시즌 내 한 아이템 (예: "다운자켓", "트랙수트") 이 1주차부터 26주차까지 팔리는 **표준 패턴 곡선**입니다.

AI 발주량 예측의 기본 재료:
- 시즌 시작 후 N주가 지나면 → 표준 곡선의 N번째 점 = 누적 판매 비율 → 잔여 시즌의 잠재 수요 추정 가능

본 fork 의 `scripts/plc_engine/` 가 이 추정을 담당.

---

## 왜 자기 브랜드 데이터로?

| 접근법 | 장점 | 단점 |
|---|---|---|
| Cross-brand 평균 (MLB+Discovery 등) | AX팀이 1회 추출 후 모든 brand 가 공유 | 본 브랜드 고유 아이템 / 라이프사이클이 평균에 묻힘. Sergio 같이 다른 카테고리는 매칭 35% 만 (나머지는 fallback) |
| **자기 브랜드 자체** ★ | 항상 100% 본 브랜드 fit. severance 정합. | 최초 1회 >=2 시즌 데이터 필요 |

본 fork 는 후자 채택.

---

## 데이터 요건

| 조건 | 필수 |
|---|---|
| **>=2 완전 시즌** 의 weekly_raw 데이터가 Snowflake 에 적재 | ✅ |
| Snowflake service account 가 본 브랜드 raw 테이블 SELECT 권한 보유 | ✅ |
| 시즌 카테고리 / 아이템 분류 일관성 (시즌 간 컬럼명 동일) | ✅ |

---

## 첫 회 PLC 빌드

```bash
.venv/bin/python scripts/plc_engine/build_plc_standard.py
```

자동 동작:

1. Snowflake 에서 본 브랜드 weekly_raw 누적 조회
2. **Sufficiency gate** — 시즌 카운트 <2 면:
   ```
   RuntimeError: 최소 2 시즌의 weekly_raw 데이터 필요.
   AX팀에 seed PLC 요청하세요: ax-team@fnf.co.kr
   ```
   → Cold-start 브랜드. SUPPORT.md "Cold-start 브랜드" 항목 참고.
3. PLC 추출 (lifecycle curve 학습)
4. `data/plc/{brand}_{type}_plc_forecast_standard.csv` 출력 (예: `mlb_fw_*`, `discovery_ss_*`). brand 와 type 은 `.env::BRAND` + `brand_config.json::targetSeason` 으로 자동 도출. 실제 경로 확인: `python -c "import sys; sys.path.insert(0,'scripts'); from config_loader import get_plc_forecast_path; print(get_plc_forecast_path())"`.
5. Coverage report 표시:
   ```
   처리된 아이템: 1,247
   Insufficient data 로 fallback: 12
   ```

첫 회는 **drift report 없음** (기존 PLC 없으므로).

---

## 재생성 (누적 데이터로)

새 시즌 데이터가 누적되면 재실행:

```bash
.venv/bin/python scripts/plc_engine/build_plc_standard.py
```

이번엔 **drift report** 가 추가로 출력:

| 평균 MAPE | 의미 | 권장 행동 |
|---|---|---|
| **<5%** | 변화 미미. 재생성해도 거의 동일. | **출시 보류 권장** — 재생성 효과 없으니 기존 PLC 유지. |
| **5–30%** | 정상 적응. 시간이 지나며 자연스럽게 패턴 정제됨. | 새 표준 적용. 다음 시즌 부터 사용. |
| **>30%** | 큰 차이. 외부 요인 (시즌 코로나 영향, 라인 재편 등) 또는 데이터 오류 의심. | raw 데이터 검증 후 재실행. 의심 시 AX팀에 1순위 contact. |

자세한 비교 csv 는 `data/plc/drift_report_{timestamp}.csv` 에 추가 출력 (>30% 케이스에 한해).

---

## 언제 재생성?

| 시점 | 재생성? |
|---|---|
| 첫 셋업 | 필수 (또는 AX팀 seed PLC) |
| 한 시즌 종료 직후 | 권장 — 새 누적 데이터 반영 |
| 발주 직전 (시즌 시작 ~1개월 전) | 선택 — drift 가 클 것 같으면 |
| 동일 시즌 안에서 | 불필요 — 한 시즌은 동일 PLC 유지 |
| 새 카테고리 / 아이템 라인 추가 | 권장 — 새 아이템의 lifecycle 학습 |
| Snowflake 데이터 정정 발생 | 권장 — 오류 데이터 영향 제거 |

---

## Cold-start 브랜드 대응

본 브랜드의 weekly_raw 데이터가 <2 시즌:

1. AX팀에 seed PLC 요청 (1회 한정 — SUPPORT.md 참고)
2. AX팀이 유사 카테고리 분석 + manual 분석으로 seed `{brand}_{type}_plc_forecast_standard.csv` 생성
3. 1Password share 또는 GPG 로 전달
4. 본인이 `data/plc/{brand}_{type}_plc_forecast_standard.csv` (본인 환경의 brand/type) 에 배치
5. 첫 시즌 운영
6. 시즌 종료 후 자체 데이터로 `build_plc_standard.py` 재실행 → 자체 PLC 로 전환

이 단계 후로는 cross-brand 의존 0.

---

## PLC 가 발주 추천에 어떻게 쓰이는지

```
weekly_raw (Snowflake)
     │
     ▼  scripts/run_all.py → ai_sales_loss_v3.py
PLC 표준 곡선 (data/plc/{brand}_{type}_plc_forecast_standard.csv)
     │
     ▼  + 현재 시즌의 누적 판매 데이터
잠재 수요 추정 + 기회비용 계산
     │
     ▼  (server/services/order_calc.py)
발주 추천량 (Step 4 화면)
```

PLC 가 정확할수록 발주 추천이 정확해집니다.

---

## 관련 코드

| 파일 | 역할 |
|---|---|
| `scripts/plc_engine/build_plc_standard.py` | PLC 생성/재생성 (CSV/Snowflake 직접 처리) |
| `scripts/plc_engine/engine.py` | PLC 추출 엔진 (core) |
| `scripts/plc_engine/predictor.py` | PLC 기반 잠재 수요 예측 |
| `scripts/plc_engine/specs.py` | PLC 스키마 (`BrandSpec`, `SeasonSpec`, `EngineParams`) |
| `scripts/ai_sales_loss_v3.py` | PLC 사용해서 기회비용 계산 (run_all.py 의 step 3) |
| `public/plc_engine_config.json` | 브랜드별/시즌별 PLC 파라미터 + `item_nm_map_path` |
| `public/item_nm_map.json` | 전 브랜드 공통 ITEM 코드 → 한글명 매핑 (PLC 빌드 시 자동 적용) |
| `data/plc/{brand}_{type}_plc_forecast_standard.csv` | 빌드 산출 — fork 동봉 (mlb/discovery × fw/ss 4개) |

수정 시 [`CLAUDE.md`](../CLAUDE.md) §2 의 디렉토리 dos/donts 참고.

---

## 자주 묻는 질문

### Q. PLC 가 매번 같은 값을 만드나?

A. **No.** 학습 알고리즘이 deterministic 이지만, 입력 데이터 (weekly_raw) 가 매번 다릅니다 (Snowflake 업데이트 반영). 같은 시점 같은 데이터로는 같은 결과.

### Q. 재생성하면 옛 PLC 는 어디로?

A. 같은 (brand, type) 의 PLC 파일에 overwrite (예: `mlb_fw_plc_forecast_standard.csv`). 다른 (brand, type) 파일은 영향 없음. 백업이 필요하면 재실행 전 수동 copy:

```bash
cp data/plc/mlb_fw_plc_forecast_standard.csv data/plc/mlb_fw_plc_forecast_standard.{date}.csv
```

### Q. 다른 브랜드의 PLC 를 빌려와도 되나?

A. 기술적으로는 가능 (csv 파일 같은 위치에 두면 됨). 다만 본 fork 의 설계 의도에 어긋남 — 본 브랜드 데이터로 검증되지 않은 PLC 사용 시 추천 정확도 보장 X. AX팀 추천 X.

### Q. PLC 가 만들어지지 않는 아이템은?

A. `Insufficient data` 로 분류 → fallback 곡선 (해당 브랜드의 전체 평균) 사용. Coverage report 에서 카운트 확인 가능. 첫 시즌은 fallback 비중이 클 수 있고 누적될수록 줄어듭니다.

### Q. PLC 생성에 얼마나 걸리나?

A. 본 브랜드 데이터 크기에 따라 30초 ~ 5분. Snowflake 쿼리 시간 포함.
