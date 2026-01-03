"""
Policy Loader

Loads and caches effective policies for decision making.
Updated for the simplified policy model.
"""

from typing import Any

from app.cache.policy_cache import policy_cache
from app.core.logging import logger


class PolicyLoader:
    """Loads and retrieves effective policies.

    With the simplified policy model:
    - No complex merging needed
    - Policies are retrieved and cached per (org, workspace, agent)
    - Each policy is independent with ONE guardrail
    """

    async def get_effective_config(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str,
        agent_access_id: str | None = None,
    ) -> dict[str, Any]:
        """Get effective guardrail configuration.

        This retrieves cached policies for the given context.
        No merging is performed - policies are returned as-is.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: MCP Server Workspace identifier
            agent_access_id: Optional agent access identifier

        Returns:
            Cached policy data or empty dict
        """
        # Check cache first
        cached = await policy_cache.get_effective_policy(
            organisation_id, mcp_server_workspace_id, agent_access_id
        )

        if cached:
            logger.debug("Policy cache hit", organisation_id=organisation_id)
            return cached

        logger.debug("Policy cache miss", organisation_id=organisation_id)

        # Cache miss - this shouldn't happen in normal flow
        # The PolicyService should have cached it
        return {}

    async def invalidate_cache(
        self,
        organisation_id: str,
        mcp_server_workspace_id: str | None = None,
        agent_access_id: str | None = None,
    ) -> None:
        """Invalidate cached policy.

        Args:
            organisation_id: Organisation identifier
            mcp_server_workspace_id: Optional workspace identifier
            agent_access_id: Optional agent access identifier
        """
        if agent_access_id and mcp_server_workspace_id:
            # Agent-level cache invalidation would go here if implemented
            await policy_cache.invalidate_workspace(
                organisation_id, mcp_server_workspace_id
            )
        elif mcp_server_workspace_id:
            await policy_cache.invalidate_workspace(
                organisation_id, mcp_server_workspace_id
            )
        else:
            await policy_cache.invalidate_tenant(organisation_id)
