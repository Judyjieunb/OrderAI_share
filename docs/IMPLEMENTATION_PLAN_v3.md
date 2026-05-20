# order-ai-share — Implementation Plan v3

> **Status**: v3 (Post-Cowork Refine — §4 8 items + (나) self-generated PLC pivot)
> **Repo target**: `order-ai-share` (was `order-ai-standalone` in v2)
> **Created**: 2026-05-18 (Cowork session)
> **Predecessor**: v2 (Post-Critic ITERATE, 14 issues resolved)
> **Type**: Brownfield extraction → standalone deliverable (severance model)

---

## What changed from v2 (top of doc)

This v3 supersedes v2. Major shifts:

1. **PLC baseline model**: 공유 표준 (MLB+Discovery 평균) → **자기 브랜드 자체 PLC 생성**. 모든 fork 가 자기 raw 데이터로 PLC 표준 곡선을 만든다. Phase 0 가 단순해지고 graduated decision tree 가 사라진다.
2. **Repo 이름**: `order-ai-standalone` → `order-ai-share`.
3. **`open_db()` 버그 수정**: v2 의 user_storage 스니펫이 `open_db(brand)` 로 호출 — 실제 `@contextmanager` 이므로 `with open_db() as con:` 패턴 사용.
4. **`is_stale()` + StaleWarning.jsx 양쪽 삭제**: fork 는 manual pipeline 운영이라 stale 개념 자체 노이즈.
5. **setup.sh `--skip-snowflake` 모드** + SSO(`externalbrowser`) 차단 검증.
6. **`/api/run-pipeline` 5분 cooldown** 추가.
7. **`.env` credential 전달 방식 명시**: 1Password share 1순위, GPG encrypted file 2순위.
8. **Open Question 1 (repo name)** 재해결: share.
9. **Open Question 5 (PLC timing)** 재해결: self-gen 으로 변경.
10. **retrain 검증**: 드리프트 리포트 (이전 PLC vs 새 PLC 의 MAPE) 추가.

Full v3 revision log at bottom of doc.

---

## RALPLAN-DR Summary

### Principles (5)

1. **Fail Fast on Misconfig** — setup.sh must halt with clear error + next-action on first missing credential or broken dependency. No silent fallback, no partial success.

2. **Zero F&F-Internal Infrastructure Dependencies** — The fork must operate without S3, DCS AI portal, EC2, or any F&F internal infrastructure at runtime. All data flows through local DuckDB + Snowflake only. (Snowflake is an allowed external dependency.) `[I13]`

3. **Single Brand Self-Sovereignty** — Each fork is one brand's autonomous instance. Single config, single PLC (derived from own data), single pipeline run. No shared cross-brand assets at runtime. `[v3-#1]`

4. **Operator-Friendly Errors Over Auto-Recovery** — Error messages should be specific enough for Claude Code to troubleshoot. No auto-healing that masks root causes.

5. **Severance-Ready Artifact** — After delivery, the repo must be fully self-contained. No lingering imports, dead references to removed modules, or broken test paths.

### Decision Drivers (Top 3)

1. **Brand division receives broken artifact = trust collapse** — If setup.sh fails or pipeline errors on first run, the single onboarding meeting is wasted and support model collapses. The harness must work on first try.

2. **S3/Auth removal creates cascading breakage** — `user_storage.py` is the backbone of Lite's data persistence layer. Ripping out S3 requires a complete local-storage replacement without breaking the 13-endpoint API surface.

3. **Self-generated PLC sufficiency** — Each brand must have **>=2 complete seasons of weekly_raw data** to bootstrap their own PLC. Brands below this threshold need AX-team seed (1회). `[v3-#1]`

### Viable Options (per Open Question)

#### OQ1: New GitHub Repo Name

| Option | Pros | Cons |
|--------|------|------|
| **A: `order-ai-share`** ★ | "share" 가 사업부와의 공유/협업 모델을 직관적으로 전달. 사내 기존 용어와 정합 | "share" 가 동기화 가능성 암시할 수 있음 — README/SUPPORT에서 severance 명시 필요 |
| B: `order-ai-standalone` | severance 정책 직설적 표현 | 사업부 관점에서 차갑게 느껴질 수 있음 |
| C: `order-ai-brand` | 단일 브랜드 운영 강조 | 모호 — 브랜드팀 버전 vs 상품 브랜드 |

**Resolved: A (`order-ai-share`)** — 사용자 결정 (v3 refine).

#### OQ2: setup.sh Language (Pure Bash vs Python Click CLI)

| Option | Pros | Cons |
|--------|------|------|
| A: Pure Bash | Zero Python dependency at setup time, universally available on macOS/Linux | Windows compat requires WSL/Git Bash |
| B: Python Click CLI | Rich UX | Chicken-and-egg: needs Python first |
| **C: Hybrid (bash bootstrap → Python validator)** ★ | Bash handles venv/npm install, Python for Snowflake validation | Two languages to maintain |

**Resolved: C (Hybrid)** — `setup.sh` handles idempotent env setup, then invokes `python -m pytest smoke_test.py` for validation.

#### OQ3: Smoke Test Framework

| Option | Pros | Cons |
|--------|------|------|
| **A: pytest** ★ | Industry standard, rich assertions, fixtures, CI-friendly | Requires pytest in requirements.txt (trivial) |
| B: Bash assert | No extra dependency | Poor error messages |
| C: Custom Python script | No framework dependency | Reinventing wheel |

**Resolved: A (pytest)** — Claude Code understands pytest output perfectly for troubleshooting.

#### OQ4: Sample Data Bundling

| Option | Pros | Cons |
|--------|------|------|
| **D: None (Snowflake-only)** ★ | Forces real connection from day 1, simplest repo | No offline demo |
| A: Git LFS | Always available on clone | Setup complexity, repo bloat |
| B: GitHub Release attachment | Clean separation | Extra step |
| C: Presigned URL | No Git bloat | URL expires |

**Resolved: D (None)** — operators have Snowflake credentials from 본 IT. DuckDB baseline generated from Snowflake on first pipeline run.

#### OQ5: PLC Standard — Origin

| Option | Pros | Cons |
|--------|------|------|
| ~~Cross-brand average (MLB+Discovery)~~ | One-time AX work | Item mismatch, graduated decision tree complexity, AX maintenance burden |
| **Self-generated (own brand history)** ★ `[v3-#1]` | 100% own-fit, severance-aligned, simpler Phase 0 | Requires >=2 seasons of clean data; AX manual seed for cold-start brands |

**Resolved: Self-generated** — fork 의 본질(브랜드 자치)에 정합. Phase 0 가 단순해지고 graduated decision tree 가 사라진다. Cold-start 케이스만 AX 수동 seed 1회.

#### OQ6: brand_config.json Single-Brand Enforcement

| Option | Pros | Cons |
|--------|------|------|
| A: Environment variable | Simple override | Doesn't prevent multi-brand JSON |
| **B: Schema validation in config_loader** ★ | Catches misconfig at pipeline start | Requires config_loader modification |
| C: UI disable | Prevents user confusion | Frontend-only |
| D: B + C combined | Defense in depth | Two enforcement points |

**Resolved: B** — Add `SINGLE_BRAND_MODE=true` check in `config_loader.py`. When enabled, `get_brand()` validates brand_config.json has exactly one brand entry. UI naturally follows.

---

### Pre-mortem (3 Scenarios) — DELIBERATE MODE

#### Scenario 1: "Silent S3 Fallback Ghost"

- **Failure mode**: `s3_client.py` 제거 후 `user_storage.py` 나 `lite.py` 가 트랜시티브 import 로 S3 함수 호출. 특정 endpoint (예: POST `/confirmed-mapping`) 진입 시에만 에러 출현, setup/smoke test 에서는 안 잡힘.
- **Detection**: `grep -r "s3_client\|presigned\|S3_BUCKET\|S3_API_KEY"` — 전 Python 파일. `server/routers/lite.py` 부터 import chain 정적 분석.
- **Mitigation**: Phase 3 sub-step ordering 강제 — consumer rewrite 먼저 → grep verify → THEN s3_client.py 삭제. Phase 9 integration test 는 13개 endpoint 전수 검증.

#### Scenario 2: "Snowflake Permission Scope Mismatch"

- **Failure mode**: 본 IT 가 제공한 service account 가 `SELECT 1` 은 통과 (smoke test pass) 하지만, 브랜드별 테이블/뷰에 `SELECT` 권한 없음. 첫 풀 파이프라인에서 cryptic 에러.
- **Detection**: Smoke test Level 2 = `SELECT 1` + brand-specific parameterized query: `SELECT COUNT(*) FROM FNF.PRCS.DB_SCS_W WHERE BRD_CD = %s AND SESN = '25F'`. BRAND_TO_BRD_CD 매핑 (MLB→M, Discovery→X, Duvetica→V, MLBKids→I, Sergio→ST). `[I2]`
- **Mitigation**: SETUP.md 에 필요 Snowflake roles/grants 명시. 온보딩 미팅 체크리스트 포함.

#### Scenario 3: "Insufficient Historical Data" `[v3-#1]`

