"""
RBAC Guardrail

Simple agent-level tool access control.
Uses flat allowed_tools/denied_tools lists for straightforward configuration.
"""

import fnmatch
from typing import Any, ClassVar

from app.config.constants import Direction, Severity
from app.core.logging import logger
from app.governance_plane.guardrails.base import BaseGuardrail, GuardrailResult
from app.schemas.decision import DecisionRequest, MCPMessage


class RBACGuardrail(BaseGuardrail):
    """RBAC guardrail for tool access control.

    Uses a simple flat configuration:
    - allowed_tools: List of tool patterns that are allowed
    - denied_tools: List of tool patterns that are denied
    - default_action: "allow" or "deny" when tool doesn't match any pattern

    Evaluation order:
    1. Check denied_tools first - if matches, block
    2. Check allowed_tools - if matches, allow
    3. If no match, use default_action
    """

    name: ClassVar[str] = "rbac"
    display_name: ClassVar[str] = "Agent Tool Access Control"
    description: ClassVar[str] = "Control which tools agents can access"
    supported_directions: ClassVar[list[Direction]] = [Direction.REQUEST]

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize RBAC guardrail.

        Args:
            config: Guardrail configuration with:
                - allowed_tools: List of allowed tool patterns (supports wildcards)
                - denied_tools: List of denied tool patterns (supports wildcards)
                - default_action: "allow" or "deny" (default: "deny")
        """
        super().__init__(config)

    async def evaluate(
        self,
        message: MCPMessage,
        request: DecisionRequest,
    ) -> GuardrailResult:
        """Evaluate RBAC rules for the message.

        Args:
            message: MCP message
            request: Decision request containing context

        Returns:
            Guardrail result
        """
        # Only check tool calls
        if message.method != "tools/call":
            logger.debug(
                "RBAC: Skipping non-tool-call method",
                method=message.method,
            )
            return self._allow()

        # Get tool name
        tool_name = message.params.get("name") if message.params else None
        if not tool_name:
            logger.debug("RBAC: No tool name in params, allowing")
            return self._allow()

        logger.debug(
            "RBAC: Evaluating tool access",
            tool_name=tool_name,
            agent_access_id=request.agent_access_id,
        )

        # Get config
        allowed_tools = self.config.get("allowed_tools", [])
        denied_tools = self.config.get("denied_tools", [])
        default_action = self.config.get("default_action", "deny")

        logger.debug(
            "RBAC: Configuration loaded",
            allowed_tools_count=len(allowed_tools),
            denied_tools_count=len(denied_tools),
            default_action=default_action,
        )

        # Step 1: Check denied_tools first (deny takes precedence)
        for pattern in denied_tools:
            if self._matches_pattern(tool_name, pattern):
                logger.info(
                    "RBAC: BLOCKED - Tool in denied list",
                    tool_name=tool_name,
                    matched_pattern=pattern,
                )
                return self._block(
                    reason=f"Tool '{tool_name}' is explicitly denied",
                    details={
                        "tool": tool_name,
                        "matched_pattern": pattern,
                        "match_type": "denied_tools",
                    },
                    severity=Severity.WARNING,
                )

        # Step 2: Check allowed_tools
        for pattern in allowed_tools:
            if self._matches_pattern(tool_name, pattern):
                logger.debug(
                    "RBAC: ALLOWED - Tool in allowed list",
                    tool_name=tool_name,
                    matched_pattern=pattern,
                )
                return self._allow(
                    details={
                        "tool": tool_name,
                        "matched_pattern": pattern,
                        "match_type": "allowed_tools",
                    }
                )

        # Step 3: No match - use default_action
        if allowed_tools:
            # If allowed_tools is defined but tool didn't match, block
            logger.info(
                "RBAC: BLOCKED - Tool not in allowed list",
                tool_name=tool_name,
                allowed_patterns=allowed_tools,
            )
            return self._block(
                reason=f"Tool '{tool_name}' is not in the allowed list",
                details={
                    "tool": tool_name,
                    "allowed_tools": allowed_tools,
                    "match_type": "not_in_allowed_list",
                },
                severity=Severity.WARNING,
            )

        # No allowed_tools defined, use default_action
        if default_action == "deny":
            logger.info(
                "RBAC: BLOCKED - Default action is deny",
                tool_name=tool_name,
            )
            return self._block(
                reason=f"Tool '{tool_name}' blocked by default deny policy",
                details={
                    "tool": tool_name,
                    "match_type": "default_deny",
                },
                severity=Severity.WARNING,
            )

        logger.debug(
            "RBAC: ALLOWED - Default action is allow",
            tool_name=tool_name,
        )
        return self._allow(details={"tool": tool_name, "match_type": "default_allow"})

    def _matches_pattern(self, tool_name: str, pattern: str) -> bool:
        """Check if tool name matches a pattern.

        Supports wildcards: "filesystem/*" matches "filesystem/read"

        Args:
            tool_name: Tool name to check
            pattern: Pattern to match against (supports * and ? wildcards)

        Returns:
            True if matches
        """
        return fnmatch.fnmatch(tool_name, pattern)
