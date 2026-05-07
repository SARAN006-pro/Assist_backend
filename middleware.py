"""
ARIA Backend - Production Middleware
====================================
Global exception handler, structured logging, request tracing.
Prevents all silent crashes and ensures 500s include useful diagnostics.
"""

import time
import uuid
import traceback
import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Structured logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("aria.middleware")


class ProductionMiddleware(BaseHTTPMiddleware):
    """
    Catches ALL unhandled exceptions so FastAPI never returns a raw 500.
    Adds:
      - X-Request-ID header for tracing
      - Request/response duration logging
      - Structured error body on failure
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for health check to reduce noise
        skip_logging = request.url.path in ["/health", "/docs", "/openapi.json"]

        if not skip_logging:
            request_id = str(uuid.uuid4())[:8]
            start = time.perf_counter()
            request.state.request_id = request_id

            logger.info(
                "→ %s %s | id=%s | client=%s",
                request.method,
                request.url.path,
                request_id,
                request.client.host if request.client else "unknown",
            )
        else:
            request_id = str(uuid.uuid4())[:8]
            request.state.request_id = request_id

        try:
            response = await call_next(request)

            if not skip_logging:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "← %s %s | id=%s | status=%d | %.1fms",
                    request.method,
                    request.url.path,
                    request_id,
                    response.status_code,
                    duration_ms,
                )
                response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            if not skip_logging:
                duration_ms = (time.perf_counter() - start) * 1000
                tb = traceback.format_exc()

                logger.error(
                    "💥 UNHANDLED EXCEPTION | id=%s | %s %s | %.1fms\n%s",
                    request_id,
                    request.method,
                    request.url.path,
                    duration_ms,
                    tb,
                )

            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "An unexpected error occurred. Please retry.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )