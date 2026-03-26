"""Redis-based memory store and rate limiting."""

import json
from typing import Any

from redis.asyncio import Redis

from app.config import get_settings


class RedisStore:
    """Manages Redis connection and memory operations."""

    def __init__(self):
        """Initialize Redis connection."""
        settings = get_settings()
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    async def get_client(self) -> Redis:
        """Get raw Redis client."""
        return self.redis

    async def add_message(self, phone: str, role: str, content: str, ttl: int = 86400) -> None:
        """Add a message to the conversation history.
        
        Keeps the last N messages and defaults to a 24-hour TTL.
        """
        key = f"thuk:hist:{phone}"
        msg = {"role": role, "content": content}
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.rpush(key, json.dumps(msg))
            pipe.ltrim(key, -10, -1)  # Keep last 10 messages
            pipe.expire(key, ttl)
            await pipe.execute()

    async def get_history(self, phone: str, limit: int = 6) -> list[dict[str, str]]:
        """Get the latest N messages from history."""
        key = f"thuk:hist:{phone}"
        messages = await self.redis.lrange(key, -limit, -1)
        return [json.loads(m) for m in messages] if messages else []

    async def clear_history(self, phone: str) -> None:
        """Clear conversation history."""
        key = f"thuk:hist:{phone}"
        await self.redis.delete(key)

    async def set_flag(self, phone: str, key: str, value: Any, ttl: int = 60) -> None:
        """Set a temporary flag (e.g., for delete confirmation)."""
        r_key = f"thuk:flag:{phone}:{key}"
        await self.redis.setex(r_key, ttl, json.dumps(value))

    async def get_flag(self, phone: str, key: str) -> Any | None:
        """Get a flag's value."""
        r_key = f"thuk:flag:{phone}:{key}"
        val = await self.redis.get(r_key)
        return json.loads(val) if val else None

    async def delete_flag(self, phone: str, key: str) -> None:
        """Delete a flag."""
        r_key = f"thuk:flag:{phone}:{key}"
        await self.redis.delete(r_key)

    async def check_rate_limit(self, phone: str, max_requests: int = 20, window_secs: int = 60) -> bool:
        """Check if phone number has exceeded rate limit using standard inc + expire.
        
        Returns True if allowed, False if exceeded.
        """
        key = f"thuk:rl:{phone}"
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.ttl(key)
            result = await pipe.execute()
            
        current_count = result[0]
        ttl = result[1]
        
        if current_count == 1 or ttl < 0:
            # First request in window, set expiry
            await self.redis.expire(key, window_secs)
            
        return current_count <= max_requests

# Global instance
store = RedisStore()
