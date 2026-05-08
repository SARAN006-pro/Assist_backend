"""
app/main.py — ARIA FastAPI Application
========================================
Every startup step is logged so Railway shows EXACTLY where it fails.

Railway health check failure = one of these causes:
  A) uvicorn never starts     → wrong Procfile command / import crash
  B) uvicorn starts but binds wrong port  → hardcoded port vs $PORT
  C) /health endpoint crashes → dependency in health route
  D) /health responds too slowly → blocked by DB/AI startup call

This file is hardened against all four.
"""

# ── Step 0: Logging first — before ANY other import ──────────────────────────
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    force=True,
)
logger = logging.getLogger("aria.main")
logger.info("=" * 55)
logger.info("ARIA BACKEND — STARTUP SEQUENCE BEGIN")
logger.info("=" * 55)

# ── Step 1: Standard library ──────────────────────────────────────────────────
import os
import traceback
from contextlib import asynccontextmanager

logger.info("[1/7] stdlib imports OK")

# ── Step 2: FastAPI ───────────────────────────────────────────────────────────
try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    logger.info("[2/7] fastapi imports OK")
except ImportError as e:
    logger.critical("[2/7] ❌ fastapi import FAILED: %s", e)
    logger.critical("      Fix: ensure 'fastapi' is in requirements.txt")
    sys.exit(1)

# ── Step 3: Internal config ───────────────────────────────────────────────────
try:
    from app.core.config import settings
    logger.info("[3/7] config OK | env=%s port=%s", settings.ENVIRONMENT, settings.PORT)
    settings.log_status()
except Exception as e:
    logger.critical("[3/7] ❌ config FAILED: %s\n%s", e, traceback.format_exc())
    sys.exit(1)

# ── Step 4: Middleware ────────────────────────────────────────────────────────
try:
    from app.core.middleware import TracingMiddleware
    logger.info("[4/7] middleware OK")
except Exception as e:
    logger.error("[4/7] ⚠️  middleware FAILED (continuing): %s", e)
    TracingMiddleware = None  # type: ignore

# ── Step 5: Services ──────────────────────────────────────────────────────────
try:
    from app.services import redis_service
    logger.info("[5/7] redis_service OK")
except Exception as e:
    logger.warning("[5/7] ⚠️  redis_service unavailable (continuing): %s", e)
    redis_service = None  # type: ignore

# ── Step 6: Routers ───────────────────────────────────────────────────────────
routers_loaded = {}
for name, mod_path in [
    ("health",    "app.routers.health"),
    ("chat",      "app.routers.chat"),
    ("websocket", "app.routers.websocket"),
]:
    try:
        import importlib
        mod = importlib.import_module(mod_path)
        routers_loaded[name] = mod.router
        logger.info("[6/7] router '%s' OK", name)
    except Exception as e:
        logger.error("[6/7] ❌ router '%s' FAILED: %s\n%s", name, e, traceback.format_exc())
        if name == "health":
            logger.critical("      Health router is required — aborting.")
            sys.exit(1)

# ── Step 7: Lifespan ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[7/7] lifespan startup")
    logger.info("  App    : %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("  Port   : %s", os.environ.get("PORT", "8000 (default)"))
    logger.info("  Env    : %s", settings.ENVIRONMENT)

    if redis_service:
        await redis_service.init(settings.REDIS_URL)

    logger.info("=" * 55)
    logger.info("✅ ARIA READY — health check should now pass")
    logger.info("=" * 55)
    yield

    logger.info("ARIA shutting down…")
    if redis_service:
        await redis_service.close()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=False,   # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
logger.info("CORS configured: %s", origins)

if TracingMiddleware:
    app.add_middleware(TracingMiddleware)

# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def _global(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", "no-id")
    logger.error("🔥 GLOBAL HANDLER id=%s %s", rid, exc, exc_info=True)
    return JSONResponse(status_code=500, content={
        "error": "internal_server_error",
        "message": str(exc),
        "exc_type": type(exc).__name__,
        "request_id": rid,
    })

# ── Register routers ──────────────────────────────────────────────────────────
for name, router in routers_loaded.items():
    app.include_router(router)
    logger.info("Router registered: %s", name)

logger.info("Routes: %s", [r.path for r in app.routes if hasattr(r, "path")])

# ── Local dev entrypoint ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    logger.info("Starting local dev server on port %s", port)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)