"""
app/routers/health.py
======================
Health check endpoints — Railway REQUIRES these to respond in < healthcheckTimeout.

RULES:
  - Must return 200 instantly
  - Must NOT require auth
  - Must NOT depend on Redis, DB, or AI being up
  - Both GET / and GET /health must work
"""
import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.core.config import settings

router = APIRouter()


@router.get("/")
async def root():
    """Railway default health check target."""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@router.get("/health")
async def health():
    """Detailed health — always 200, shows degraded state not error."""
    return JSONResponse(status_code=200, content={
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": round(time.time(), 2),
    })


@router.get("/ping")
async def ping():
    """Instant liveness probe."""
    return {"ping": "pong", "ts": round(time.time(), 2)}