- **Failure mode**: 신규 브랜드(예: 최근 인수) 가 weekly_raw 데이터 <2 시즌. `build_plc_standard.py` 실행 시 데이터 부족으로 의미 있는 표준 PLC 못 만듦. 출시 강행하면 fallback 곡선만 사용 → 예측 무의미.
- **Detection**: `build_plc_standard.py` 진입 시 데이터 sufficiency 게이트:
  - Snowflake 에서 해당 브랜드의 시즌 카운트 조회
  - <2 시즌이면 명확한 에러 + 옵션 안내 ("AX팀에 seed PLC 요청하세요")
- **Mitigation**: AX팀이 manual seed PLC 1회 제공 가능 (cold-start 브랜드 전용). 사업부는 첫 시즌 운영 → 누적 데이터로 자체 PLC 전환.

---

### Expanded Test Plan — DELIBERATE MODE

#### Unit Tests

| Target | Test Cases | Location |
|--------|-----------|----------|
| `config_loader.py` single-brand mode | Valid single brand, multi-brand rejection, missing brand field, empty config, **BRAND env vs brand_config.json mismatch** `[I8]` | `tests/unit/test_config_single_brand.py` |
| `gt_builder.py` (new) | weekly_raw → GT derivation, ADJ_* = original copy, empty input handling | `tests/unit/test_gt_builder.py` |
| `build_plc_standard.py` (new) `[v3-#1]` | 출력 스키마 = `{brand}_{type}_plc_forecast_standard.csv` (brand × season_type 분리), sufficiency 게이트 (>=2 시즌), 드리프트 리포트 출력 | `tests/unit/test_build_plc.py` |
| `server/db.py` get_db | Missing file error, valid connection, read-only enforcement | `tests/unit/test_db.py` |
| Permissions stub | Always returns configured brand, no HTTP header dependency | `tests/unit/test_permissions_stub.py` |
| Local user_storage `[v3-#3]` | File read/write/delete, idempotent delete, metadata attachment. `with open_db() as con:` 패턴 사용 검증 | `tests/unit/test_local_storage.py` |

