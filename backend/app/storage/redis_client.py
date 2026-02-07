import json
from typing import Optional, List, Dict, Any
from datetime import datetime

import redis.asyncio as redis

from app.config import settings


class RedisClient:
    """Redis client for session caching"""

    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.session_ttl = settings.session_ttl_hours * 3600

    async def connect(self):
        """Connect to Redis"""
        self.redis = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()

    async def ping(self) -> bool:
        """Check Redis connection"""
        try:
            if self.redis:
                await self.redis.ping()
                return True
            return False
        except Exception:
            return False

    # ============ Session Operations ============

    async def get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get session data from Redis"""
        key = f"session:{session_token}"
        data = await self.redis.hgetall(key)
        if not data:
            return None

        # Parse JSON fields
        if "fields_status" in data:
            data["fields_status"] = json.loads(data["fields_status"])
        if "context" in data:
            data["context"] = json.loads(data["context"])

        return data

    async def set_session(
        self,
        session_token: str,
        session_id: str,
        current_phase: int,
        fields_status: Dict[str, Any],
        context: Dict[str, Any] = None,
        user_id: str = None
    ):
        """Save session data to Redis"""
        key = f"session:{session_token}"
        data = {
            "id": session_id,
            "current_phase": str(current_phase),
            "fields_status": json.dumps(fields_status),
            "context": json.dumps(context or {}),
            "last_activity": str(int(datetime.utcnow().timestamp()))
        }
        if user_id:
            data["user_id"] = user_id

        await self.redis.hset(key, mapping=data)
        await self.redis.expire(key, self.session_ttl)

    async def update_session_field(
        self,
        session_token: str,
        field: str,
        value: Any
    ):
        """Update a single session field"""
        key = f"session:{session_token}"
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        await self.redis.hset(key, field, str(value))

    async def delete_session(self, session_token: str):
        """Delete session from Redis"""
        key = f"session:{session_token}"
        await self.redis.delete(key)

    # ============ Message Cache Operations ============

    async def add_message(
        self,
        session_token: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Add message to cache"""
        key = f"session:{session_token}:messages"
        message = {
            "role": role,
            "content": content,
            "metadata": metadata,
            "ts": int(datetime.utcnow().timestamp())
        }
        await self.redis.lpush(key, json.dumps(message))
        # Keep only recent messages
        await self.redis.ltrim(key, 0, settings.max_messages_cached - 1)
        await self.redis.expire(key, self.session_ttl)

    async def get_messages(
        self,
        session_token: str,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """Get cached messages"""
        key = f"session:{session_token}:messages"
        limit = limit or settings.max_messages_cached
        messages = await self.redis.lrange(key, 0, limit - 1)
        # Reverse to get chronological order
        return [json.loads(m) for m in reversed(messages)]

    # ============ Rate Limiting ============

    async def check_rate_limit(self, session_token: str) -> bool:
        """Check if session is rate limited"""
        key = f"ratelimit:{session_token}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 60)
        return count <= settings.rate_limit_per_minute

    # ============ Privacy Modal Flag ============

    async def is_privacy_shown(self, session_token: str) -> bool:
        """Check if privacy modal has been shown"""
        key = f"privacy_shown:{session_token}"
        return await self.redis.exists(key) > 0

    async def set_privacy_shown(self, session_token: str):
        """Mark privacy modal as shown"""
        key = f"privacy_shown:{session_token}"
        await self.redis.set(key, "1", ex=7 * 24 * 3600)  # 7 days


# Global Redis client instance
_redis_client: Optional[RedisClient] = None
_use_memory_fallback = False


async def get_redis():
    """Get Redis client instance, falls back to memory client if Redis unavailable"""
    global _redis_client, _use_memory_fallback

    if _use_memory_fallback:
        from app.storage.memory_client import get_memory_client
        return await get_memory_client()

    if _redis_client is None:
        _redis_client = RedisClient()
        try:
            await _redis_client.connect()
            if not await _redis_client.ping():
                raise Exception("Redis ping failed")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Redis not available, using memory fallback: {e}"
            )
            _use_memory_fallback = True
            from app.storage.memory_client import get_memory_client
            return await get_memory_client()

    return _redis_client


async def close_redis():
    """Close Redis connection"""
    global _redis_client, _use_memory_fallback
    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None
    if _use_memory_fallback:
        from app.storage.memory_client import close_memory_client
        await close_memory_client()
        _use_memory_fallback = False
