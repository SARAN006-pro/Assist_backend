"""app/core/config.py — Safe configuration. Never raises on missing env vars."""
import os
import logging

logger = logging.getLogger("aria.config")


class Settings:
    # Railway sets PORT automatically — never hardcode
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    APP_NAME: str = os.getenv("APP_NAME", "ARIA")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-change-me")

    # AI — any one is enough
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    AI_TIMEOUT: int = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))

    # Optional
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    def log_status(self):
        logger.info("Config | env=%s port=%s model=%s", self.ENVIRONMENT, self.PORT, self.AI_MODEL)
        if not any([self.OPENAI_API_KEY, self.ANTHROPIC_API_KEY, self.GEMINI_API_KEY]):
            logger.warning("No AI API key set — chat returns echo responses")
        if not self.REDIS_URL:
            logger.info("Redis disabled (no REDIS_URL)")


settings = Settings()