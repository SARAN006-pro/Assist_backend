"""
middleware.py
=============
Production middleware stack for ARIA Backend.

Catches ALL unhandled exceptions before they become raw 500s.
Adds X-Request-ID to every response for log tracing.
"""

import time
import uuid
import traceback
import logging
import sys
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Network_backend logging pattern
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    force=True,
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
        skip_logging = request.url.path in ["/health", "/docs", "/openapi.json", "/"]

        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        request.state.request_id = request_id

        if not skip_logging:
            logger.info(
                "→ %s %s | id=%s | ip=%s",
                request.method,
                request.url.path,
                request_id,
                request.client.host if request.client else "unknown",
            )

        try:
            response = await call_next(request)

            if not skip_logging:
                ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "← %s %s | id=%s | status=%d | %.0fms",
                    request.method,
                    request.url.path,
                    request_id,
                    response.status_code,
                    ms,
                )
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            ms = (time.perf_counter() - start) * 1000
            logger.error(
                "💥 CRASH | id=%s | %s %s | %.0fms\n%s",
                request_id,
                request.method,
                request.url.path,
                ms,
                traceback.format_exc(),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "An unexpected error occurred. Our team has been notified.",
                    "request_id": request_id,
                    "exc_type": type(exc).__name__,
                },
                headers={"X-Request-ID": request_id},
            )