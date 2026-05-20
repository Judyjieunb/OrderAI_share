# CLAUDE.md — order-ai-share

> 본 디렉토리에서 Claude Code 와 함께 작업할 때의 가드레일. 사람도 같이 읽으면 됨.
>
> **첫 번째 원칙**: 본 fork 는 사업부 자치 운영용 — AX팀과 동기화 없음 (severance). 변경은 자유롭지만 결과/검증은 사업부 책임.

---

## 0. 작업 시작 전 반드시 확인

1. [`README.md`](./README.md) — 전체 그림
2. [`SETUP.md`](./SETUP.md) — 셋업 / 트러블슈팅 FAQ
3. [`TODO.md`](./TODO.md) (있다면) — 진행 중/보류 항목
4. 본 CLAUDE.md §1 "변경 가능 vs 변경 금지" 표 — 작업 위치가 어느 영역인지 먼저 파악

> **변경 전 영향도 분석 필수**: 코드 수정 전 upstream(입력 제공처) + downstream(출력 소비처) 의 전체 연결고리를 파악하고, 영향받는 파일 목록을 의뢰자에게 먼저 공유.

> **구조/방식 변경 시 비교분석 필수**: 새로운 방식 도입이나 기존 방식 변경 요청 시 무조건 수용하지 말고, **현재 방식 vs 새 방식의 장단점을 비교 테이블로** 제시한 뒤 합의된 방향으로 진행.

---

## 1. 변경 가능 vs 변경 금지

### 🟢 Config / Param — 자유롭게 변경

| 위치 | 변경 가능 항목 | 반영 방법 |
|---|---|---|
| `.env` | 환경 변수 (Snowflake / BRAND / DUCKDB_PATH 등). `SNOWFLAKE_AUTH=externalbrowser` 로 SSO 모드 토글 가능 | 서버 재기동 |
| `public/brand_config.json` | targetSellThrough, gradeThresholds, sizeOrder 등 | 다음 파이프라인 실행 시 |
| `requirements.txt` | 새 패키지 추가 | `pip install -r requirements.txt` |
| `apps/lite/package.json` | 프론트 새 패키지 | `npm install` |

### 🟡 새 함수 / 새 컴포넌트 추가 — 권장 패턴

기존 코드를 수정하는 대신 **새 파일 / 새 함수 추가** 가 더 안전:

| 위치 | 권장 패턴 |
|---|---|
| `server/services/order_calc.py` | 새 함수 추가 (`apply_budget_my_team` 등). 기존 `apply_budget_and_color` 수정 X |
| `server/services/color_allocation.py` | 새 매칭 전략 함수 추가 |
| `server/routers/lite.py` | 새 endpoint 추가 (기존 endpoint 의 응답 키 변경은 위험) |
| `apps/lite/src/components/` | 새 컴포넌트 파일 추가. 기존 Step 1~5 컴포넌트는 surgical 수정만 |

### 🔴 절대 금지 — 변경 시 모든 결과의 신뢰성 무너짐

| 위치 | 이유 |
|---|---|
| `server/db.py` 의 DuckDB 스키마 가정 | DuckDB 테이블 컬럼명/타입 박제. 잘못 만지면 모든 step 깨짐 |
| `server/routers/lite.py` 의 **endpoint 경로** | 프론트가 호출 — URL 변경 시 양쪽 동시 수정 필수 |
| `scripts/plc_engine/` 의 core (`engine.py`, `predictor.py`, `specs.py`) | PLC 학습 로직 자체. 잘못 만지면 발주 예측이 무의미 |
| `apps/lite/src/service/apiClient.js` 의 `FILE_TO_ENDPOINT` 매핑 | baseline / 사물함 라우팅의 anchor |
| 본인 사물함 JSON 파일명 (`confirmed_*`, `go_list.json`) | 백엔드/프론트 양쪽 contract |

### 🔴 절대 부활시키지 마세요 — 의도적 제거

본 fork 는 다음을 **명시적으로 제거** 했습니다. 비슷한 코드/파일을 다시 만들면 fork 의 설계 의도 위반:

| 항목 | 왜 제거됨 |
|---|---|
| `server/s3_client.py` | share 는 S3 미사용 (로컬 파일시스템) |
| `server/routers/full.py` | full 모드 미지원 |
| `server/production*.py` | 컨테이너/EC2 배포 미지원 (로컬 운영만) |
| `apps/lite/src/components/common/StaleWarning.jsx` | manual 파이프라인 모델 — stale 개념 노이즈 |
| `scripts/ai_sales_loss_v2_legacy.py` | V3 PLC 엔진만 사용 |
| `scripts/seed_users.py` | 단일 운영자 — 권한 매트릭스 X |
| `Dockerfile`, `deploy.sh`, `docker-compose.yml` | 로컬 운영 |
| `HARDCODED_BRAND_MAP`, `ROLE_TO_BRAND`, `BRAND_ENUM` | 단일 브랜드 — 매핑 불필요 |

