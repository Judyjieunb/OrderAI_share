# TODO — order-ai-share

> 본 fork 의 진행 중/보류 항목. AX팀 인계 전 + 인계 후 양쪽 추적.

---

## 🔁 운영자 자체 환경에서 검증 권장

본 fork 는 운영자 환경 (OS / Snowflake credentials 등) 에서 받자마자 4 스킬 호출로 자체 검증:

| 검증 영역 | 흡수 스킬 |
|---|---|
| OS / Prereqs / `setup.sh` 풀 검증 | **`/onboard`** (Stage 1-7) |
| `.env` 모드 (SSO / Service Account / skip) | **`/onboard`** Stage 3 |
| Snowflake 연결 실패 진단 (HttpError, credentials, brand 불일치 등) | **`/onboard`** Stage 6 의 진단표 |
| OS 별 설치 안내 (macOS Homebrew / Linux apt / Windows WSL2) | **`/onboard`** Stage 1-2 의 OS 자동감지 |
| 5 step UI walkthrough + console error 점검 | **`/server-start`** |

신규 brand/시즌 또는 PLC 빌드 → `/prepare-pipeline`. 분석 + baseline DuckDB 적재 → `/run-pipeline`.

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

