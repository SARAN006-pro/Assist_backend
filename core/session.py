import redis.asyncio as redis
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional
from config import settings


class SessionManager:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def close(self):
        if self.redis:
            await self.redis.close()

    async def create(self, user_email: str) -> str:
        """Create a new session and return session_id."""
        session_id = str(uuid.uuid4())
        await self.redis.hset(f"session:{session_id}", mapping={
            "user_email": user_email,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        await self.redis.expire(f"session:{session_id}", settings.SESSION_TTL)
        # Initialize empty history
        await self.redis.set(f"history:{session_id}", json.dumps([]))
        await self.redis.expire(f"history:{session_id}", settings.SESSION_TTL)
        return session_id

    async def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a session."""
        history_json = await self.redis.get(f"history:{session_id}")
        if history_json:
            return json.loads(history_json)
        return []

    async def save_history(self, session_id: str, history: List[Dict[str, str]]):
        """Save conversation history, trimming to last 40 messages."""
        # Trim to last 40 messages
        trimmed = history[-40:]
        await self.redis.set(f"history:{session_id}", json.dumps(trimmed))
        # Refresh TTL
        await self.redis.expire(f"history:{session_id}", settings.SESSION_TTL)

    async def get_email(self, session_id: str) -> Optional[str]:
        """Get user email for a session."""
        return await self.redis.hget(f"session:{session_id}", "user_email")

    async def delete(self, session_id: str):
        """Delete a session and its history."""
        await self.redis.delete(f"session:{session_id}")
        await self.redis.delete(f"history:{session_id}")


session_manager = SessionManager()