---

## 2. 디렉토리별 Dos / Donts

### `server/`

**Dos**
- 새 endpoint 필요 시 `server/routers/lite.py` 끝부분에 `@router.get/post` 추가
- 새 비즈니스 로직 → `server/services/` 에 새 모듈 추가 (`my_team_rules.py` 등)
- DuckDB 의 새 query → `server/db.py` 끝부분에 새 함수 추가 (기존 함수 시그니처 변경 X)

**Donts**
- ❌ `server/api.py` 의 `app` 변수에 새 import / 새 미들웨어 함부로 추가 — CORS 설정 깨짐 가능
- ❌ `server/permissions.py` 의 함수 시그니처 변경 — routers/lite.py 가 `Depends()` 로 호출
- ❌ DuckDB write 쿼리 추가 — baseline 은 read-only. write 가 필요하면 `data/user-storage/` 의 로컬 파일로
- ❌ S3 / boto3 / presigned URL 코드 재도입

### `apps/lite/src/`

**Dos**
- API 호출은 항상 `createApiClient(user.email, brand, season, user.role)`. `useMemo` 로 감싸기
- baseline 데이터 fetch → `api.fetchFile('xxx.json')` (filename 화이트리스트 확인)
- POST 액션 → `api.post('/api/lite/xxx', body)` 또는 `/api/lite/...`
- 새 컴포넌트 → `src/components/` 평면 배치, 공통은 `common/` 하위

**Donts**
- ❌ `fetch('/api/lite/...')` 직접 호출 — 항상 `createApiClient` 경유 (X-User-Email 헤더 + brand/season 자동 부착)
- ❌ DCS AI 인증 코드 재도입 (`postMessage`, `ALLOWED_ORIGINS` 등) — share 는 single user stub
- ❌ `StaleWarning` 컴포넌트 재생성 — manual 모델에서 노이즈

### `scripts/`

**Dos**
- 새 분석 step → 새 `.py` 파일 + `run_all.py` 끝에 추가 호출
- `plc_engine/` 안의 새 strategy → 새 파일 추가 (`engine.py` 직접 수정 X)
- Snowflake 쿼리 추가 → `queries/` 에 새 SQL 파일

**Donts**
- ❌ `ai_sales_loss_v2_legacy.py` 부활 — V3 만 사용
- ❌ `seed_users.py` 부활 — 단일 운영자
- ❌ `plc_engine/engine.py` 의 PLC 학습 알고리즘 임의 변경 — 발주 예측 신뢰도 와해
- ❌ 다른 브랜드의 weekly_raw 데이터를 본 fork 에서 처리 — 단일 브랜드 강제

### `data/`

**Dos**
- `data/plc/{brand}_{type}_plc_forecast_standard.csv` 재생성 (`build_plc_standard.py` 통해). 예: `mlb_fw_*`, `discovery_ss_*`. 경로는 `config_loader.get_plc_forecast_path()` 가 brand + targetSeason 의 type 으로 자동 도출.
- `data/user-storage/` 본인 사물함 reset (UI 우상단 Reset 또는 `rm -rf`)

**Donts**
- ❌ `data/production/order_ai.duckdb` 직접 SQL write — `run_all.py` 의 6번째 step (`dump_to_duckdb.py`) 가 baseline JSON 으로부터 재생성
- ❌ `data/` 안의 어떤 파일도 git commit — `.gitignore` 처리됨

### `public/`

**Dos**
- `brand_config.json` 의 임계값 / sizeOrder / subSeasonCutoff 조정
- `color_mapping.json` 새 컬러코드 추가
- `item_nm_map.json` — 전 브랜드 공통 ITEM 코드 → 한글명 매핑. 신규 ITEM 추가 시 갱신 (PLC 빌드 시 `build_plc_standard.py` 가 적용)
- `plc_engine_config.json` — 신규 시즌 등록 (`seasons` 영역) 또는 brand 별 `plc_exclude_prods` 조정

**Donts**
- ❌ `brand_config.json` 의 `brand` 필드를 `.env` 의 `BRAND` 와 다르게 → `RuntimeError`

---

## 3. 변경 후 반드시 돌릴 검증

작업 종료 / PR 시 다음 통과 필수:

```bash
# (1) 백엔드 정적 import + 부팅 검증
PYTHONPATH=. .venv/bin/python -c "import server.api; print('routes:', len(server.api.app.routes))"

# (2) 프론트 빌드
cd apps/lite && npm run build

# (3) 백엔드 헬스체크
.venv/bin/uvicorn server.api:app --port 8000 &
sleep 3
curl -fs http://localhost:8000/api/health | grep -q '"ok"' && echo "✅ health"
curl -fs http://localhost:8000/openapi.json | python3 -c "import sys, json; print(len(json.load(sys.stdin)['paths']), 'endpoints')"

# (4) Smoke test (Snowflake 연결 변경 시)
.venv/bin/python -m pytest smoke_test.py -v
```

