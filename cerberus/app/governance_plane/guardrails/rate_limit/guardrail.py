"""
Rate Limit Guardrail

Request throttling based on configurable limits.
Each rate limit type (per_minute, per_hour) has its own guardrail class.
"""

from typing import ClassVar

from app.cache.rate_limit_store import rate_limit_store
from app.config.constants import Direction, Severity
from app.core.logging import logger
from app.governance_plane.guardrails.base import BaseGuardrail, GuardrailResult
from app.schemas.decision import DecisionRequest, MCPMessage

# Default rate limits
DEFAULT_RATE_LIMIT_MINUTE = 100
DEFAULT_RATE_LIMIT_HOUR = 1000


class BaseRateLimitGuardrail(BaseGuardrail):
    """Base class for rate limiting guardrails.

    Each subclass handles a specific time window (minute, hour).
    """

    # Subclasses must override these
    name: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    window: ClassVar[str] = ""  # "minute" or "hour"
    default_limit: ClassVar[int] = 100

    supported_directions: ClassVar[list[Direction]] = [Direction.REQUEST]

    async def evaluate(
        self,
        message: MCPMessage,
        request: DecisionRequest,
    ) -> GuardrailResult:
        """Evaluate rate limits.

        Args:
            message: MCP message
            request: Decision request containing context

        Returns:
            Guardrail result
        """
        organisation_id = request.organisation_id
        mcp_server_workspace_id = request.mcp_server_workspace_id
        agent_access_id = request.agent_access_id

        # Get tool name for tool-specific limits
        tool_name = None
        if message.method == "tools/call" and message.params:
            tool_name = message.params.get("name")

        # Get limit from config or use default for this window type
        limit = self._get_limit(tool_name)

        logger.debug(
            "RateLimit: Checking rate limit",
            guardrail_type=self.name,
            organisation_id=organisation_id,
            agent_access_id=agent_access_id,
            tool_name=tool_name,
            limit=limit,
            window=self.window,
        )

        # Check rate limit
        allowed, current, retry_after = await rate_limit_store.check_and_increment(
            organisation_id=organisation_id,
            mcp_server_workspace_id=mcp_server_workspace_id,
            agent_access_id=agent_access_id,
            limit=limit,
            tool=tool_name,
            window=self.window,
        )

        if not allowed:
            logger.warning(
                "RateLimit: BLOCKED - Rate limit exceeded",
                guardrail_type=self.name,
                organisation_id=organisation_id,
                agent_access_id=agent_access_id,
                tool_name=tool_name,
                current_count=current,
                limit=limit,
                window=self.window,
                retry_after_seconds=retry_after,
            )
            return self._block(
                reason=f"Rate limit exceeded: {limit} requests per {self.window}",
                details={
                    "current_count": current,
                    "limit": limit,
                    "window": self.window,
                    "retry_after_seconds": retry_after,
                    "tool": tool_name,
                },
                severity=Severity.WARNING,
            )

        logger.debug(
            "RateLimit: ALLOWED - Within limits",
            guardrail_type=self.name,
            agent_access_id=agent_access_id,
            tool_name=tool_name,
            current_count=current,
            limit=limit,
            window=self.window,
        )

        return self._allow(
            details={
                "current_count": current,
                "limit": limit,
                "window": self.window,
            }
        )

    def _get_limit(self, tool_name: str | None) -> int:
        """Get applicable rate limit for tool.

        Args:
            tool_name: Optional tool name

        Returns:
            Rate limit value
        """
        # Check tool-specific limits first
        per_tool_limits = self.config.get("per_tool_limits", {})
        if tool_name and tool_name in per_tool_limits:
            tool_config = per_tool_limits[tool_name]
            if isinstance(tool_config, dict) and "limit" in tool_config:
                return tool_config["limit"]
            if isinstance(tool_config, int):
                return tool_config

        # Check for simple "limit" config (most common case)
        if "limit" in self.config:
            return self.config["limit"]

        # Fall back to class default
        return self.default_limit


# =============================================================================
# SPECIFIC RATE LIMIT GUARDRAIL CLASSES
# =============================================================================


class RateLimitPerMinuteGuardrail(BaseRateLimitGuardrail):
    """Rate limit per minute guardrail."""

    name: ClassVar[str] = "rate_limit_per_minute"
    display_name: ClassVar[str] = "Rate Limit - Per Minute"
    description: ClassVar[str] = "Limit requests per minute"
    window: ClassVar[str] = "minute"
    default_limit: ClassVar[int] = DEFAULT_RATE_LIMIT_MINUTE


class RateLimitPerHourGuardrail(BaseRateLimitGuardrail):
    """Rate limit per hour guardrail."""

    name: ClassVar[str] = "rate_limit_per_hour"
    display_name: ClassVar[str] = "Rate Limit - Per Hour"
    description: ClassVar[str] = "Limit requests per hour"
    window: ClassVar[str] = "hour"
    default_limit: ClassVar[int] = DEFAULT_RATE_LIMIT_HOUR


# List of all rate limit guardrail classes for registration
RATE_LIMIT_GUARDRAIL_CLASSES = [
    RateLimitPerMinuteGuardrail,
    RateLimitPerHourGuardrail,
]