> v3 변경: `get_pipeline_version` / `is_stale` 테스트 제거 — stale 개념 자체 삭제 (v3-#4).

#### Integration Tests

| Target | Test Cases | Location |
|--------|-----------|----------|
| Full pipeline (Snowflake → DuckDB → JSON) | `run_all.py` produces valid DuckDB + public JSONs | `tests/integration/test_pipeline.py` |
| V3 PLC + self-generated PLC + own GT | End-to-end PLC prediction with self-generated standard | `tests/integration/test_plc_self_gen.py` `[v3-#1]` |
| API server (all 13 Lite endpoints) | Each endpoint returns expected shape, no auth barrier | `tests/integration/test_lite_api.py` |
| Config → pipeline → frontend data | brand_config → scripts → DuckDB → API → JSON matches frontend expectations | `tests/integration/test_data_flow.py` |
| **Brand config consistency** `[I8]` | BRAND env + brand_config.json disagree → RuntimeError | `tests/integration/test_config.py` |
| **PLC sufficiency gate** `[v3-#1]` | <2 seasons 입력 → 에러 + seed PLC 안내 메시지 | `tests/integration/test_plc_sufficiency.py` |
| **Pipeline cooldown** `[v3-#6]` | 연속 호출 시 두 번째 요청 5분 내 거부 | `tests/integration/test_pipeline_cooldown.py` |

#### E2E Tests

| Target | Method | Verification |
|--------|--------|-------------|
| Clean install simulation (Ubuntu) | Fresh Docker container (Ubuntu 22.04 + Python 3.11 + Node 18) | `setup.sh` exit 0, smoke_test PASS |
| **macOS clean install** `[I12]` | Manual or scripted verification on macOS (Homebrew Python/Node) | Document manual steps, verify `setup.sh` exit 0 |
| Pre-meeting mode `[v3-#5]` | `./setup.sh --skip-snowflake` 실행 | venv/npm 설치 PASS, Snowflake 스킵 표시, exit 0 |
| First-run PLC generation `[v3-#1]` | After setup, `python scripts/plc_engine/build_plc_standard.py` | `data/plc/{brand}_{type}_plc_forecast_standard.csv` 생성 (예: `mlb_fw_*`) |
| Pipeline first-run | After PLC build, `python scripts/run_all.py` completes | DuckDB file created, all JSON outputs present |
| Frontend serves | `npm run dev` after pipeline | Browser shows Step 1-5 with data |

#### Observability

| Signal | Implementation |
|--------|---------------|
| setup.sh step-by-step progress | `echo "[1/5] Creating Python venv..."` with step counter |
| setup.sh PASS/FAIL exit | Last line: `echo "=== SETUP COMPLETE: PASS ==="` or `echo "=== SETUP FAILED at step N: {reason} ==="` with exit 1 |
| smoke_test detailed output | pytest verbose mode + custom markers per check |
| Pipeline run summary | `run_all.py` prints elapsed time per step + total + sufficiency check result |
| PLC drift report `[v3-#7]` | `build_plc_standard.py` 출력: 기존 PLC 대비 MAPE (없으면 첫 생성으로 표시) |
| Onboarding meeting checklist | `docs/ONBOARDING_CHECKLIST.md` with checkboxes for IT + operator |

---

## Implementation Phases

### Phase 0: Pre-work (GT Generator + PLC Build Tool) `[v3-#1]`

**Goal**: Create the tool that brand divisions will run as their first step. No shared MLB+Discovery extraction — every brand bootstraps from own data.

**Files to create (in main repo first, then copy to fork)**:
- `scripts/plc_engine/gt_builder.py` — NEW: weekly_raw → GT derivation (ADJ_* = SC original copy)
- `scripts/plc_engine/build_plc_standard.py` — NEW: 자기 브랜드 raw 데이터로 PLC 표준 곡선 생성

**Actions**:

1. Implement `gt_builder.py`:
   - Input: `weekly_raw.xlsx` (same format as `weekly_analysis.py` input)
   - Output: GT DataFrame with columns matching PLC engine's expected input
   - `ADJ_SALE_QTY` = `SALE_QTY` (original, no adjustment — brand division's own ground truth)
   - Handles: missing weeks (fill 0), multiple colors (aggregate to style level)

2. Implement `build_plc_standard.py` `[v3-#1] [v3-#7]`:
   - Input: 사업부의 누적 weekly_raw (Snowflake → DataFrame)
   - **Sufficiency gate**: 시즌 카운트 <2 → 명확한 에러 + AX팀 seed 안내 메시지로 종료
   - Output: `data/plc/{brand}_{type}_plc_forecast_standard.csv` — brand × season_type 분리. 경로는 `config_loader.get_plc_forecast_path()` 가 `.env::BRAND` + `brand_config.json::targetSeason` 으로 자동 도출. item-level lifecycle curves 스키마는 동일.
   - **Drift report** `[v3-#7]`: 같은 (brand, type) 의 기존 csv 가 있으면 새 PLC vs 기존 PLC 의 평균 MAPE 계산:
     - 5% 미만: "표준과 거의 동일 — 재생성 효과 미미. 출시 보류 권장" (warning, not failure)
     - 5–30%: "정상 적응 — 새 표준 사용" (info)
     - >30%: "큰 차이 — raw 데이터 검증 권장" (warning + 자세한 비교 csv 별도 출력)
   - Coverage report: "X items processed, Y items insufficient data → fallback curve"

3. **NO MLB+Discovery extraction step** — v2 의 이 단계는 v3 에서 삭제. 각 fork 는 own data 로 자체 생성.

**Verification**:
- [ ] `gt_builder.py` unit tests pass (empty input, single style, multi-color aggregate)
- [ ] `build_plc_standard.py` unit tests pass (schema validation, sufficiency gate, drift report)
- [ ] Sufficiency gate: <2 시즌 입력 → RuntimeError("최소 2 시즌의 weekly_raw 데이터 필요. AX팀에 seed PLC 요청하세요: ax-team@fnf.co.kr")
- [ ] Drift report 출력 형식 확인 (3 단계 분기 정상 동작)

**Effort**: 1.5-2 days (v2 의 2-3 days 보다 축소 — MLB+Discovery 추출 작업 제거 효과)
**Dependencies**: None (can start immediately)

---

### Phase 1: Create New Repo + Initial Import

**Goal**: Stand up the new repo with a clean subset of the main repo's code. `[I1]` NEW minimal `server/api.py` 작성 (main 의 api.py 복사 금지).

**Actions**:
1. Create private GitHub repo: `Judyjieunb/order-ai-share` `[v3-#2]`
2. Initialize with selective file copy (NOT git subtree — clean break):
   ```
   order-ai-share/
   ├── scripts/
   │   ├── main.py
   │   ├── weekly_analysis.py
   │   ├── ai_sales_loss_v3.py
   │   ├── step4_integration.py
   │   ├── generate_size_data.py
   │   ├── run_all.py
   │   ├── dump_to_duckdb.py
   │   ├── config_loader.py
   │   ├── snowflake_client.py
   │   └── plc_engine/
   │       ├── __init__.py
   │       ├── broken.py
   │       ├── builders.py
   │       ├── engine.py
   │       ├── predictor.py
   │       ├── preprocess.py
   │       ├── specs.py
   │       ├── utils.py
   │       ├── gt_builder.py            ← from Phase 0
   │       └── build_plc_standard.py    ← from Phase 0 (v3 신규명)
   ├── queries/                          ← [I11] SQL query files
   │   ├── d1_season_raw.sql
   │   ├── d2_weekly_raw.sql
   │   ├── d3_similarity_mapping.sql
   │   ├── d3_r2_similarity_gtm_image.sql
   │   └── d4_size_data.sql
   ├── server/
   │   ├── api.py                       ← [I1] NEW minimal file
   │   ├── db.py
   │   ├── routers/
   │   │   ├── __init__.py
   │   │   ├── lite.py
   │   │   └── shared.py
   │   ├── services/
   │   │   ├── __init__.py
   │   │   ├── color_allocation.py
   │   │   ├── color_helpers_duckdb.py
   │   │   ├── order_calc.py
   │   │   └── user_storage.py          ← Phase 3 rewrite
   │   ├── permissions.py               ← Phase 2 rewrite
   │   └── s3_client.py                 ← Phase 3 delete
   ├── apps/lite/                        ← full Vite project
   │   ├── src/                         ← StaleWarning.jsx 제외 (Phase 3 #4)
   │   ├── package.json
   │   ├── vite.config.js
   │   ├── tailwind.config.js
   │   └── postcss.config.js
   ├── public/
   │   ├── brand_config.json
   │   ├── plc_engine_config.json
   │   └── color_mapping.json
   ├── data/
   │   ├── plc/                          ← v3: 빈 폴더 (build_plc_standard.py 가 채움)
   │   │   └── .gitkeep
   │   └── production/                   ← DuckDB will be generated here
   ├── output/                           ← pipeline outputs
   ├── requirements.txt
   ├── .env.example
   ├── .gitignore
   └── README.md                         ← placeholder
   ```

3. **`[I1]` NEW minimal `server/api.py`** (~85 lines) — do NOT copy main repo's api.py. `[v3-#6]` 추가 — pipeline cooldown:

   ```python
   """
   FastAPI backend — Order AI Share (Lite-only).

   Minimal server: shared + lite routers only.
   No Full mode, no S3, no DCS AI auth.

   Run: uvicorn server.api:app --port 8000 --reload
   """

   import os
   import sys
   import subprocess
   import threading
   import time

   from dotenv import load_dotenv
   from fastapi import FastAPI, HTTPException
   from fastapi.middleware.cors import CORSMiddleware

   # config_loader access
   BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
   _SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
   if _SCRIPTS_DIR not in sys.path:
       sys.path.insert(0, _SCRIPTS_DIR)

   load_dotenv(os.path.join(BASE_DIR, ".env"))

   app = FastAPI(title="Order AI Share")

   # CORS
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
       allow_methods=["*"],
       allow_headers=["*"],
   )

   # --- Routers (shared + lite ONLY) ---
   from server.routers import shared as _shared_router   # noqa: E402
   from server.routers import lite as _lite_router        # noqa: E402
   app.include_router(_shared_router.router)
   app.include_router(_lite_router.router)

   # --- Pipeline trigger endpoint with cooldown [v3-#6] ---
   _pipeline_lock = threading.Lock()
   _pipeline_last_run: float = 0.0  # Unix timestamp
   _COOLDOWN_SECONDS = 5 * 60       # 5분

   @app.post("/api/run-pipeline")
   async def run_pipeline():
       """Run the analysis pipeline (scripts/run_all.py). Concurrency lock + 5min cooldown."""
       global _pipeline_last_run
       now = time.time()
       elapsed = now - _pipeline_last_run
       if elapsed < _COOLDOWN_SECONDS:
           remaining = int(_COOLDOWN_SECONDS - elapsed)
           raise HTTPException(
               status_code=429,
               detail=f"Pipeline cooldown 활성. {remaining}초 후 재시도 가능.",
           )
       if not _pipeline_lock.acquire(blocking=False):
           return {"status": "already_running"}
       try:
           _pipeline_last_run = now
           python = sys.executable
           result = subprocess.run(
               [python, os.path.join(_SCRIPTS_DIR, "run_all.py")],
               capture_output=True, text=True, cwd=BASE_DIR,
           )
           return {
               "status": "success" if result.returncode == 0 else "error",
               "returncode": result.returncode,
               "stdout": result.stdout[-2000:] if result.stdout else "",
               "stderr": result.stderr[-2000:] if result.stderr else "",
           }
       finally:
           _pipeline_lock.release()
   ```

4. Explicitly EXCLUDE from copy:
   - `server/routers/full.py` (Full mode only)
   - `server/production.py`, `server/production_lite.py` (EC2 production scripts)
   - `src/` (main Full frontend)
   - `apps/lite/Dockerfile`, `apps/lite/deploy.sh`, `apps/lite/docker-compose.yml`, `apps/lite/docker-entrypoint.sh`
   - `apps/lite/src/components/common/StaleWarning.jsx` `[v3-#4]`
   - `scripts/ai_sales_loss_v2_legacy.py`
   - `scripts/seed_users.py`
   - Root `Dockerfile`, `deploy.sh`, `docker-compose.yml`
   - `test/` (will create fresh test suite)
   - `.omc/`, `.claude/` (development tooling)

5. Create `.gitignore`:
   ```
   .env
   .venv/
   node_modules/
   data/production/*.duckdb
   data/plc/*.csv
   output/
   __pycache__/
   *.pyc
   apps/lite/dist/
   ```

6. Create `.env.example` `[I14]`:
   ```
   # Snowflake 연결 (본 IT 발급 service account)
   SNOWFLAKE_ACCOUNT=your_account.ap-northeast-2
   SNOWFLAKE_USER=svc_orderai_brand
   SNOWFLAKE_PASSWORD=
   SNOWFLAKE_WAREHOUSE=COMPUTE_WH
   SNOWFLAKE_ROLE=ORDERAI_READER
   SNOWFLAKE_DATABASE=FNF
   SNOWFLAKE_SCHEMA=PRCS
   # [v3-#5] SNOWFLAKE_AUTH 항목 추가 금지. password 사용 (자동). SSO/externalbrowser 는 헤드리스 환경 차단.

   # 운영 설정
   BRAND=DUVETICA
   SINGLE_BRAND_MODE=true
   DUCKDB_PATH=data/production/order_ai.duckdb
   ```

**Verification**:
- [ ] Repo created on GitHub (private)
- [ ] All files present in correct structure (including `queries/` `[I11]`)
- [ ] No `full.py`, `ai_sales_loss_v2_legacy.py`, deploy artifacts, `StaleWarning.jsx` in repo `[v3-#4]`
- [ ] `.gitignore` prevents credential/data leaks
- [ ] **NEW `server/api.py` only imports `shared` and `lite` routers — no `full`** `[I1]`
- [ ] **`/api/run-pipeline` cooldown 동작 검증** `[v3-#6]`
- [ ] `cd order-ai-share && .venv/bin/python -c "import server.api"` succeeds

**Effort**: 0.5 day
**Dependencies**: Phase 0 (gt_builder.py, build_plc_standard.py)

---

### Phase 2: Remove DCS AI Auth (Frontend + Backend)

**Goal**: Replace DCS AI embed auth with hardcoded single-user stub.

**Files modified**:
- `apps/lite/src/hooks/useDcsAuth.js` → REWRITE to always return local user
- `apps/lite/src/contexts/AuthContext.jsx` → SIMPLIFY (no role checking)
- `server/permissions.py` → REWRITE as passthrough stub
- `server/routers/lite.py` → Update Depends() to use stub

**Actions**:

1. **Frontend: `useDcsAuth.js`** → Replace with:
   ```javascript
   // Standalone mode: no DCS AI portal auth. Single user from .env/config.
   export function useDcsAuth() {
     const user = {
       id: 'standalone-user',
       name: 'Brand Operator',
       email: 'operator@local',
       role: ['orderai:brand:all'],
     }
     return { user, isLoading: false }
   }
   ```

2. **Frontend: `AuthContext.jsx`** → Keep structure but remove postMessage listener, always authenticated.

3. **Backend: `server/permissions.py`** → Replace entire file with passthrough:
   ```python
   """Permissions stub (share mode). All access granted to configured brand."""
   import os
   from fastapi import Depends, Header, Query

   def _get_configured_brand() -> str:
       return os.getenv("BRAND", "").upper()

   def require_brand_access(
       brand: str = Query(...),
       x_user_email: str = Header(default="operator@local", alias="X-User-Email"),
   ) -> str:
       """Always grants access. Returns email."""
       return x_user_email

   def list_user_brands_only(
       x_user_email: str = Header(default="operator@local", alias="X-User-Email"),
   ) -> list[str]:
       """Returns the single configured brand."""
       return [_get_configured_brand()]
   ```

4. **`server/routers/lite.py`** → Import unchanged from `server.permissions` (interface preserved).

5. **Remove**: `ALLOWED_ORIGINS`, `DEV_USER` complexity from frontend.

**Verification**:
- [ ] Frontend loads without DCS_AUTH postMessage (no 5s timeout spinner)
- [ ] All 13 Lite API endpoints respond without `X-User-Email` header
- [ ] `GET /api/lite/brands` returns single configured brand
- [ ] No references to `ROLE_TO_BRAND`, `HARDCODED_BRAND_MAP`, `BRAND_ENUM` remain (permissions.py rewrite 로 자연 제거)
- [ ] `grep -r "dcsai\|DCS_AUTH\|fnf.co.kr" apps/lite/src/` returns 0 results

**Effort**: 0.5 day
**Dependencies**: Phase 1

---

### Phase 3: Remove S3 Dependency (Local Storage Replacement)

**Goal**: Replace S3-based user_storage with local filesystem storage. Stale 개념 자체 삭제 `[v3-#4]`. This is the highest-risk phase.

**Files modified**:
- `server/services/user_storage.py` → REWRITE (local filesystem, no stale logic)
- `server/routers/shared.py` → REWRITE `/api/s3/file/` endpoint `[I3]`
- `server/routers/lite.py` → Update S3 error messages, **stale 응답 헤더 제거** `[I6] [v3-#4]`
- `server/s3_client.py` → DELETE (AFTER all consumers rewritten) `[I4]`
- `apps/lite/src/components/common/StaleWarning.jsx` → DELETE `[v3-#4]`
- `apps/lite/src/service/apiClient.js` → Remove `X-Stale-Warning` 헤더 파싱 `[v3-#4]`

**`[I4]` EXPLICIT SUB-STEP ORDERING** (must be followed in sequence):

#### Step 3.1: Rewrite `server/services/user_storage.py` `[v3-#3] [v3-#4]`

Local filesystem implementation. **`is_stale()` / `get_pipeline_version()` 제거** — fork 는 manual pipeline 이라 stale 개념 노이즈.

```python
"""
Local filesystem user storage (share mode).
Replaces S3 presigned URL storage for brand division fork.

Storage layout:
  data/user-storage/{brand}/{season}/{filename}

Single-user mode: no email partitioning needed.
No pipeline_version tracking — fork operator runs pipeline manually.
"""
import json, os, logging
from typing import Optional

logger = logging.getLogger(__name__)
_BASE_DIR = os.environ.get("USER_STORAGE_PATH", "data/user-storage")

def _file_path(email: str, brand: str, season: str, filename: str) -> str:
    return os.path.join(_BASE_DIR, brand.lower(), season.lower(), filename)

async def read_user_only(email, brand, season, filename) -> Optional[dict]:
    path = _file_path(email, brand, season, filename)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

async def read_with_fallback(email, brand, season, filename) -> Optional[dict]:
    return await read_user_only(email, brand, season, filename)

async def write_user_file(email, brand, season, filename, data) -> bool:
    path = _file_path(email, brand, season, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[user_storage] Saved {path}")
        return True
    except PermissionError:
        logger.error(f"[user_storage] PermissionError writing {path} — check filesystem permissions")
        raise

async def delete_user_file(email, brand, season, filename) -> bool:
    path = _file_path(email, brand, season, filename)
    if os.path.exists(path):
        os.remove(path)
    return True

# v3 변경: is_stale / get_pipeline_version 함수 삭제.
# fork 는 manual pipeline 운영 — operator 가 언제 돌렸는지 안다는 가정.
```

> **v3 검증된 오픈DB 사용 패턴** `[v3-#3]`: `server.db.open_db()` 는 `@contextmanager` 이므로 **인자 없이** `with open_db() as con:` 패턴으로 호출. v2 의 `con = open_db(brand)` 는 BUG.

#### Step 3.2: Rewrite `server/routers/shared.py` `/api/s3/file/` endpoint `[I3]`

S3-first → local-only (`public/` + `data/user-storage/`):

```python
"""
공통 라우터 — Share mode (3 endpoints).

- GET /api/health              헬스체크
- GET /api/brand-config        현재 brand_config.json 조회
- GET /api/s3/file/{filename}  로컬 JSON 파일 조회 (public/ + data/user-storage/)
"""

import json
import os

from fastapi import APIRouter, Depends, Header, HTTPException

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
USER_STORAGE_DIR = os.environ.get("USER_STORAGE_PATH",
                                   os.path.join(BASE_DIR, "data", "user-storage"))
BRAND_CONFIG_PATH = os.path.join(PUBLIC_DIR, "brand_config.json")

router = APIRouter()

_ALLOWED_FILES = {
    "budget_config.json",
    "color_mapping.json",
    "confirmed_mapping.json",
    "confirmed_order_data.json",
    "dashboard_data.json",
    "go_list.json",
    "order_recommendation_data.json",
    "season_closing_data.json",
    "style_mapping_data.json",
    "size_assortment_data.json",
}


def get_user_email(x_user_email: str = Header(default="")) -> str:
    return x_user_email


@router.get("/api/health")
async def health():
    return {"status": "ok"}


@router.get("/api/brand-config")
async def get_brand_config():
    if os.path.exists(BRAND_CONFIG_PATH):
        with open(BRAND_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@router.get("/api/s3/file/{filename}")
async def get_local_file(filename: str, user_email: str = Depends(get_user_email)):
    """로컬 파일 조회: data/user-storage/ 우선, public/ fallback."""
    if filename not in _ALLOWED_FILES:
        raise HTTPException(status_code=400, detail="허용되지 않은 파일입니다.")

    # User storage 우선 (brand/season 경로에서 검색)
    if user_email:
        for root, dirs, files in os.walk(USER_STORAGE_DIR):
            if filename in files:
                fpath = os.path.join(root, filename)
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f)

    # 로컬 public/ fallback
    local_path = os.path.join(PUBLIC_DIR, filename)
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise HTTPException(status_code=404, detail=f"{filename}을 찾을 수 없습니다.")
```

#### Step 3.3: Update `server/routers/lite.py` error messages + remove stale `[I6] [v3-#4]`

- Line 612: `"confirmed_mapping S3 저장 실패 — S3_API_KEY/네트워크 점검 필요"` → `"confirmed_mapping 로컬 파일 저장 실패 — 파일 시스템 권한 점검 필요"`
- Line 658: `"order_recommendation S3 저장 실패"` → `"order_recommendation 로컬 파일 저장 실패 — 파일 시스템 권한 점검 필요"`
- Line 609, 655 logger.error 에서 "S3" 제거
- **`X-Stale-Warning` 응답 헤더 추가하는 코드 모두 제거** `[v3-#4]`

#### Step 3.4: Frontend StaleWarning 제거 `[v3-#4]`

- `apps/lite/src/components/common/StaleWarning.jsx` 파일 삭제
- 모든 `import StaleWarning` 와 `<StaleWarning />` 사용처 제거 (각 Step 컴포넌트)
- `apiClient.js` 의 `stale` 필드 반환 제거 (응답 객체에서)

#### Step 3.5: Grep verification (BEFORE deletion)

```bash
grep -r "s3_client\|S3_API_KEY\|S3_BUCKET\|presigned\|PRESIGNED_API_BASE\|boto3\|s3_download_json\|s3_upload_json" server/ apps/
grep -r "X-Stale-Warning\|is_stale\|getPipelineVersion\|StaleWarning" server/ apps/lite/src/
```

**Must return 0 results** (except `s3_client.py` 자신). 잔존 시 진행 금지.

#### Step 3.6: Delete `server/s3_client.py`

Only AFTER step 3.5 confirms no remaining consumers.

#### Step 3.7: Final grep verification

```bash
grep -r "s3_client\|S3_API_KEY\|S3_BUCKET\|presigned\|X-Stale-Warning\|StaleWarning" server/ apps/
```

**Must return 0 results.**

**Verification**:
- [ ] `server/s3_client.py` does not exist
- [ ] `grep -r "s3_client\|S3_API_KEY\|S3_BUCKET\|presigned" server/` returns 0 results
- [ ] `grep -r "S3\|s3_client\|S3_API_KEY" server/routers/lite.py` returns 0 results `[I6]`
- [ ] `StaleWarning.jsx` does not exist; `grep -r "StaleWarning" apps/lite/src/` returns 0 results `[v3-#4]`
- [ ] `grep -r "is_stale\|get_pipeline_version" server/` returns 0 results `[v3-#4]`
- [ ] POST `/api/lite/confirmed-mapping` successfully writes to local filesystem
- [ ] GET `/api/lite/style-mapping` reads from local filesystem
- [ ] GET `/api/s3/file/{filename}` serves from `public/` and `data/user-storage/` `[I3]`
- [ ] POST `/api/lite/reset` deletes local files correctly
- [ ] Server starts without `S3_API_KEY` env var (no warnings, no errors)
- [ ] All 13 Lite endpoints still function correctly

**Effort**: 1-1.5 days (highest risk phase)
**Dependencies**: Phase 2

---

### Phase 4: Remove EC2/Nginx/Deploy Artifacts

**Goal**: Remove all cloud deployment infrastructure. Keep only local dev server.

**Files to DELETE**:
- `apps/lite/Dockerfile`, `apps/lite/deploy.sh`, `apps/lite/docker-compose.yml`, `apps/lite/docker-entrypoint.sh`, `apps/lite/.env.production.example`
- Root `Dockerfile`, `deploy.sh`, `docker-compose.yml` (if copied in Phase 1)
- `server/production.py`, `server/production_lite.py` (if copied)

**Files to MODIFY**:
- `apps/lite/vite.config.js` — Remove any proxy to EC2/production URLs
- `apps/lite/package.json` — Remove deploy-related scripts if any

**Actions**:
1. Delete all Docker/deploy files listed above
2. Verify `vite.config.js` proxy points to `localhost:8000` (local FastAPI)
3. Ensure `npm run dev` + `uvicorn server.api:app --port 8000` is the only needed startup

**Verification**:
- [ ] No files matching `Dockerfile|deploy.sh|docker-compose|docker-entrypoint|production` exist
- [ ] `npm run dev` starts frontend on port 3000 (or configured port)
- [ ] `uvicorn server.api:app --port 8000` starts backend
- [ ] Frontend successfully proxies API calls to local backend

**Effort**: 0.5 day
**Dependencies**: Phase 3

---

### Phase 5: Single Brand Mode + Remove Multi-Brand Logic

**Goal**: Enforce single-brand operation. `[I8]` 시작 시 BRAND env ↔ brand_config.json consistency 검증.

**Files modified**:
- `scripts/config_loader.py` — Add SINGLE_BRAND_MODE validation + consistency assertion `[I8]`
- `public/brand_config.json` — Simplify to single-brand schema
- `server/routers/lite.py` — `GET /brands` returns hardcoded single brand
- `server/db.py` — Simplify (no brand routing in queries, but keep brand param for data integrity)
- `scripts/dump_to_duckdb.py` — Single brand dump only
- `scripts/seed_users.py` → DELETE (no user management)

**Actions**:

1. **`config_loader.py`** — Add validation `[I8]`:

   ```python
   def get_brand():
       """BRAND env 또는 brand_config.json. 둘 다 설정되었으면 일치해야 함."""
       env_brand = os.environ.get("BRAND", "").strip().upper()
       config = _load_config()
       config_brand = config.get('brand', '').strip().upper()
       
       if env_brand and config_brand and env_brand != config_brand:
           raise RuntimeError(
               f"[Config] BRAND 환경변수({env_brand})와 brand_config.json({config_brand})이 "
               f"불일치합니다. 둘 중 하나를 수정하세요.\n"
               f"  - .env: BRAND={env_brand}\n"
               f"  - brand_config.json: \"brand\": \"{config_brand}\""
           )
       
       brand = env_brand or config_brand
       if not brand:
           raise RuntimeError(
               "[Config] BRAND 환경변수 또는 brand_config.json에 brand를 설정하세요.\n"
               "예: BRAND=DUVETICA 또는 brand_config.json의 'brand' 필드"
           )
       return brand
   ```

2. **Remove `HARDCODED_BRAND_MAP`** — 본 grep 결과:
   - `scripts/seed_users.py` — DELETE entirely
   - `test/server/test_step4_db.py` — Phase 1 에서 test/ 통째 제외됨, 자동 처리
   - `server/permissions.py` — Phase 2 에서 rewrite 됨, 자동 제거

3. **Simplify `brand_config.json`**:
   ```json
   {
     "brand": "DUVETICA",
     "baseSeason": "25F",
     "targetSeason": "26F",
     "subSeasons": { ... }
   }
   ```

4. **`server/routers/lite.py` GET /brands** — Phase 2 permissions stub 으로 자동 처리.

5. **`dump_to_duckdb.py`** — 단일 브랜드만 처리하도록 확인.

**Verification**:
- [ ] `BRAND=DUVETICA python scripts/run_all.py` 가 Duvetica 만 처리
- [ ] `HARDCODED_BRAND_MAP` 참조 0
- [ ] `scripts/seed_users.py` 존재 안 함
- [ ] `GET /api/lite/brands` 정확히 1 브랜드 반환
- [ ] BRAND env 와 brand_config 불일치 → **RuntimeError + 명확한 메시지** `[I8]`
- [ ] brand 미설정 → 명확한 에러
- [ ] `test_brand_config_consistency` 통과 `[I8]`

**Effort**: 0.5 day
**Dependencies**: Phase 2 (permissions stub)

---

### Phase 6: Remove V2 Legacy Code

**Goal**: V2 demand forecasting 코드 정리.

**Files to DELETE**: `scripts/ai_sales_loss_v2_legacy.py`

**Files to MODIFY**:
- `scripts/weekly_analysis.py` line 173-174 — V2 참조 주석을 V3 로
- `scripts/run_all.py` — V2 참조 없음 확인

**Verification**:
- [ ] `ai_sales_loss_v2_legacy.py` 존재 안 함
- [ ] `grep -r "ai_sales_loss_v2" scripts/ server/` 가 historical comment 만 (import 없음)
- [ ] `python scripts/run_all.py` V2 참조 없이 완료

**Effort**: 0.25 day
**Dependencies**: Phase 1

---

### Phase 7: Harness (setup.sh + Smoke Test) `[v3-#5]`

**Goal**: Self-validating harness — 핵심 deliverable.

**Files to CREATE**:
- `setup.sh` — Bash bootstrap with `--skip-snowflake` mode `[v3-#5]`
- `smoke_test.py` — pytest-based validation
- `pytest.ini`

**Actions**:

1. **`setup.sh`** `[I9] [v3-#5]`:

   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   
   # [v3-#5] --skip-snowflake 모드 (pre-meeting 셋업)
   SKIP_SNOWFLAKE=false
   for arg in "$@"; do
       case $arg in
           --skip-snowflake) SKIP_SNOWFLAKE=true ;;
           --help) 
               echo "Usage: $0 [--skip-snowflake]"
               echo "  --skip-snowflake : Skip step 5 (smoke test). Use before onboarding meeting."
               exit 0 ;;
       esac
   done
   
   echo "+==============================================+"
   echo "|  Order AI Share -- Setup                     |"
   if [ "$SKIP_SNOWFLAKE" = true ]; then
       echo "|  Mode: PRE-MEETING (Snowflake check skipped) |"
   fi
   echo "+==============================================+"
   echo ""
   
   # --- Step 1/5: Prereqs ---
   echo "[1/5] Checking prerequisites..."
   command -v python3 >/dev/null 2>&1 || { echo "FAIL: python3 not found. Install Python 3.11+"; exit 1; }
   command -v node >/dev/null 2>&1 || { echo "FAIL: node not found. Install Node.js 18+"; exit 1; }
   command -v npm >/dev/null 2>&1 || { echo "FAIL: npm not found. Install Node.js 18+"; exit 1; }
   
   PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
   echo "  Python: $PY_VERSION"
   echo "  Node: $(node --version)"
   
   # --- Step 2/5: venv + Python deps ---
   echo "[2/5] Setting up Python virtual environment..."
   if [ ! -d ".venv" ]; then
       python3 -m venv .venv
   fi
   source .venv/bin/activate
   pip install -q --upgrade pip
   pip install -q -r requirements.txt
   echo "  Done. $(pip list | wc -l) packages installed."
   
   # --- Step 3/5: Node deps ---
   echo "[3/5] Installing frontend dependencies..."
   cd apps/lite && npm install --silent && cd ../..
   echo "  Done."
   
   # --- Step 4/5: .env validation [v3-#5] ---
   echo "[4/5] Checking .env configuration..."
   if [ ! -f ".env" ]; then
       if [ "$SKIP_SNOWFLAKE" = true ]; then
           echo "  .env not found (OK for pre-meeting mode)."
       else
           echo "FAIL: .env file not found."
           echo "  -> Copy .env.example to .env and fill in Snowflake credentials."
           echo "  -> Or run: ./setup.sh --skip-snowflake (pre-meeting mode)"
           exit 1
       fi
   else
       # SSO 차단 [v3-#5]
       if grep -q "SNOWFLAKE_AUTH=externalbrowser" .env 2>/dev/null; then
           echo "FAIL: SNOWFLAKE_AUTH=externalbrowser (SSO) 는 헤드리스 환경에서 동작 안 함."
           echo "  -> .env 에서 SNOWFLAKE_AUTH 항목을 제거하거나 비워두세요 (password 자동 사용)."
           exit 1
       fi
       echo "  .env found. SSO auth check passed."
   fi
   
   # --- Step 5/5: Smoke test (skip if --skip-snowflake) ---
   if [ "$SKIP_SNOWFLAKE" = true ]; then
       echo "[5/5] Skipping smoke test (pre-meeting mode)."
       echo ""
       echo "=== SETUP COMPLETE: PRE-MEETING ==="
       echo ""
       echo "Pre-meeting prep done. After onboarding meeting:"
       echo "  1. Fill .env with Snowflake credentials"
       echo "  2. Run: ./setup.sh   (full validation)"
       echo "  3. Then: python scripts/plc_engine/build_plc_standard.py  (first-time)"
       echo "  4. Then: python scripts/run_all.py"
       exit 0
   fi
   
   echo "[5/5] Running smoke test (Snowflake connectivity)..."
   python -m pytest smoke_test.py -v --tb=short
   RESULT=$?
   
   echo ""
   if [ $RESULT -eq 0 ]; then
       echo "=== SETUP COMPLETE: PASS ==="
       echo ""
       echo "Next steps:"
       echo "  1. First-time PLC build:  .venv/bin/python scripts/plc_engine/build_plc_standard.py"
       echo "  2. Run pipeline:           .venv/bin/python scripts/run_all.py"
       echo "  3. Start server:           .venv/bin/uvicorn server.api:app --port 8000"
       echo "  4. Start frontend:         cd apps/lite && npm run dev"
       echo ""
       echo "  Or activate the venv first:  source .venv/bin/activate"
   else
       echo "=== SETUP FAILED at step 5: Smoke test ==="
       echo "  -> Check .env Snowflake credentials"
       echo "  -> Ask Claude Code to help troubleshoot the error above"
       exit 1
   fi
   ```

2. **`smoke_test.py`** `[I2] [I7] [I14]`:

   ```python
   """
   Smoke test -- validates environment is correctly configured.
   Level 2: venv + deps + .env format + Snowflake SELECT 1 + brand COUNT query.
   
   Run: python -m pytest smoke_test.py -v
   """
   import os
   import pytest
   from dotenv import load_dotenv
   
   load_dotenv()
   
   # [I2] Brand name -> BRD_CD mapping (Snowflake column value)
   BRAND_TO_BRD_CD = {
       "MLB": "M",
       "DISCOVERY": "X",
       "DUVETICA": "V",
       "MLB KIDS": "I",
       "MLBKIDS": "I",
       "SERGIO": "ST",
       "SERGIO TACCHINI": "ST",
   }
   
   
   class TestEnvironment:
       def test_python_version(self):
           import sys
           assert sys.version_info >= (3, 11), "Python 3.11+ required"
       
       def test_critical_imports(self):
           import pandas, duckdb, snowflake.connector, fastapi, httpx
       
       def test_server_api_importable(self):
           """[I1] Verify server.api can be imported without crashing."""
           import server.api
       
       def test_env_file_exists(self):
           assert os.path.exists(".env"), ".env file missing"
       
       def test_env_has_snowflake_vars(self):
           required = [
               "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_WAREHOUSE",
               "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA",  # [I14]
           ]
           missing = [v for v in required if not os.environ.get(v)]
           assert not missing, f"Missing env vars: {missing}"
       
       def test_brand_configured(self):
           brand = os.environ.get("BRAND", "")
           assert brand, "BRAND env var not set"
       
       def test_brand_config_consistency(self):
           """[I8] BRAND env var and brand_config.json must agree if both set."""
           import json
           env_brand = os.environ.get("BRAND", "").strip().upper()
           config_path = os.path.join("public", "brand_config.json")
           if os.path.exists(config_path):
               with open(config_path) as f:
                   config = json.load(f)
               config_brand = config.get("brand", "").strip().upper()
               if env_brand and config_brand:
                   assert env_brand == config_brand, (
                       f"BRAND env ({env_brand}) != brand_config.json ({config_brand}). "
                       f"Fix one to match the other."
                   )
   
   
   class TestSnowflakeConnectivity:
       def _connect(self):
           import snowflake.connector
           return snowflake.connector.connect(
               account=os.environ["SNOWFLAKE_ACCOUNT"],
               user=os.environ["SNOWFLAKE_USER"],
               password=os.environ.get("SNOWFLAKE_PASSWORD", ""),
               warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
               role=os.environ.get("SNOWFLAKE_ROLE", ""),
               database=os.environ.get("SNOWFLAKE_DATABASE", "FNF"),     # [I14]
               schema=os.environ.get("SNOWFLAKE_SCHEMA", "PRCS"),        # [I14]
           )
   
       def test_select_one(self):
           """Snowflake basic connectivity."""
           conn = self._connect()
           cur = conn.cursor()
           cur.execute("SELECT 1")
           assert cur.fetchone()[0] == 1
           conn.close()
       
       def test_brand_data_access(self):
           """[I2][I7] Verify access to brand-specific data with parameterized query."""
           brand = os.environ["BRAND"].upper()
           brd_cd = BRAND_TO_BRD_CD.get(brand)
           assert brd_cd is not None, (
               f"Unknown brand '{brand}'. "
               f"Valid brands: {list(BRAND_TO_BRD_CD.keys())}"
           )
           
           conn = self._connect()
           cur = conn.cursor()
           cur.execute(
               "SELECT COUNT(*) FROM FNF.PRCS.DB_SCS_W "
               "WHERE BRD_CD = %s AND SESN = '25F'",
               (brd_cd,),
           )
           count = cur.fetchone()[0]
           assert count > 0, (
               f"No data found for brand '{brand}' (BRD_CD='{brd_cd}') "
               f"-- check Snowflake permissions"
           )
           conn.close()
   ```

3. **`pytest.ini`**:
   ```ini
   [pytest]
   testpaths = .
   markers =
       smoke: Smoke test (setup validation)
   ```

4. **`requirements.txt`** 추가: `pytest>=7.0.0`

**Verification**:
- [ ] `./setup.sh` 가 executable (`chmod +x`)
- [ ] `./setup.sh` on configured machine → exits 0 with "PASS"
- [ ] `./setup.sh --skip-snowflake` → exits 0 with "PRE-MEETING" + 다음 단계 안내 `[v3-#5]`
- [ ] `./setup.sh` without `.env` → exits 1 with `--skip-snowflake` 옵션 안내 포함
- [ ] `./setup.sh` 가 SSO `.env` 발견 → exits 1 with clear SSO 경고 `[v3-#5]`
- [ ] `./setup.sh` with wrong creds → exits 1, pytest shows which test failed
- [ ] Idempotent (실행 두 번 같은 결과)
- [ ] `python -m pytest smoke_test.py -v` 독립 실행 가능
- [ ] "Next steps" uses absolute `.venv/bin/` paths `[I9]`
- [ ] "Next steps" 에 `build_plc_standard.py` 단계 포함 `[v3-#1]`
- [ ] `test_brand_data_access` uses parameterized query `[I2] [I7]`

**Effort**: 1 day
**Dependencies**: Phase 4 (clean repo), Phase 5 (single brand mode)

---

### Phase 8: Documentation `[v3-#8]`

**Goal**: Operator-friendly docs that Claude Code can use for troubleshooting.

**Files to CREATE**:
- `README.md` — Overview + "show this to Claude Code"
- `SETUP.md` — Detailed step-by-step
- `SUPPORT.md` — Support policy (1 meeting + severance) + **credential delivery method** `[v3-#8]`
- `docs/PLC_GUIDE.md` — Self-generated PLC overview (replaces ITEM_COMPATIBILITY.md) `[v3-#1]`
- `docs/ONBOARDING_CHECKLIST.md` — Meeting prep

**Actions**:

1. **`README.md`**:
   - Project 설명 (AI-based initial order optimization, single brand, **self-generated PLC**)
   - Quick start (4 commands: setup.sh → build_plc_standard.py → run_all.py → dev servers) `[v3-#1]`
   - "If anything fails, paste this README to Claude Code for help"
   - Architecture diagram (단순: Snowflake → Pipeline → DuckDB → API → Frontend)
   - No F&F internal URLs, no DCS AI references

2. **`SETUP.md`**:
   - Prereqs (Python 3.11+, Node 18+, Snowflake credentials)
   - **Pre-meeting**: `./setup.sh --skip-snowflake` 단독 실행 가능 안내 `[v3-#5]`
   - `.env` 설정 (`SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA` 포함) `[I14]`
   - **SNOWFLAKE_AUTH 항목 추가 금지** 안내 `[v3-#5]`
   - `brand_config.json` (brand, baseSeason, targetSeason)
   - **First-time PLC 빌드**: `python scripts/plc_engine/build_plc_standard.py` `[v3-#1]`
   - 풀 파이프라인 실행: `python scripts/run_all.py`
   - 서버 기동 + npm run dev
   - Troubleshooting FAQ (top 5 expected issues + insufficient data scenario)

3. **`SUPPORT.md`** `[v3-#8]`:
   - "이 시스템은 초기 세팅 회의 1회 후 독립 운영됩니다"
   - No code sync, no bug fixes from upstream
   - Self-help: README, SETUP.md, Claude Code
   - **PLC 재생성 (누적 데이터 사용)**: `python scripts/plc_engine/build_plc_standard.py` 재실행 `[v3-#1]`
   - **Credential delivery method** `[v3-#8]`:
     - **1순위: 1Password Share** — AX팀이 사업부에 1회용 share link 전달
     - **2순위: GPG encrypted file** — 사전 GPG 키 교환 후 암호화 파일 전달
     - **금지**: plain email, Slack DM, GitHub commit, USB unencrypted

4. **`docs/PLC_GUIDE.md`** (replaces ITEM_COMPATIBILITY.md) `[v3-#1]`:
   - 핵심 컨셉: "각 fork 는 자기 브랜드 raw 데이터로 PLC 표준 곡선을 만든다"
   - When to (re)generate:
     - 첫 출시 후 1회
     - 새 시즌 데이터 누적 후 (시즌 종료 시점에 권장)
     - 새 카테고리/아이템 추가 후
   - 데이터 요건: >=2 완전 시즌
   - Insufficient data 시 안내: AX팀에 seed PLC 요청 — `ax-team@fnf.co.kr`
   - **Drift report 해석** `[v3-#7]`:
     - <5%: 변화 미미. 재생성 효과 없음.
     - 5–30%: 정상 적응. 새 표준 적용.
     - >30%: 큰 차이. raw 데이터 검증 후 재실행.

5. **`docs/ONBOARDING_CHECKLIST.md`**:
   - [ ] Snowflake service account credentials 1Password share 전달됨 `[v3-#8]`
   - [ ] 사업부 운영자 Python 3.11+ 설치 확인
   - [ ] 사업부 운영자 Node.js 18+ 설치 확인
   - [ ] **Pre-meeting: `./setup.sh --skip-snowflake` PASS 확인** `[v3-#5]`
   - [ ] Meeting 중: `.env` 파일 설정
   - [ ] `./setup.sh` PASS
   - [ ] `python scripts/plc_engine/build_plc_standard.py` 성공 + drift report 확인 `[v3-#1]`
   - [ ] `python scripts/run_all.py` 완료 (DuckDB generated)
   - [ ] Frontend 데이터 표시 확인 (visual)
   - [ ] 다음 시즌 데이터 도착 후 재실행 방법 숙지

**Verification**:
- [ ] README.md contains no internal F&F URLs or DCS AI references
- [ ] SETUP.md is followable by a fresh operator
- [ ] All code examples in docs are correct and runnable
- [ ] PLC_GUIDE.md 가 self-gen 흐름 정확히 설명 `[v3-#1]`
- [ ] SUPPORT.md credential delivery 1Password 1순위 명시 `[v3-#8]`
- [ ] ONBOARDING_CHECKLIST.md 인쇄 가능, pre-meeting 단계 포함 `[v3-#5]`

**Effort**: 1 day
**Dependencies**: Phase 7 (setup.sh must be final)

---

### Phase 9: Clean Install Verification

**Goal**: Prove the artifact works on a fresh machine.

**Method**: Docker container (Ubuntu) AND macOS verification `[I12]`.

**Actions**:

1. `test/Dockerfile.verification` (NOT shipped):
   ```dockerfile
   FROM ubuntu:22.04
   RUN apt-get update && apt-get install -y python3.11 python3.11-venv python3-pip nodejs npm git
   WORKDIR /app
   COPY . /app/
   COPY .env.test /app/.env
   ```

2. Build and run (Ubuntu):
   ```bash
   docker build -f test/Dockerfile.verification -t order-ai-verify .
   docker run --rm order-ai-verify bash -c "./setup.sh"
   ```

3. **macOS verification** `[I12]`:
   - `./setup.sh` 실행 (Homebrew Python/Node)
   - 미설치 시: `brew install python@3.11 node@18`
   - 모든 smoke test 통과 확인 (특히 Snowflake connector — platform-specific wheels)
   - macOS 특이 이슈 SETUP.md troubleshooting 에 반영

4. Test matrix:
   - [ ] **Ubuntu (Docker)**: setup.sh PASS with valid creds
   - [ ] **macOS**: setup.sh PASS with valid creds `[I12]`
   - [ ] **Ubuntu (Docker)**: `setup.sh --skip-snowflake` PASS `[v3-#5]`
   - [ ] setup.sh FAIL with missing .env (correct error)
   - [ ] setup.sh FAIL with wrong Snowflake password (correct error)
   - [ ] setup.sh FAIL with `SNOWFLAKE_AUTH=externalbrowser` 설정 (correct error) `[v3-#5]`
   - [ ] After setup: `build_plc_standard.py` 생성 (DuckDB 있다면) `[v3-#1]`
   - [ ] After PLC: `run_all.py` 생성 (DuckDB)
   - [ ] After pipeline: `uvicorn` starts
   - [ ] All 13 Lite endpoints respond correctly
   - [ ] Frontend `npm run dev` builds and serves

5. Manual UI walkthrough:
   - Step 1 (SeasonClosing) 로드 with data
   - Step 2 (Dashboard) 시계열 표시
   - Step 3 (StyleMapping) GO list 업로드 + mapping 확정
   - Step 4 (OrderSuggest) Step 3 확정 후 추천 표시
   - Step 5 (SizeAssortment) 사이즈 데이터 표시
   - **StaleWarning 어디에도 없음 확인** `[v3-#4]`

**Verification**:
- [ ] Docker (Ubuntu) verification 모두 통과
- [ ] **macOS verification 모두 통과** `[I12]`
- [ ] **Pipeline cooldown** 5분 검증 — 연속 호출 시 429 응답 `[v3-#6]`
- [ ] All 13 API endpoints tested (auto via `tests/integration/test_lite_api.py`)
- [ ] UI walkthrough 5 step 모두 functional
- [ ] No console errors during walkthrough
- [ ] Pipeline 산출 파일 개수 expected

**Effort**: 1 day
**Dependencies**: Phase 8

---

### Phase 10: Onboarding Meeting Preparation

**Goal**: Prepare materials for the single onboarding meeting.

**Deliverables**:
- `docs/ONBOARDING_CHECKLIST.md` (Phase 8)
- Demo scenario script
- Pre-meeting email template

**Actions**:

1. **Pre-meeting email** (referenced in SUPPORT.md) `[v3-#5] [v3-#8]`:
   - Python 3.11+ 설치
   - Node.js 18+ 설치
   - Terminal access ready
   - Claude Code 구독 active
   - **`git clone` + `./setup.sh --skip-snowflake` 까지 미리 실행 권장** `[v3-#5]`
   - IT 가 회의에서 Snowflake credentials **1Password share link 전달** `[v3-#8]`

2. **Demo scenario** (meeting flow, ~50min):
   - 5 min: Pre-meeting 확인 (`./setup.sh --skip-snowflake` PASS 상태)
   - 5 min: 1Password share 받아 .env 작성
   - 5 min: `./setup.sh` 풀 실행 → PASS 관전
   - 10 min: `python scripts/plc_engine/build_plc_standard.py` 실행 + drift report 해석 `[v3-#1]`
   - 10 min: `python scripts/run_all.py` 실행 (각 step 설명)
   - 5 min: 서버 기동, 브라우저 오픈
   - 10 min: Steps 1-5 walkthrough with real data

3. **Handoff artifacts**:
   - GitHub repo access (collaborator invite)
   - .env (1Password share, NOT in repo) `[v3-#8]`
   - This document as reference

**Verification**:
- [ ] Demo scenario 1회 사내 리허설
- [ ] Pre-meeting email 작성
- [ ] 전체 흐름 (clone → pre-setup → meeting setup → PLC → pipeline → UI) <50 min
- [ ] 운영자가 회의 후 독립 재실행 가능

**Effort**: 0.5 day
**Dependencies**: Phase 9

---

## Acceptance Criteria (Aggregate)

### Repository Structure
- [ ] Private GitHub repo `order-ai-share` 존재 `[v3-#2]`
- [ ] DCS AI auth 0 (`dcsai`, `fnf.co.kr`, `DCS_AUTH` 참조 없음)
- [ ] S3 의존성 0 (`s3_client`, `presigned`, `S3_API_KEY` 참조 없음)
- [ ] EC2/deploy artifacts 0 (no Dockerfile, deploy.sh, docker-compose.yml)
- [ ] V2 legacy code 0
- [ ] `HARDCODED_BRAND_MAP` 참조 0
- [ ] **`StaleWarning.jsx` 존재 안 함, `is_stale`/`getPipelineVersion` 참조 0** `[v3-#4]`
- [ ] Single brand mode enforced via config_loader
- [ ] `queries/` 디렉토리 5 SQL 파일 `[I11]`
- [ ] `server/api.py` NEW minimal version (shared+lite only) + **5분 cooldown** `[I1] [v3-#6]`

### Harness
- [ ] `./setup.sh` → PASS on configured machine
- [ ] `./setup.sh --skip-snowflake` → PASS pre-meeting mode `[v3-#5]`
- [ ] `./setup.sh` → FAIL with clear error on misconfigured (including SSO detection) `[v3-#5]`
- [ ] Idempotent
- [ ] `python -m pytest smoke_test.py` 독립 실행
- [ ] Parameterized Snowflake queries `[I2] [I7]`
- [ ] "Next steps" uses absolute `.venv/bin/` paths, **build_plc_standard.py 단계 포함** `[I9] [v3-#1]`

### PLC `[v3-#1]`
- [ ] `build_plc_standard.py` 자기 브랜드 raw 데이터로 정상 생성
- [ ] Sufficiency gate: <2 시즌 → 명확한 에러 + AX팀 seed 안내
- [ ] **Drift report**: 5/30 임계 분기 정상 출력 `[v3-#7]`
- [ ] MLB+Discovery 평균 PLC 참조 0 (v2 잔재 없음)

### Pipeline
- [ ] `python scripts/run_all.py` produces DuckDB + all JSON outputs
- [ ] V3 PLC engine works with self-generated standard `[v3-#1]`
- [ ] GT generator produces valid ground truth from weekly_raw
- [ ] **Pipeline cooldown** 5분 검증 `[v3-#6]`

### API + Frontend
- [ ] All 13 Lite endpoints functional without auth headers
- [ ] Local filesystem storage replaces S3
- [ ] `/api/s3/file/{filename}` serves from local dirs only `[I3]`
- [ ] **`X-Stale-Warning` 헤더 0** `[v3-#4]`
- [ ] Frontend 5 step 모두 데이터 with no StaleWarning UI `[v3-#4]`

### Documentation
- [ ] README, SETUP, SUPPORT 문서 존재 + 정확
- [ ] **PLC_GUIDE.md** (replaces ITEM_COMPATIBILITY) self-gen 흐름 설명 `[v3-#1]`
- [ ] ONBOARDING_CHECKLIST pre-meeting + meeting 단계 분리 `[v3-#5]`
- [ ] **Credential delivery: 1Password 1순위 명시** `[v3-#8]`

---

## Risk Register (v3 updated)

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| S3 removal breaks non-obvious code path | HIGH | HIGH | grep + ordered sub-steps `[I4]` + integration test 13 endpoints |
| Snowflake service account wrong permissions | MEDIUM | HIGH | Smoke test parameterized COUNT query `[I2]` |
| **Insufficient historical data for self-gen PLC** `[v3-#1]` | LOW | MEDIUM | Sufficiency gate (>=2 seasons) + AX manual seed protocol + PLC_GUIDE.md |
| setup.sh fails on Windows (no bash) | MEDIUM | MEDIUM | Document WSL/Git Bash, or provide setup.ps1 later |
| **SSO (externalbrowser) auth blocks headless** `[v3-#5]` | LOW | MEDIUM | setup.sh detects `SNOWFLAKE_AUTH=externalbrowser` → fail with message |
| config_loader caching causes stale reads | LOW | LOW | Document: restart pipeline after config change |
| user_storage rewrite loses edge case behavior | MEDIUM | MEDIUM | Test all CRUD + reset scope combinations |
| server/api.py imports crash on startup | RESOLVED | — | NEW minimal api.py `[I1]` |
| BRAND env vs brand_config.json split-brain | MEDIUM | MEDIUM | Startup assertion `[I8]` |
| Brand division modifies code and breaks it | HIGH | LOW | Not our problem (severance), good docs help |
| **`/api/run-pipeline` concurrent abuse** `[v3-#6]` | LOW | LOW | 5분 cooldown + concurrency lock |
| **Drift report misinterpretation** `[v3-#7]` | LOW | MEDIUM | PLC_GUIDE.md 명시: 3단계 임계 + 해석 가이드 |
| **Credential leak via plain email/Slack** `[v3-#8]` | MEDIUM | HIGH | SUPPORT.md 1Password 1순위 강제, ONBOARDING_CHECKLIST 검증 |
| macOS-specific issues (wheels, paths) | MEDIUM | MEDIUM | macOS verification Phase 9 `[I12]` |

> v3 변경 — 삭제된 risk: "Standard PLC poor fit for target brand" (self-gen 으로 자연 해소), "PLC ITEM Mismatch Silent Degradation" (Pre-mortem Scenario 3 재정의)

---

## ADR: Lite Fork Separation (v3 unchanged)

**Decision**: Lite system 을 `order-ai-share` 라는 독립 GitHub repo 로 추출. self-validating harness 포함, **self-generated PLC**.

**Drivers**:
1. Brand divisions need autonomous local operation without F&F central infrastructure
2. Support model "1 meeting then severance" — artifact must be self-sufficient
3. Current Lite 가 DCS AI auth, S3, multi-brand routing 에 깊게 결합
4. **Each brand should own its PLC standard** `[v3-#1]` — cross-brand average creates unnecessary AX-team dependency

**Alternatives Considered**:
1. ~~Git subtree/submodule~~ — Rejected: implies ongoing sync
2. ~~Docker image delivery~~ — Rejected: operators need source access for config/retrain
3. ~~Feature flags in main repo~~ — Rejected: increases main repo complexity
4. ~~Configurable profiles in single repo~~ — Rejected: dead S3/auth code remains
5. ~~Cross-brand shared PLC (v2 design)~~ — Rejected: graduated decision tree complexity, AX maintenance burden, item mismatch risk `[v3-#1]`

**Why Chosen**: Clean copy + surgical removal + self-gen PLC = simplest mental model. No sync obligation, no shared assets, no cross-brand dependency.

**Consequences**:
- Bug fixes in main Lite will NOT propagate to forks (accepted)
- Brand divisions may diverge over time (accepted)
- Each fork requires AX manual seed if <2 시즌 history (low frequency, acceptable)
- PLC quality 가 fork 별로 다름 (intended — own brand best fit)

**Follow-ups**:
- [ ] Decide license before first external delivery
- [ ] Consider template repo if >3 brand divisions fork
- [ ] Monitor first deployment for undiscovered issues

---

## Effort Summary

| Phase | Effort | Cumulative |
|-------|--------|-----------|
| Phase 0: Pre-work (gt_builder + build_plc) `[v3-#1]` | 1.5-2 days | 1.5-2 days |
| Phase 1: Create repo | 0.5 day | 2-2.5 days |
| Phase 2: Remove auth | 0.5 day | 2.5-3 days |
| Phase 3: Remove S3 + Stale `[v3-#4]` | 1-1.5 days | 3.5-4.5 days |
| Phase 4: Remove deploy | 0.5 day | 4-5 days |
| Phase 5: Single brand | 0.5 day | 4.5-5.5 days |
| Phase 6: Remove V2 | 0.25 day | 4.75-5.75 days |
| Phase 7: Harness `[v3-#5]` | 1 day | 5.75-6.75 days |
| Phase 8: Documentation `[v3-#8]` | 1 day | 6.75-7.75 days |
| Phase 9: Verification | 1 day | 7.75-8.75 days |
| Phase 10: Onboarding prep | 0.5 day | 8.25-9.25 days |
| **TOTAL** | **~8-9 working days** | (v2 의 10일 대비 단축) |

---

## Dependency Graph

```
Phase 0 (PLC build tool + GT) ---+
                                  v
Phase 1 (create repo) --+---> Phase 2 (auth) ---> Phase 3 (S3 + Stale) ---> Phase 4 (deploy)
                        |                                                       |
                        |                                                       v
                        +---> Phase 6 (V2) -----------------------------> Phase 5 (brand)
                                                                                |
                                                                                v
                                                                          Phase 7 (harness)
                                                                                |
                                                                                v
                                                                          Phase 8 (docs)
                                                                                |
                                                                                v
                                                                          Phase 9 (verify)
                                                                                |
                                                                                v
                                                                          Phase 10 (onboard)
```

Critical path: 0 → 1 → 2 → 3 → 4 → 5 → 7 → 8 → 9 → 10
Parallelizable: Phase 6 can run alongside 2-4.

---

## Revision Log

### v3.1 (2026-05-18) — SSO 허용 (Phase 7 amendment)

v3 에서 SSO (`SNOWFLAKE_AUTH=externalbrowser`) 를 setup.sh 가 무조건 차단하던 정책을 완화. 로컬 운영자 모델에선 SSO 가 더 안전 (password 평문 보관 X, 브랜드 권한 자동).

| 변경 위치 | 내용 |
|---|---|
| `setup.sh` step 4 | SSO 모드 발견 시 FAIL → INFO 메시지 출력하고 통과 |
| `smoke_test.py` | `_connect()` 에 `authenticator=externalbrowser` 분기 추가. `test_env_has_snowflake_vars` 가 모드별 필수 변수 분기 |
| `.env.example` | 두 모드 옵션 명시 (SSO 권장, Service Account 헤드리스용) |
| `SETUP.md` §3, §4 | 두 모드별 .env 설정 분기, Troubleshooting 의 SSO timeout 항목 추가 |
| `SUPPORT.md` Credential 전달 정책 | 옵션 A (SSO) 권장 / 옵션 B (Service Account) — 1Password 전달은 옵션 B 에만 해당 |
| `docs/ONBOARDING_CHECKLIST.md` 5–10분 | 인증 모드 결정 후 분기 |

v3 의 `[v3-#5]` 태그 (SSO 차단) 는 v3.1 에서 무효화. 추가 태그 없이 SSO 가 정식 옵션으로 등록됨.

### v3 (2026-05-18) — Cowork Refine

§4 8개 항목 + (나) self-generated PLC pivot. 모든 v3 변경에 `[v3-#N]` 태그.

| # | 항목 | 변경 내용 | 영향 Phase |
|---|------|-----------|------------|
| v3-#1 | **PLC baseline 모델 전환** | 공유 표준(MLB+Discovery) → **self-generated**. graduated decision tree 삭제. ITEM_COMPATIBILITY → PLC_GUIDE | Phase 0, 1, 8, ADR, Risk |
| v3-#2 | repo 이름 | `order-ai-standalone` → `order-ai-share` | Phase 1, 전체 |
| v3-#3 | **`open_db()` 버그 수정** | v2 의 `con = open_db(brand)` → `with open_db() as con:` (verified via grep against source) | Phase 3 user_storage |
| v3-#4 | **`is_stale()` + StaleWarning 양쪽 삭제** | fork 는 manual pipeline 운영 — stale 개념 노이즈 | Phase 1, 3 |
| v3-#5 | **`setup.sh --skip-snowflake` + SSO 차단** | pre-meeting 모드 + `SNOWFLAKE_AUTH=externalbrowser` 검출 시 fail | Phase 7, 10, ONBOARDING_CHECKLIST |
| v3-#6 | **`/api/run-pipeline` 5분 cooldown** | 동시 호출 방지 + 429 응답 | Phase 1, 9 |
| v3-#7 | **build_plc_standard 드리프트 리포트** | 기존 vs 새 PLC MAPE: <5 / 5-30 / >30 분기 | Phase 0, 8 |
| v3-#8 | **`.env` credential 전달 방식 명시** | 1Password share 1순위, GPG 2순위, plain email 금지 | Phase 8, 10 |

### v2 (2026-05-18) — Critic ITERATE Response

14 issues from `lite-fork-critic-verdict.md` resolved (full table preserved in v2 doc).

---

## Open Questions Resolved (v3 final)

| # | Question | v3 Resolution | Rationale |
|---|----------|---------------|-----------|
| 1 | Repo name | **`order-ai-share`** | 사용자 결정 — fork 가 아닌 share 모델 |
| 2 | setup.sh language | Hybrid (bash → pytest) | Avoids chicken-and-egg |
| 3 | Smoke test framework | pytest | Spec mandates, Claude Code understands |
| 4 | Sample data bundling | None (Snowflake-only) | Operators have creds, DuckDB on first run |
| 5 | PLC timing/source | **Self-generated** `[v3-#1]` | Severance-aligned, simpler, better fit |
| 6 | Single-brand enforcement | config_loader schema validation | Earliest failure point |
