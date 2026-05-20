# Onboarding Checklist — order-ai-share

> 사업부 단일 운영자 인계 시 사용. AX팀 + 운영자 양쪽이 함께 체크.
>
> 미팅 1회 (~50분) 가 가정. 인계 후 severance.

---

## Pre-meeting (미팅 전에 운영자가 단독으로)

| 체크 | 항목 | 비고 |
|---|---|---|
| ☐ | Python 3.11+ 설치 확인 (`python3 --version`) | macOS: `brew install python@3.11` |
| ☐ | Node 18+ 설치 확인 (`node --version`) | macOS: `brew install node@18` |
| ☐ | Git 설치 확인 (`git --version`) | — |
| ☐ | Claude Code 구독 active | 셀프 트러블슈팅 1순위 도구 |
| ☐ | GitHub 본인 계정 → AX팀에 username 공유 | repo collaborator invite 받기용 |
| ☐ | GitHub 초대 수락 + `git clone` 성공 | `git clone https://github.com/Judyjieunb/order-ai-share.git` |
| ☐ | `./setup.sh --skip-snowflake` 단독 실행 → `=== SETUP COMPLETE: PRE-MEETING ===` 확인 | venv + npm install 미리 |

체크 끝나면 미팅 진입 준비 완료. 못 한 항목이 있으면 미팅에서 지원.

---

## Meeting Flow (대략 50분)

### 0–5분: 환경 확인

| 체크 | 항목 |
|---|---|
| ☐ | 운영자의 Pre-meeting 체크 결과 공유 |
| ☐ | 본 fork 의 아키텍처 (Snowflake → DuckDB → API → UI) 5분 설명 |
| ☐ | severance 정책 ([SUPPORT.md](../SUPPORT.md)) 확인 |

### 5–10분: Snowflake 인증 모드 결정 + Credential 전달

먼저 두 모드 중 선택:

| 체크 | 항목 |
|---|---|
| ☐ | 인증 모드 결정 — **옵션 A (SSO, 권장)** 또는 **옵션 B (service account)** |

#### 옵션 A: SSO (externalbrowser)

| 체크 | 항목 |
|---|---|
| ☐ | IT 가 운영자 본인 Snowflake account 의 role 에 본 브랜드 grant 부여 (이미 부여돼있으면 skip) |
| ☐ | AX팀이 Snowflake account/warehouse/database/schema 값 공유 (회의 중 화면 표시 OK — password 없으니 보안 부담 낮음) |
| ☐ | 운영자가 `cp .env.example .env` 후 SSO 모드로 채움 (`SNOWFLAKE_AUTH=externalbrowser` 추가) |

#### 옵션 B: Service Account + Password

| 체크 | 항목 |
|---|---|
| ☐ | AX팀이 **1Password share link** 생성 |
| ☐ | 운영자가 Slack DM (본인 한정) 으로 link 수신 |
| ☐ | 운영자가 link 열어서 값 확인 (열람 1회 후 자동 만료) |
| ☐ | 운영자가 `cp .env.example .env` 후 service account 값 채움 (password 포함) |

#### 양쪽 공통

| 체크 | 항목 |
|---|---|
| ☐ | `.env` 가 `.gitignore` 대상임을 확인 (`git status` 에 안 보여야 함) |
| ☐ | `public/brand_config.json` 의 `brand` 필드가 `.env` 의 `BRAND` 와 일치 확인 |

### 10–15분: 풀 셋업 검증

| 체크 | 항목 |
|---|---|
| ☐ | `./setup.sh` 실행 → `=== SETUP COMPLETE: PASS ===` 확인 |
| ☐ | smoke_test.py 의 9개 테스트 모두 PASS |
| ☐ | 실패 시 위 pytest 출력을 Claude Code 에 붙여넣어 트러블슈팅 (운영자 본인 시도, AX팀 관전) |

### 15–25분: 첫 회 PLC 빌드

| 체크 | 항목 |
|---|---|
| ☐ | `.venv/bin/python scripts/plc_engine/build_plc_standard.py` 실행 |
| ☐ | (cold-start 브랜드) AX팀의 seed PLC 를 `data/plc/{brand}_{type}_plc_forecast_standard.csv` (본인 환경 brand/type) 에 배치 |
| ☐ | Drift report 해석 — `<5/5-30/>30` 분기별 의미 ([PLC_GUIDE.md](./PLC_GUIDE.md) 참고) |
| ☐ | Coverage report 의 fallback 카운트 확인 |

### 25–40분: 파이프라인 + UI 실행

| 체크 | 항목 |
|---|---|
| ☐ | `.venv/bin/python scripts/run_all.py` 실행 (6 step, 3–10분 소요) |
| ☐ | `data/production/order_ai.duckdb` 생성 확인 (6번째 step `dump_to_duckdb.py` 산출) |
| ☐ | `public/*.json` 출력물 5개 확인 (`dashboard_data`, `season_closing_data`, `past_styles_data`, `style_mapping_data`, `size_assortment_data`) |
| ☐ | 백엔드 기동 (`.venv/bin/uvicorn server.api:app --port 8000`) |
| ☐ | `curl http://localhost:8000/api/health` → `{"status":"ok"}` |
| ☐ | 프론트엔드 기동 (`cd apps/lite && npm run dev`) |
| ☐ | 브라우저 → Step 1 ~ 5 데이터 표시 확인 |

### 40–50분: 운영 가이드 + Q&A

| 체크 | 항목 |
|---|---|
| ☐ | 다음 시즌 데이터 도착 시 재실행 흐름 ([SETUP.md](../SETUP.md) §10) |
| ☐ | PLC 재생성 시점 ([PLC_GUIDE.md](./PLC_GUIDE.md) "언제 재생성?") |
| ☐ | 셀프 트러블슈팅 우선순위 (Claude Code → 문서 → git history) |
| ☐ | AX팀 contact 정책 (cold-start seed PLC 또는 보안 사고에 한정) |
| ☐ | 운영자 Q&A |

---

## Post-meeting (운영자 단독 확인)

미팅 후 며칠 내:

| 체크 | 항목 |
|---|---|
| ☐ | 단독 재실행 (`run_all.py` + `uvicorn` + `npm run dev`) 가능 |
| ☐ | UI 의 Step 1 ~ 5 한 번씩 클릭해보고 데이터 정상 표시 |
| ☐ | Step 3 GO list 업로드 → Step 4 확정 흐름 1회 따라하기 |
| ☐ | `.env` 백업 (1Password 본인 vault 에 보관) |
| ☐ | 본 디렉토리를 본인 백업 도구에 등록 (`data/` `output/` 제외) |

---

## 인계 완료 시그널

다음 모두 ☐ → ☑ 면 severance 적용:

- ☐ 운영자가 위 모든 체크리스트 통과
- ☐ AX팀이 인계 완료 confirm
- ☐ `.env` 가 운영자 손에 있고 1Password 본인 vault 에 백업됨
- ☐ 운영자가 단독으로 다음 시즌 운영 가능하다고 의사 표명

이후 AX팀의 정기 지원 없음. 셀프 서비스 + Claude Code 1순위.
