# SUPPORT — order-ai-share

> 본 시스템은 **온보딩 미팅 1회 후 사업부 자율 운영** 모델입니다 (severance).
>
> AX팀은 인계 후 정기 patch / bug fix / upstream sync 를 제공하지 않습니다.

---

## 책임 경계

### AX팀 보장

| 항목 | 범위 |
|---|---|
| 1회 온보딩 미팅 | 미팅 진행 + Q&A |
| 인계 시점 코드의 동작 | `./setup.sh` PASS + 5 step UI 정상 표시 |
| Cold-start 브랜드 seed PLC | weekly_raw 데이터 <2 시즌인 브랜드에 한해 manual 생성 1회 |
| 본 문서 (README/SETUP/SUPPORT/CLAUDE/PLC_GUIDE) | 인계 시점 내용 |

### 사업부 책임

| 항목 | 범위 |
|---|---|
| 본 디렉토리 수정 / 커스터마이즈 | 변경 + 검증 + 결과 확인 |
| 운영 환경 관리 | Python/Node 버전 유지, `.env` 보안, 서버 기동 |
| Snowflake credentials 보관 | `.env` 의 노출 차단, 정기 password 변경 |
| 사고 / 장애 대응 | 트러블슈팅, 데이터 재생성 |
| 결과 검증 | AI 추천을 그대로 적용하지 말고 자체 판단 |
| 발주 의사결정 | 최종 발주 결정의 모든 책임 |
| 새 시즌 PLC 재생성 | `build_plc_standard.py` 재실행 |

---

## Credential 전달 정책

Snowflake 인증 모드에 따라 정책이 다릅니다.

### ✅ 옵션 A: SSO (externalbrowser) — 권장

- IT 가 운영자 본인 Snowflake account 의 role 에 브랜드 grant 만 부여
- 운영자는 `.env` 에 `SNOWFLAKE_AUTH=externalbrowser` 와 본인 계정 정보만 입력 (password 불필요)
- `./setup.sh` 또는 파이프라인 실행 시 브라우저 팝업으로 본인 SSO login
- **장점**:
  - `.env` 에 password 평문 보관 없음 (유출 위험 0)
  - 권한이 본인 role 에 자동 반영 — 별도 grant 작업 불필요
  - 퇴사 / 이직 시 SSO 끊기면 자동 종료
- **단점**: 헤드리스 환경 (Docker / CI) 에서 동작 안 함 (브라우저 팝업 필요)

### ⚠️ 옵션 B: Service Account + Password — 헤드리스 환경 또는 SSO 불가 시

Snowflake credentials 는 다음 방식으로만 전달:

**1순위 — 1Password Share**

- AX팀이 1Password 의 "Share" 기능으로 1회용 share link 생성
- 운영자에게 별도 채널 (Slack DM 본인 한정) 로 link 전달
- 운영자가 link 열어서 값 복사 → `.env` 직접 입력
- Share link 는 24시간 후 만료 (또는 사용 1회 후 만료 설정)

**2순위 — GPG Encrypted File**

- 사전에 GPG 공개키 교환
- AX팀이 GPG 로 `.env.encrypted` 생성 → 보안 채널 (회사 이메일 + 직접 확인) 로 전달
- 운영자가 자기 GPG private key 로 복호화 → `.env` 로 사용

### ❌ 금지 패턴 (옵션 B 한정)

옵션 B 사용 시 다음 방식으로 password 받지 마세요. 받았으면 즉시 신고:

- Plain email (제목/본문에 password 직접 포함)
- Slack 일반 채널 메시지
- 단톡방 메시지
- USB unencrypted 파일
- GitHub commit (history 에 영구 잔존)
- 화면 캡쳐 (스크린샷)

옵션 A (SSO) 사용 시 password 자체가 없어서 이 패턴들 모두 해당 안 됨 — 또 하나의 SSO 장점.

---

## 셀프 서비스 — 문제 해결 자원

순서대로 시도:

### 1. Claude Code

가장 빠른 셀프 서비스. 에러 메시지 + 본 디렉토리 구조를 Claude Code 에 붙여넣고:

