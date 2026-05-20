"""
공통 라우터 — order-ai-share (3 endpoints).

- GET /api/health              헬스체크
- GET /api/brand-config        현재 brand_config.json 조회
- GET /api/s3/file/{filename}  로컬 JSON 파일 조회 (public/ + data/user-storage/)

share 모델은 S3 없음 — 모든 파일을 로컬 파일시스템에서 서빙.
endpoint 경로(`/api/s3/file/...`)는 프론트 호환을 위해 유지.
"""

import json
import os

from fastapi import APIRouter, Depends, Header, HTTPException

# 경로 — server/routers/shared.py 기준 3단계 위 = 프로젝트 루트
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
USER_STORAGE_DIR = os.environ.get(
    "USER_STORAGE_PATH",
    os.path.join(BASE_DIR, "data", "user-storage"),
)
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
    """현재 brand_config.json 반환 (없으면 빈 dict)."""
    if os.path.exists(BRAND_CONFIG_PATH):
        with open(BRAND_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@router.get("/api/s3/file/{filename}")
async def get_local_file(
    filename: str, user_email: str = Depends(get_user_email)
):
    """
    로컬 파일 조회 — 화이트리스트 검증 후
    1순위 data/user-storage/, 2순위 public/.
    """
    if filename not in _ALLOWED_FILES:
        raise HTTPException(status_code=400, detail="허용되지 않은 파일입니다.")

    # 1순위: 본인 사물함 (전체 user-storage 트리에서 filename 검색)
    if os.path.isdir(USER_STORAGE_DIR):
        for root, _dirs, files in os.walk(USER_STORAGE_DIR):
            if filename in files:
                fpath = os.path.join(root, filename)
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f)

    # 2순위: public/ fallback (baseline)
    local_path = os.path.join(PUBLIC_DIR, filename)
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise HTTPException(status_code=404, detail=f"{filename}을 찾을 수 없습니다.")
