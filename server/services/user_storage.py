"""
사용자 사물함 — 로컬 파일시스템 (order-ai-share).

원본 풀버전의 S3 Presigned URL 기반에서 로컬 파일시스템으로 대체.
share 모델은 단일 운영자가 manual 로 파이프라인을 실행하므로
pipeline_version 추적 / stale 검증은 제거됨 (v3-#4).

저장 경로:
  data/user-storage/{brand}/{season}/{filename}

USER_STORAGE_PATH 환경변수로 root override 가능 (Docker volume 매핑 등).

호환성 — routers/lite.py 가 호출하는 인터페이스:
  - read_with_fallback(email, brand, season, filename) → dict | None
  - read_user_only(email, brand, season, filename)     → dict | None
  - write_user_file(email, brand, season, filename, data) → bool
  - delete_user_file(email, brand, season, filename)   → bool
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_DIR = os.environ.get("USER_STORAGE_PATH", "data/user-storage")


def _file_path(email: str, brand: str, season: str, filename: str) -> str:
    """
    경로 빌더. share 모델은 단일 사용자라 email 은 경로에 사용하지 않음 —
    인터페이스 호환만 유지.
    """
    return os.path.join(_BASE_DIR, brand.lower(), season.lower(), filename)


async def read_with_fallback(
    email: str, brand: str, season: str, filename: str
) -> Optional[dict]:
    """본인 사물함 조회. share 모델은 본인=공용이므로 단일 경로 조회."""
    return await read_user_only(email, brand, season, filename)


async def read_user_only(
    email: str, brand: str, season: str, filename: str
) -> Optional[dict]:
    """본인 사물함 조회. 파일 없으면 None."""
    path = _file_path(email, brand, season, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[user_storage] read 실패 ({path}): {e}")
        return None


async def write_user_file(
    email: str, brand: str, season: str, filename: str, data: dict
) -> bool:
    """본인 사물함에 저장. 디렉토리 자동 생성."""
    path = _file_path(email, brand, season, filename)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[user_storage] saved {path}")
        return True
    except PermissionError:
        logger.error(
            f"[user_storage] PermissionError writing {path} — 파일 시스템 권한 점검 필요"
        )
        raise
    except Exception as e:
        logger.error(f"[user_storage] write 실패 ({path}): {e}")
        return False


async def delete_user_file(
    email: str, brand: str, season: str, filename: str
) -> bool:
    """본인 사물함에서 삭제 (Reset). 파일이 없어도 True (idempotent)."""
    path = _file_path(email, brand, season, filename)
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"[user_storage] deleted {path}")
        return True
    except Exception as e:
        logger.error(f"[user_storage] delete 실패 ({path}): {e}")
        return False
