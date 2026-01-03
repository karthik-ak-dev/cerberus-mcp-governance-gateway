"""
Rate Limit Store

Redis-based rate limiting using sliding window algorithm.
"""

import time
from typing import Optional, Tuple

from app.cache.redis_client import get_redis
from app.core.logging import logger


class RateLimitStore:
    """Redis-based rate limit counter storage."""

    def __init__(self, prefix: str = "ratelimit:") -> None:
        """Initialize rate limit store.

        Args:
            prefix: Redis key prefix
        """
        self.prefix = prefix

    def _build_key(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
        agent_access_id: str,
        tool: Optional[str] = None,
        window: str = "minute",
    ) -> str:
        """Build rate limit key.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
            agent_access_id: Agent Access identifier
            tool: Optional tool name
            window: Time window (second, minute, hour, day)

        Returns:
            Redis key
        """
        tool_part = tool or "_global"
        return (
            f"{self.prefix}{organisation_id}:{mcp_server_workspace_id}:"
            f"{agent_access_id}:{tool_part}:{window}"
        )

    def _get_window_seconds(self, window: str) -> int:
        """Get window duration in seconds.

        Args:
            window: Window name

        Returns:
            Duration in seconds
        """
        windows = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }
        return windows.get(window, 60)

    async def check_and_increment(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
        agent_access_id: str,
        limit: int,
        tool: Optional[str] = None,
        window: str = "minute",
    ) -> Tuple[bool, int, int]:
        """Check rate limit and increment counter.

        Uses sliding window algorithm for accurate rate limiting.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
            agent_access_id: Agent Access identifier
            limit: Maximum requests allowed
            tool: Optional tool name
            window: Time window

        Returns:
            Tuple of (allowed, current_count, retry_after_seconds)
        """
        redis_client = get_redis()
        key = self._build_key(
            organisation_id, mcp_server_workspace_id, agent_access_id, tool, window
        )
        window_seconds = self._get_window_seconds(window)

        # Current timestamp
        now = time.time()
        window_start = now - window_seconds

        # Use pipeline for atomic operations
        pipe = redis_client.pipeline()

        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current entries
        pipe.zcard(key)

        # Execute
        results = await pipe.execute()
        current_count = results[1]

        # Check if under limit
        if current_count < limit:
            # Add new entry
            await redis_client.zadd(key, {str(now): now})
            # Set expiration
            await redis_client.expire(key, window_seconds * 2)

            return True, current_count + 1, 0

        # Rate limit exceeded - calculate retry after
        oldest = await redis_client.zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_time = oldest[0][1]
            retry_after = int(window_seconds - (now - oldest_time)) + 1
        else:
            retry_after = window_seconds

        logger.warning(
            "Rate limit exceeded",
            organisation_id=organisation_id,
            agent_access_id=agent_access_id,
            tool=tool,
            window=window,
            current=current_count,
            limit=limit,
        )

        return False, current_count, retry_after

    async def get_current_count(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
        agent_access_id: str,
        tool: Optional[str] = None,
        window: str = "minute",
    ) -> int:
        """Get current request count without incrementing.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
            agent_access_id: Agent Access identifier
            tool: Optional tool name
            window: Time window

        Returns:
            Current request count
        """
        redis_client = get_redis()
        key = self._build_key(
            organisation_id, mcp_server_workspace_id, agent_access_id, tool, window
        )
        window_seconds = self._get_window_seconds(window)

        now = time.time()
        window_start = now - window_seconds

        # Remove old and count
        await redis_client.zremrangebyscore(key, 0, window_start)
        return await redis_client.zcard(key)

    async def reset(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
        agent_access_id: str,
        tool: Optional[str] = None,
        window: Optional[str] = None,
    ) -> None:
        """Reset rate limit counters.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
            agent_access_id: Agent Access identifier
            tool: Optional tool name (None = all tools)
            window: Optional window (None = all windows)
        """
        redis_client = get_redis()

        if window:
            key = self._build_key(
                organisation_id, mcp_server_workspace_id, agent_access_id, tool, window
            )
            await redis_client.delete(key)
        else:
            # Delete all windows
            for w in ["second", "minute", "hour", "day"]:
                key = self._build_key(
                    organisation_id, mcp_server_workspace_id, agent_access_id, tool, w
                )
                await redis_client.delete(key)


# Singleton instance
rate_limit_store = RateLimitStore()
