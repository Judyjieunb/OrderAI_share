"""
FastAPI backend — Order AI Share (Lite-only).

Minimal server: shared + lite routers only.
No Full mode, no S3 (Phase 3 에서 제거), no DCS AI auth (Phase 2 에서 stub).

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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers (shared + lite ONLY) ---
from server.routers import shared as _shared_router   # noqa: E402
from server.routers import lite as _lite_router       # noqa: E402
app.include_router(_shared_router.router)
app.include_router(_lite_router.router)

# --- Pipeline trigger endpoint with 5min cooldown [v3-#6] ---
_pipeline_lock = threading.Lock()
_pipeline_last_run: float = 0.0  # Unix timestamp
_COOLDOWN_SECONDS = 5 * 60       # 5분


@app.post("/api/run-pipeline")
async def run_pipeline():
    """Run the analysis pipeline (scripts/run_all.py).

    동시 호출 방지: lock + 5분 cooldown.
    """
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
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }
    finally:
        _pipeline_lock.release()
