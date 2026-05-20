"""
서버 라우터 분리 (Step 1.4~1.6에서 신설).

- shared.py: Full/Lite 양쪽이 사용하는 공통 엔드포인트 (3개)
- full.py:   Full 전용 엔드포인트 (운영팀, 11개) — Step 1.5에서 추가
- lite.py:   Lite 전용 엔드포인트 (담당자, 13개) — Step 1.6/Step 5에서 추가

규칙: routers/full.py ↔ routers/lite.py 직접 import 금지. 공통 로직은 server/services/ 경유.
"""
