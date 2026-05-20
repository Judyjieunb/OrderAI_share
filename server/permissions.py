"""
권한 stub (order-ai-share).

share 모델은 단일 브랜드 + 단일 운영자. 권한 매트릭스 없음.
원본 풀버전의 DuckDB users 조회 / DCS AI role 매핑은 전부 제거됨.

호환성: routers/lite.py 가 `require_brand_access` 와 `list_user_brands_only` 를
Depends() 로 호출하는 인터페이스는 그대로 유지 — 함수 시그니처만 단순화.
"""

import os

from fastapi import Header, Query


def _get_configured_brand() -> str:
    """BRAND 환경변수 (대문자 정규화). 미설정 시 빈 문자열."""
    return os.getenv("BRAND", "").strip().upper()


def require_brand_access(
    brand: str = Query(...),
    x_user_email: str = Header(default="operator@local", alias="X-User-Email"),
) -> str:
    """모든 접근 허용. user_email 만 반환 — 사물함 경로 식별용."""
    return x_user_email


def list_user_brands_only(
    x_user_email: str = Header(default="operator@local", alias="X-User-Email"),
) -> list[str]:
    """설정된 단일 브랜드 반환."""
    brand = _get_configured_brand()
    return [brand] if brand else []
