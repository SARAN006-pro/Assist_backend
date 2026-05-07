import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import aiosqlite
from pathlib import Path

from api import auth, chat, system, voice
from api.security import setup_security_middleware
from core.session import session_manager
from config import settings
from middleware import ProductionMiddleware

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("aria")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting ARIA backend (env: {settings.APP_ENV})...")
    logger.info(f"Security: rate_limit={settings.RATE_LIMIT_ENABLED}, cors={settings.CORS_ORIGINS}")

    # Redis connection with graceful failure
    try:
        await session_manager.connect()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Running without session persistence.")

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
        logger.info("Audit database initialized")
    except Exception as e:
        logger.warning(f"Audit database initialization failed: {e}. Continuing without audit logging.")

    await auth.init_users_db()
    logger.info(f"ARIA backend started (model: {settings.GROQ_MODEL})")
    yield
    await session_manager.close()
    logger.info("ARIA backend stopped")


app = FastAPI(
    title="ARIA API",
    version="1.0.0",
    description="Autonomous Resource & Intelligence Assistant",
    lifespan=lifespan,
)

# Add request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response

# Setup security middleware
setup_security_middleware(app)

# Add production middleware (exception handling, request tracing)
app.add_middleware(ProductionMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

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


@app.get("/health")
async def health():
    redis_status = "disconnected"
    if session_manager.is_available:
        try:
            await session_manager.redis.ping()
            redis_status = "connected"
        except Exception as e:
            logger.warning(f"Health check Redis error: {e}")

    return {
        "status": "online",
        "service": "ARIA",
        "redis": redis_status,
        "model": settings.GROQ_MODEL,
        "version": "1.0.0",
        "environment": settings.APP_ENV
    }


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