3개 모두 통과 = 최소 안전성 확보.

> **더 강한 검증** (장기 TODO): Pydantic contract test + 골든 데이터셋 회귀. 현재 미구현.

---

## 4. 데이터 컨벤션 — 현재 상태

| 위치 | 현재 표기 | 비고 |
|---|---|---|
| `recommendations[].class2` vs `new_class2` | OR fallback 패턴 잔존 (`rec.class2 || rec.new_class2`) | 통일 작업은 contract test 갖춘 후 |
| `추천발주량` (한글) vs `confirmed_qty` (영문) | 혼재 | 동일 — 통일 작업 보류 |
| Dashboard JSON: flat (`hit`/`normal`/`shortage`/`risk`) | 프론트가 받자마자 `success/failure` 중첩으로 변환 | 백엔드 단일 구조로 통일 권장 (장기) |

**작업 가이드**: 새 코드 추가 시 **새 fallback / 새 한글 키 / 새 변환 로직** 만들지 마세요. 통일 작업이 어려워집니다.

---

## 5. Karpathy-Inspired 코딩 가이드라인

### Think Before Coding
- 가정은 명시. 불확실하면 질문.
- 여러 해석 가능 시 옵션 제시. 임의 선택 X.
- 더 단순한 방법이 있다면 그렇게 말하기.

### Simplicity First
- 요청 문제를 푸는 **최소 코드**. 추측성 기능 X.
- 일회용 코드의 추상화 X. "유연성" 도 요청 시에만.
- 200줄 짜놓고 50줄로 가능했으면 다시 쓰기.

### Surgical Changes
- 변경한 코드의 **직접 이웃**만 손대기. 인접 코드 / 주석 / 포맷팅 "개선" 금지.
- 기존 스타일 따르기. 본인이 다르게 할 거라도.
- 변경 후 생긴 dead import / 변수만 정리. 사전 dead code 는 의뢰 없이 건드리지 X.

**테스트**: 변경된 모든 줄이 의뢰의 직접 결과인가? 그렇지 않으면 surgical 위반.

### Goal-Driven Execution
"검증" 단계가 명시되지 않은 작업은 위험:
- "검증 로직 추가" → "잘못된 입력 테스트 작성 → 통과시키기"
- "버그 수정" → "버그 재현 테스트 작성 → 통과시키기"

위 §3 "검증 명령" 을 success criterion 으로 사용.

---

## 6. 잘 작동하는 패턴 예시

### "예산 천장 ceiling 계산 방식을 우리 팀 기준으로 변경"

✅ 좋은 접근:
```python
# server/services/order_calc.py 끝부분에 추가:
def apply_budget_and_color_v2_my_team(...):
    """우리 팀 ceiling 로직 — 기존 함수는 그대로 두고 새 함수 추가."""
    ...

# server/routers/lite.py 에서 분기 (또는 .env 의 BUDGET_STRATEGY 환경변수로):
if os.getenv("BUDGET_STRATEGY") == "my_team":
    result = apply_budget_and_color_v2_my_team(...)
else:
    result = apply_budget_and_color(...)
```

❌ 나쁜 접근:
- 기존 `apply_budget_and_color` 함수 본문 수정 (다음 시즌 회귀 시 비교 불가)

### "Step 4 추천 화면에 우리 팀 전용 컬럼 1개 추가"

✅ 좋은 접근:
- `apps/lite/src/components/OrderSuggest.jsx` 의 테이블 렌더 부분에 surgical 추가
- 백엔드 응답 키가 이미 있으면 거기서 읽음. 없으면 백엔드 surgical 추가

❌ 나쁜 접근:
- `OrderSuggest.jsx` 를 전체 리팩토링하면서 추가

---

## 7. 자가 점검 체크리스트

작업 종료 전 한 번 더:

- [ ] §3 검증 명령 3개 모두 통과
- [ ] 변경 파일 목록이 의뢰의 직접 결과인가 (surgical)
- [ ] §1 의 🔴 "절대 금지" / "부활 X" 패턴 위반 없는가
- [ ] §4 의 혼재 컨벤션에 **새 fallback / 새 한글 키** 추가 안 했는가
- [ ] 새 환경변수 추가 시 `.env.example` 반영
- [ ] 새 npm/pip 의존성 추가 시 `package.json` / `requirements.txt` 반영
- [ ] git commit 시 `.env` / `data/` / `output/` 안 들어갔는가 (`git status` 확인)

---

> **북극성 문장**: "AX팀은 인계 시점의 동작을 보장한다. 그 이후 본 fork 의 운영은 사업부의 자율과 책임이다."
