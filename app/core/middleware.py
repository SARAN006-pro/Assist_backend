"""app/core/middleware.py — Tracing middleware. Catches all unhandled exceptions."""
import logging
import time
import traceback
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("aria.middleware")


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = str(uuid.uuid4())[:8]
        request.state.request_id = rid
        t0 = time.perf_counter()
        logger.info("→ %s %s id=%s", request.method, request.url.path, rid)
        try:
            response = await call_next(request)
            ms = (time.perf_counter() - t0) * 1000
            logger.info("← %s %s id=%s status=%d %.0fms",
                        request.method, request.url.path, rid, response.status_code, ms)
            response.headers["X-Request-ID"] = rid
            return response
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000
            logger.error("💥 CRASH id=%s %.0fms\n%s", rid, ms, traceback.format_exc())
            return JSONResponse(status_code=500, content={
                "error": "internal_server_error",
                "request_id": rid,
                "exc_type": type(exc).__name__,
                "message": str(exc),
            })