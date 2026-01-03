"""Cache module for Redis operations."""

from app.cache.redis_client import (
    get_redis,
    init_redis,
    close_redis,
)

__all__ = [
    "get_redis",
    "init_redis",
    "close_redis",
]
