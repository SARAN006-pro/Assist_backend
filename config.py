"""
config.py
=========
Central configuration loader for ARIA Backend.

CRITICAL RULE: Every env var must have a safe default.
A missing env var must NEVER crash the backend at startup —
it should log a warning and degrade gracefully.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os
import logging

logger = logging.getLogger("aria.config")


class Settings(BaseSettings):
    # ── Server ────────────────────────────────────────────────────────────────
    # Railway injects PORT automatically. Never hardcode 8000.
    BACKEND_PORT: int = int(os.getenv("PORT", "8000"))
    BACKEND_HOST: str = os.getenv("HOST", "0.0.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    APP_ENV: str = os.getenv("ENVIRONMENT", "development")

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = os.getenv("APP_NAME", "ARIA")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-in-production")

    # ── Groq AI (OpenAI-compatible API) ────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
    GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", "4096"))
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    # ── Alternative AI Providers (OpenAI, Anthropic, Gemini) ──────────────────
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    AI_TIMEOUT_SECONDS: int = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))

    # ── Security - JWT ────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

    # ── Security - Rate Limiting ────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

    # ── Security - CORS ────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # ── Security - Headers ────────────────────────────────────────────────────
    SECURITY_HEADERS_ENABLED: bool = True

    # ── Redis (optional — app runs without it) ────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_ENABLED: bool = bool(os.getenv("REDIS_URL", ""))
    SESSION_TTL: int = int(os.getenv("SESSION_TTL", "86400"))

    # ── Sandbox ────────────────────────────────────────────────────────────────
    SANDBOX_IMAGE: str = os.getenv("SANDBOX_IMAGE", "python:3.12-slim")
    SANDBOX_TIMEOUT: int = int(os.getenv("SANDBOX_TIMEOUT", "30"))
    ALLOWED_BASE_DIRS: List[str] = ["/home", "/tmp", "/var/log"]

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Handle Railway Redis environment variables
        if os.getenv("REDIS_URL"):
            self.REDIS_URL = os.getenv("REDIS_URL", self.REDIS_URL)
        elif os.getenv("REDIS_HOST") and os.getenv("REDIS_PORT"):
            password = self.REDIS_PASSWORD or ""
            prefix = f":{password}@" if password else ""
            self.REDIS_URL = f"redis://{prefix}{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}"

    def validate(self) -> None:
        """Log warnings for missing important vars — do NOT raise exceptions."""
        # Check AI providers
        if not self.GROQ_API_KEY and not self.OPENAI_API_KEY and not self.ANTHROPIC_API_KEY and not self.GEMINI_API_KEY:
            logger.warning(
                "⚠️  No AI API key found. Set GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY. "
                "Chat endpoints will return errors."
            )

        # Check secret key
        if self.SECRET_KEY == "change-this-in-production":
            logger.warning("⚠️  SECRET_KEY is using default. Set a real value in environment variables.")

        # Check Redis
        if not self.REDIS_ENABLED:
            logger.info("ℹ️  Redis disabled (REDIS_URL not set). Running stateless.")

        logger.info("✅ Config loaded | env=%s | AI_MODEL=%s | Groq=%s",
                     self.APP_ENV, self.AI_MODEL, self.GROQ_MODEL)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    def get_cors_origins(self) -> List[str]:
        """Get CORS origins based on environment"""
        if os.getenv("CORS_ORIGINS"):
            import json
            return json.loads(os.getenv("CORS_ORIGINS", "[]"))

        # Network_backend pattern: wildcard for mobile apps is safe
        if os.getenv("CORS_ORIGINS", "") == "*":
            return ["*"]
        return self.CORS_ORIGINS

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Initialize and validate settings
settings = Settings()
settings.validate()