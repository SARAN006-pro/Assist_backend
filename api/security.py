from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import logging
from collections import defaultdict
from typing import Callable
from config import settings

logger = logging.getLogger("aria.security")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)

        if settings.SECURITY_HEADERS_ENABLED:
            # Prevent clickjacking
            response.headers["X-Frame-Options"] = "DENY"
            # Prevent MIME type sniffing
            response.headers["X-Content-Type-Options"] = "nosniff"
            # Enable XSS filter
            response.headers["X-XSS-Protection"] = "1; mode=block"
            # Referrer policy
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            # Content Security Policy
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.groq.com"
            # Permissions Policy
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.requests: defaultdict = defaultdict(list)
        self.max_requests = settings.RATE_LIMIT_REQUESTS
        self.window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS

    async def dispatch(self, request: Request, call_next: Callable):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Clean old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < self.window_seconds
        ]

        # Check rate limit
        if len(self.requests[client_ip]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {self.max_requests} requests per {self.window_seconds} seconds",
                    "retry_after": self.window_seconds
                }
            )

        # Add current request
        self.requests[client_ip].append(current_time)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            self.max_requests - len(self.requests[client_ip])
        )
        return response


class SecureErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Handle errors securely without exposing sensitive information"""

    async def dispatch(self, request: Request, call_next: Callable):
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as exc:
            logger.error(f"Unhandled exception: {exc}", exc_info=True)

            # Don't expose internal errors in production
            if settings.is_production:
                error_message = "An internal error occurred"
            else:
                error_message = str(exc)

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal server error",
                    "message": error_message,
                    "request_id": request.headers.get("X-Request-ID", "unknown")
                }
            )


def setup_security_middleware(app):
    """Setup all security middleware"""
    app.add_middleware(SecureErrorHandlerMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)