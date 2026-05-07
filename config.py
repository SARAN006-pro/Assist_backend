from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from urllib.parse import urlparse


class Settings(BaseSettings):
    # Environment
    APP_ENV: str = "development"

    # Groq AI (OpenAI-compatible API)
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    GROQ_MAX_TOKENS: int = 4096
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Security - JWT
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days

    # Security - Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Security - CORS
    # For production, set this to your actual domain via environment variable
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Security - Headers
    SECURITY_HEADERS_ENABLED: bool = True

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # Redis - Railway provides these via environment variables when addon is attached
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: Optional[str] = None
    SESSION_TTL: int = 86400

    # Sandbox
    SANDBOX_IMAGE: str = "python:3.12-slim"
    SANDBOX_TIMEOUT: int = 30
    ALLOWED_BASE_DIRS: List[str] = ["/home", "/tmp", "/var/log"]

    # Logging
    LOG_LEVEL: str = "INFO"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Railway provides PORT env var - override BACKEND_PORT if set
        if os.getenv("PORT"):
            self.BACKEND_PORT = int(os.getenv("PORT"))

        # Handle Railway Redis environment variables
        # Railway sets REDIS_URL when Redis addon is attached
        if os.getenv("REDIS_URL"):
            self.REDIS_URL = os.getenv("REDIS_URL")
        elif os.getenv("REDIS_HOST") and os.getenv("REDIS_PORT"):
            # Fallback: construct from individual env vars
            password = self.REDIS_PASSWORD or ""
            prefix = f":{password}@" if password else ""
            self.REDIS_URL = f"redis://{prefix}{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}"

        # Validate production settings
        if self.APP_ENV == "production":
            weak_keys = (
                "aria-dev-secret-change-in-prod",
                "your-super-secret-key-change-this",
                "change-this-to-a-random-secure-string-in-production",
            )
            if self.SECRET_KEY in weak_keys:
                raise ValueError("SECRET_KEY must be changed for production!")
            if self.CORS_ORIGINS == ["*"]:
                raise ValueError("CORS_ORIGINS cannot be ['*'] in production!")

            for origin in self.get_cors_origins():
                parsed = urlparse(origin)
                if parsed.scheme != "https":
                    raise ValueError("Production CORS_ORIGINS must use https:// URLs")
                if parsed.hostname in {"localhost", "127.0.0.1"}:
                    raise ValueError("Production CORS_ORIGINS cannot point to localhost")

            if not self.REDIS_URL or self.REDIS_URL == "redis://localhost:6379":
                raise ValueError("REDIS_URL must be configured for production with Railway Redis")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    def get_cors_origins(self) -> List[str]:
        """Get CORS origins based on environment"""
        # Allow environment variable to override
        if os.getenv("CORS_ORIGINS"):
            import json
            return json.loads(os.getenv("CORS_ORIGINS"))
        return self.CORS_ORIGINS

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()