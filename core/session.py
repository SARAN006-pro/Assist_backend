import redis.asyncio as redis
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from config import settings

logger = logging.getLogger("aria.session")


class SessionManager:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self._redis_available = False

    async def connect(self):
        """Connect to Redis with graceful failure - app runs without Redis if unavailable."""
        try:
            # Check if REDIS_URL is set and valid
            if not settings.REDIS_URL or settings.REDIS_URL == "redis://localhost:6379":
                # Default URL without actual Redis - skip connection
                logger.warning("REDIS_URL not configured, running without session persistence")
                return

            self.redis = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self.redis.ping()
            self._redis_available = True
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}. Running without session persistence.")
            self.redis = None
            self._redis_available = False

    async def close(self):
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")

    @property
    def is_available(self) -> bool:
        """Check if Redis is available for session operations."""
        return self._redis_available and self.redis is not None

    async def create(self, user_email: str) -> str:
        """Create a new session and return session_id."""
        session_id = str(uuid.uuid4())

        if self.is_available:
            try:
                await self.redis.hset(f"session:{session_id}", mapping={
                    "user_email": user_email,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                await self.redis.expire(f"session:{session_id}", settings.SESSION_TTL)
                await self.redis.set(f"history:{session_id}", json.dumps([]))
                await self.redis.expire(f"history:{session_id}", settings.SESSION_TTL)
            except Exception as e:
                logger.error(f"Redis session creation failed: {e}")
                # Continue with session_id even if Redis fails
        else:
            logger.info(f"Created session {session_id} (no Redis - stateless mode)")

        return session_id

    async def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a session."""
        if not self.is_available:
            return []

        try:
            history_json = await self.redis.get(f"history:{session_id}")
            if history_json:
                return json.loads(history_json)
        except Exception as e:
            logger.error(f"Redis get_history failed: {e}")
        return []

    async def save_history(self, session_id: str, history: List[Dict[str, str]]):
        """Save conversation history, trimming to last 40 messages."""
        if not self.is_available:
            return

        try:
            trimmed = history[-40:]
            await self.redis.set(f"history:{session_id}", json.dumps(trimmed))
            await self.redis.expire(f"history:{session_id}", settings.SESSION_TTL)
        except Exception as e:
            logger.error(f"Redis save_history failed: {e}")

    async def get_email(self, session_id: str) -> Optional[str]:
        """Get user email for a session."""
        if not self.is_available:
            return None

        try:
            return await self.redis.hget(f"session:{session_id}", "user_email")
        except Exception as e:
            logger.error(f"Redis get_email failed: {e}")
            return None

    async def delete(self, session_id: str):
        """Delete a session and its history."""
        if not self.is_available:
            return

        try:
            await self.redis.delete(f"session:{session_id}")
            await self.redis.delete(f"history:{session_id}")
        except Exception as e:
            logger.error(f"Redis delete failed: {e}")


session_manager = SessionManager()