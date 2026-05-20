"""
서버 공통 비즈니스 로직 (lite·full 양쪽이 import).

routers/lite.py ↔ routers/full.py 간 직접 import는 금지 — 공통 함수는 본 패키지에서만 제공.

모듈:
- user_storage: lite-user/{email}/ 영역 read/write (본인 사물함)
- order_calc: 발주 추천 + 예산 ceiling (Step 1.3에서 추출 예정)
- color_allocation: 컬러배분 3단계 매칭 (Step 1.2에서 추출 예정)
"""
