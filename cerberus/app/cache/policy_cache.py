"""
Policy Cache

Caching layer for policy lookups to reduce database queries.
"""

import json
from typing import Any, Optional

from app.cache.redis_client import RedisCache, get_redis
from app.core.logging import logger


# Cache TTL in seconds
POLICY_CACHE_TTL = 300  # 5 minutes


class PolicyCache(RedisCache):
    """Cache for policy data."""

    def __init__(self) -> None:
        super().__init__(prefix="policy:")

    async def get_effective_policy(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
        agent_access_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get cached effective policy.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
            agent_access_id: Optional agent access identifier

        Returns:
            Cached policy dict or None
        """
        cache_key = self._build_key(
            organisation_id, mcp_server_workspace_id, agent_access_id
        )
        cached = await self.get(cache_key)

        if cached:
            logger.debug("Policy cache hit", key=cache_key)
            return json.loads(cached)

        logger.debug("Policy cache miss", key=cache_key)
        return None

    async def set_effective_policy(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
        agent_access_id: Optional[str],
        policy: dict[str, Any],
    ) -> None:
        """Cache effective policy.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
            agent_access_id: Optional agent access identifier
            policy: Policy data to cache
        """
        cache_key = self._build_key(
            organisation_id, mcp_server_workspace_id, agent_access_id
        )
        await self.set(cache_key, json.dumps(policy), ttl=POLICY_CACHE_TTL)
        logger.debug("Policy cached", key=cache_key)

    async def invalidate_organisation(self, organisation_id: str) -> None:
        """Invalidate all cached policies for an organisation.

        Args:
            organisation_id: Organisation identifier
        """
        # Pattern-based deletion
        pattern = f"{self.prefix}effective:{organisation_id}:*"
        await self._delete_pattern(pattern)
        logger.info(
            "Invalidated organisation policy cache", organisation_id=organisation_id
        )

    async def invalidate_workspace(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
    ) -> None:
        """Invalidate all cached policies for a workspace.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
        """
        pattern = (
            f"{self.prefix}effective:{organisation_id}:{mcp_server_workspace_id}:*"
        )
        await self._delete_pattern(pattern)
        logger.info(
            "Invalidated workspace policy cache",
            organisation_id=organisation_id,
            mcp_server_workspace_id=mcp_server_workspace_id,
        )

    async def invalidate_agent_access(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
        agent_access_id: str,
    ) -> None:
        """Invalidate cached policy for a specific agent access.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
            agent_access_id: Agent access identifier
        """
        cache_key = self._build_key(
            organisation_id, mcp_server_workspace_id, agent_access_id
        )
        await self.delete(cache_key)
        logger.info(
            "Invalidated agent access policy cache",
            organisation_id=organisation_id,
            mcp_server_workspace_id=mcp_server_workspace_id,
            agent_access_id=agent_access_id,
        )

    # Keep old method name for backwards compatibility during migration
    async def invalidate_tenant(self, organisation_id: str) -> None:
        """Alias for invalidate_organisation."""
        await self.invalidate_organisation(organisation_id)

    def _build_key(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
        agent_access_id: Optional[str],
    ) -> str:
        """Build cache key for effective policy.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
            agent_access_id: Optional agent access identifier

        Returns:
            Cache key string
        """
        agent_part = agent_access_id or "_default"
        return f"effective:{organisation_id}:{mcp_server_workspace_id}:{agent_part}"

    async def _delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern
        """
        redis_client = get_redis()
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            if keys:
                await redis_client.delete(*keys)
            if cursor == 0:
                break


# Singleton instance
policy_cache = PolicyCache()
