# TODO — order-ai-share

> 본 fork 의 진행 중/보류 항목. AX팀 인계 전 + 인계 후 양쪽 추적.

---

## 🔴 인계 전 잊으면 안 되는 보류 항목

### #2. requirements.txt 슬림화
- **상태**: 1차 슬림화 완료 — `anthropic`, `openai`, `httpx` 제거 (전체 .py 0 import 정적 확인). 부수 작업: `smoke_test.py::test_critical_imports` 의 `import httpx` 도 함께 제거.
- **추가 슬림화 대상 없음** — 나머지 패키지는 모두 실사용 확인:
  - `matplotlib` / `seaborn`: `scripts/main.py` 가 차트 생성에 실사용 (37건). 이전 가정("미사용")은 오류였음.
  - `python-multipart`: FastAPI `UploadFile` 사용 (`server/routers/lite.py`)
- **macOS fresh venv 풀 빌드 검증 (2026-05-20)** — `/tmp/order-ai-share-cleantest/` 에서 fresh venv 만들어 `pip install -r requirements.txt` PASS (58 packages). 슬림화 제거 패키지 (`anthropic`/`openai`/`httpx`) 부재 재확인. `PYTHONPATH=. .venv/bin/python -c "import server.api"` → 23 routes. 발견사항: `boto3`/`botocore` 는 `snowflake-connector-python` 의 transitive — 제거 불가, non-issue.
- **잔여 검증 (운영자 자체 실행)**: Ubuntu 22.04 Docker 풀 빌드, Windows WSL2 — `/onboard` 가 OS 자동감지 + Linux/WSL/Windows 분기 안내 포함.

### #3. Phase 9 — Clean install verification
- **상태**: **부분 PASS (2026-05-20, macOS fresh venv `/tmp/order-ai-share-cleantest/`)** — 케이스 3/4/5 통과. 잔여 케이스는 운영자가 `/onboard` 호출로 자체 실행 (cowork 의존 X).
- **검증 환경**:
  - macOS (운영자 macOS 25.3, Python 3.12, Node v25.3) — ✅ 부분 검증 완료
  - Ubuntu 22.04 Docker container — 🔁 `/onboard` 가 Linux/WSL 분기 안내 (자동감지 + `apt install` 명령)
  - Windows WSL2 — 🔁 `/onboard` 가 Windows native 감지 시 WSL2 안내 후 종료, WSL2 안에선 Linux 경로
- **케이스별 결과** (v3.1 SSO 허용 반영):

| # | 케이스 | 결과 |
|---|---|---|
| 1 | Service Account 모드 정상 `.env` → PASS | 🔁 `/onboard` 흡수 — Stage 3 의 옵션 B 선택 + Stage 4 `.env` 작성 안내 + Stage 6 진단표 |
| 2 | SSO 모드 (`SNOWFLAKE_AUTH=externalbrowser`) 정상 `.env` → PASS + INFO 메시지 | 🔁 `/onboard` 흡수 — Stage 3 의 옵션 A (기본/권장) + Stage 5 의 브라우저 팝업 안내 |
| 3 | `--skip-snowflake` 모드 → PASS (`.env` 없어도 OK) | ✅ PASS — `=== SETUP COMPLETE: PRE-MEETING ===`, 58 packages installed, smoke skip. `/onboard` Stage 3 의 옵션 C 경로로 재현 가능. |
| 4 | `.env` 없는데 skip 없이 실행 → fail with 안내 | ✅ PASS — step 4 에서 exit 1 + ".env file not found" + .env.example 복사 안내 + `--skip-snowflake` 옵션 안내. `/onboard` Stage 6 진단표가 동일 안내 매칭. |
| 5 | 잘못된 Snowflake password → smoke_test fail | ✅ PASS — step 5 의 smoke_test 11 tests 중 9 PASSED, 2 FAILED (`TestSnowflakeConnectivity::test_select_one`, `test_brand_data_access`). 에러 명확: `HttpError 290404: 404 Not Found: fake.account.invalid.snowflakecomputing.com`. `/onboard` Stage 6 의 `HttpError 290404` 패턴이 `SNOWFLAKE_ACCOUNT` 오타 안내. |
| 6 | SSO 헤드리스 환경 → 브라우저 timeout fail | 🔁 `/onboard` 흡수 — Stage 6 진단표가 `Could not connect to.*externalbrowser` 패턴 시 옵션 B (Service Account) 전환 권유 |

- **수동 UI walkthrough** (5 step 데이터 표시 + console error 0): 🔁 `/server-start` 스킬 흡수 — 백엔드/프론트 기동 + 화면 자동 띄우기 + 5 step 데이터 표시 + console error 점검 가이드

---

## 🟢 인계 후 (장기, 사업부 자율)

### A. Contract test 도입 (현재 미구현)
- **목적**: JSON 응답 키 변경 시 자동 차단 (위 CLAUDE.md §4 의 혼재 컨벤션 통일 작업의 안전망)
- **방향**: Pydantic 스키마로 백엔드 응답 동결 + 골든 데이터셋 + pytest contract test
- **착수 조건**: 사업부가 운영 안정화 후, 변경 빈도가 늘어나면

### B. 위험 신호 정리 (CLAUDE.md §4 의 혼재 컨벤션)
- **#1 `recommendations[].class2` vs `new_class2`**: OR fallback 통일
- **#2 한글 키 vs 영문 키**: 명명 규약 통일
- **#3 Dashboard JSON flat vs 중첩 변환**: 백엔드 단일 구조로 통일
- **착수 조건**: 위 A (contract test) 갖춘 후

### C. 사업부 커스터마이즈용 Claude Code 스킬 (별도 패키지)
- **목적**: 사업부가 `/skills` 로 설치해 쓸 가이드 스킬
- **착수 조건**: 첫 fork 사업부의 실제 사용 경험 피드백 후

---