> "order-ai-share 의 [에러 메시지 / 증상] 입니다. CLAUDE.md / SETUP.md 참고해서 트러블슈팅 도와주세요"

Claude Code 는 [`CLAUDE.md`](./CLAUDE.md) 의 가드레일을 이해하고 변경 가능 영역에서만 수정 제안합니다.

### 2. 문서

| 증상 / 의문 | 참고 문서 |
|---|---|
| 처음 셋업 | [`SETUP.md`](./SETUP.md) |
| 빌드/실행 에러 | [`SETUP.md`](./SETUP.md) Troubleshooting FAQ |
| 코드 수정하고 싶은데 어디 만져야 할지 | [`CLAUDE.md`](./CLAUDE.md) §1 변경 가능 vs 금지 영역 |
| PLC 관련 | [`docs/PLC_GUIDE.md`](./docs/PLC_GUIDE.md) |
| 변경 후 검증 방법 | [`CLAUDE.md`](./CLAUDE.md) §3 검증 명령 |

### 3. Git history

본인 (또는 다른 사업부 멤버) 가 과거에 같은 문제를 어떻게 해결했는지:

```bash
git log --oneline --all
git log -p -- path/to/file_with_issue
```

### 4. AX팀 contact (최후 수단)

**언제 AX팀에 연락:**

- Cold-start 브랜드 seed PLC 요청 (1회 한정)
- 보안 사고 (credential 유출 의심)

**언제 AX팀에 연락하지 X:**

- 일반 운영 트러블슈팅 → 셀프 서비스 우선
- 코드 변경 요청 → 본인 책임으로 수정
- 새 기능 요청 → 본인 책임으로 추가

연락 방법: AX팀 채널 / 매니저 경유. 회신 SLA 없음.

---

## PLC 재생성 가이드

새 시즌 raw 데이터가 누적되면 PLC 재생성 권장:

```bash
.venv/bin/python scripts/plc_engine/build_plc_standard.py
```

자동 출력:

- **Drift report** — 기존 PLC 대비 평균 MAPE:
  - <5%: 변화 미미. 재생성 효과 없음. 출시 보류 권장.
  - 5–30%: 정상 적응. 새 표준 사용.
  - >30%: 큰 차이. raw 데이터 검증 후 재실행.
- **Coverage report** — 처리된 아이템 수 + insufficient data fallback 수

자세히 → [`docs/PLC_GUIDE.md`](./docs/PLC_GUIDE.md).

---

## Update 정책 (severance)

본 fork 는 **upstream sync 가 없습니다.** AX팀이 다른 fork 나 main repo 에서 발견한 bug fix 는 본 fork 에 자동 반영되지 않습니다.

그래서 사업부에서 발견한 bug 는 본인이 fix 해야 합니다 (Claude Code 활용 권장).

예외:

- **심각한 보안 취약점 (CVE 등)**: AX팀이 patch 노트 + 수정 위치 공지 — 사업부가 직접 적용
- **데이터 스키마 breaking change** (Snowflake 측 컬럼 rename 등): AX팀이 1회 공지 + migration guide 제공

---

## 사고 대응

### Credential 유출 의심

1. 즉시 `.env` 의 `SNOWFLAKE_PASSWORD` 무효화 (Snowflake 콘솔)
2. AX팀 채널에 1순위 알림
3. 새 service account 발급 요청 (1Password share 로 받음)

### 코드 손상 (git reset 가능)

```bash
git status                # 현재 변경사항 확인
git stash                 # 작업 중인 변경 안전 보관
git reset --hard HEAD~1   # 직전 커밋으로 돌리기 (또는 특정 커밋)
git stash pop             # 안전 보관한 변경 복원
```

### 데이터 손상 (DuckDB 재생성)

```bash
rm -f data/production/order_ai.duckdb
.venv/bin/python scripts/run_all.py   # 6 step 자동 실행 → public/*.json + DuckDB 재생성
```

본인 사물함 reset (`data/user-storage/` 통째 또는 특정 시즌):

```bash
rm -rf data/user-storage/{brand}/{season}/   # 본인 책임
```

또는 UI 우상단 Reset 버튼 사용.
