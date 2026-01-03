"""
Redis Client

Async Redis connection and utilities.
"""

from typing import Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from app.config.settings import settings
from app.core.logging import logger


class _RedisState:
    """Container for Redis connection state."""

    pool: Optional[Redis] = None


_state = _RedisState()


async def init_redis() -> None:
    """Initialize Redis connection pool."""
    logger.info("Initializing Redis connection")
    try:
        _state.pool = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_POOL_SIZE,
        )
        # Test connection
        await _state.pool.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        raise


async def close_redis() -> None:
    """Close Redis connection pool."""
    if _state.pool:
        logger.info("Closing Redis connection")
        await _state.pool.close()
        _state.pool = None
        logger.info("Redis connection closed")


def get_redis() -> Redis:
    """Get Redis connection.

    Returns:
        Redis client instance

    Raises:
        RuntimeError: If Redis not initialized
    """
    if _state.pool is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _state.pool


class RedisCache:
    """Helper class for common Redis cache operations."""

    def __init__(self, prefix: str = "") -> None:
        """Initialize cache with optional key prefix.

        Args:
            prefix: Prefix for all keys (e.g., "policy:")
        """
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Build full key with prefix."""
        return f"{self.prefix}{key}" if self.prefix else key

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        redis_client = get_redis()
        return await redis_client.get(self._key(key))

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        redis_client = get_redis()
        if ttl:
            await redis_client.setex(self._key(key), ttl, value)
        else:
            await redis_client.set(self._key(key), value)

    async def delete(self, key: str) -> None:
        """Delete key from cache.

        Args:
            key: Cache key
        """
        redis_client = get_redis()
        await redis_client.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        redis_client = get_redis()
        return bool(await redis_client.exists(self._key(key)))

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a counter.

        Args:
            key: Cache key
            amount: Increment amount

        Returns:
            New counter value
        """
        redis_client = get_redis()
        return await redis_client.incrby(self._key(key), amount)

    async def expire(self, key: str, ttl: int) -> None:
        """Set expiration on a key.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds
        """
        redis_client = get_redis()
        await redis_client.expire(self._key(key), ttl)
