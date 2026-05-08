"""app/services/redis_service.py — Optional Redis. App runs fine without it."""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("aria.redis")
_client = None
_ok = False


async def init(url: str) -> None:
    global _client, _ok
    if not url:
        logger.info("Redis disabled (no REDIS_URL)")
        return
    try:
        import redis.asyncio as aioredis
        c = aioredis.from_url(url, socket_connect_timeout=5, socket_timeout=5,
                              retry_on_timeout=True, decode_responses=True)
        await asyncio.wait_for(c.ping(), timeout=5)
        _client = c
        _ok = True
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning("⚠️  Redis unavailable: %s — running without cache", e)


async def close() -> None:
    global _client, _ok
    if _client:
        await _client.close()
        _ok = False


def available() -> bool:
    return _ok


async def get(key: str) -> Optional[str]:
    if not _ok or not _client:
        return None
    try:
        return await asyncio.wait_for(_client.get(key), timeout=2)
    except Exception:
        return None


async def set(key: str, value: str, ttl: int = 3600) -> bool:
    if not _ok or not _client:
        return False
    try:
        await asyncio.wait_for(_client.setex(key, ttl, value), timeout=2)
        return True
    except Exception:
        return False