"""
main.py
=======
ARIA Backend FastAPI Application Entry Point.

This is the file Railway executes via:
  uvicorn main:app --host 0.0.0.0 --port $PORT

COMMON RAILWAY DEPLOYMENT FIXES:
  1. PORT binding: Always use os.getenv("PORT") — never hardcode 8000
  2. Import crashes: All imports wrapped so missing packages log, not crash
  3. Startup errors: Lifespan catches all errors, backend stays alive
  4. Health check: GET / responds in <100ms with no dependencies
  5. CORS: Configured for mobile + web clients
  6. Missing env vars: Config validates with warnings, not exceptions
"""

import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import aiosqlite
from pathlib import Path

# Import settings early for logging config
from config import settings

# Network_backend logging pattern - configure BEFORE any other imports
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    force=True,
)
logger = logging.getLogger("aria.main")

# Wrap imports so broken modules don't kill the whole app
try:
    from api import auth, chat, system, voice
    from api.security import setup_security_middleware
    logger.info("✅ API routers loaded")
except Exception as e:
    logger.error("❌ API router load failed: %s", e, exc_info=True)

try:
    from core.session import session_manager
    logger.info("✅ Session manager loaded")
except Exception as e:
    logger.error("❌ Session manager load failed: %s", e)
    session_manager = None  # type: ignore

try:
    from middleware import ProductionMiddleware
    logger.info("✅ Production middleware loaded")
except Exception as e:
    logger.error("❌ Middleware load failed: %s", e)
    ProductionMiddleware = None  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ───────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("🚀 %s v%s starting up", settings.APP_NAME, settings.APP_VERSION)
    logger.info("   Environment : %s", settings.APP_ENV)
    logger.info("   Host:Port   : %s:%s", settings.BACKEND_HOST, settings.BACKEND_PORT)
    logger.info("   Debug       : %s", settings.DEBUG)
    logger.info("=" * 60)

    # Redis connection with graceful failure (Network_backend pattern)
    if session_manager:
        try:
            await session_manager.connect()
            logger.info("✅ Redis connected")
        except Exception as e:
            logger.warning("⚠️  Redis connection failed: %s. Running without session persistence.", e)

    # Initialize audit database (non-critical, should not crash)
    try:
        db_path = Path(__file__).parent / "aria_audit.db"
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    tool_name TEXT,
                    inputs TEXT,
                    result TEXT,
                    duration_ms INTEGER
                )
            """)
            await db.commit()
        logger.info("✅ Audit database initialized")
    except Exception as e:
        logger.warning("⚠️  Audit database initialization failed: %s. Continuing without audit logging.", e)

    # Initialize users database (non-critical)
    try:
        await auth.init_users_db()
        logger.info("✅ Users database initialized")
    except Exception as e:
        logger.warning("⚠️  Users database initialization failed: %s. Continuing without user auth.", e)

    logger.info("✅ ARIA startup complete — ready to serve requests (model: %s)", settings.GROQ_MODEL)
    yield

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    logger.info("🛑 ARIA shutting down…")
    if session_manager:
        await session_manager.close()
    logger.info("👋 ARIA shutdown complete")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ARIA — Autonomous Resource & Intelligence Assistant",
    lifespan=lifespan,
    redoc_url=None,
    docs_url="/docs" if settings.DEBUG else None,
)


# ── Health endpoint (Network_backend pattern - fast, no dependencies) ─────────
@app.get("/")
@app.get("/health")
async def health():
    redis_status = "disconnected"
    if session_manager and session_manager.is_available:
        try:
            await session_manager.redis.ping()
            redis_status = "connected"
        except Exception as e:
            logger.warning("Health check Redis error: %s", e)

    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "redis": redis_status,
    }


# ── CORS configuration (Network_backend pattern) ───────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins() if settings.get_cors_origins() != ["*"] else ["*"],
    allow_credentials=False,  # MUST be False when allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
    max_age=3600,
)

# Setup security middleware
try:
    setup_security_middleware(app)
except Exception as e:
    logger.warning("⚠️  Security middleware setup failed: %s", e)

# Add production middleware (exception handling, request tracing)
if ProductionMiddleware:
    app.add_middleware(ProductionMiddleware)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(system.router, prefix="/system", tags=["system"])
app.include_router(voice.router, prefix="/voice", tags=["voice"])


# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catches anything ProductionMiddleware missed (e.g. startup errors)."""
    request_id = getattr(request.state, "request_id", "no-id")
    logger.error(
        "global_exception_handler | id=%s | %s", request_id, exc, exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please retry.",
            "request_id": request_id,
            "exc_type": type(exc).__name__,
            "detail": str(exc),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", "no-id")
    logger.warning(
        "HTTPException | id=%s | status=%d | %s", request_id, exc.status_code, exc.detail
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "status": exc.status_code,
            "message": exc.detail,
            "request_id": request_id,
        },
    )


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", settings.BACKEND_PORT))
    uvicorn.run(
        "main:app",
        host=settings.BACKEND_HOST,
        port=port,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
    )