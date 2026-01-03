"""
Base Guardrail

Abstract base class for all guardrail implementations.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from app.config.constants import DecisionAction, Direction, Severity
from app.schemas.decision import DecisionRequest, GuardrailEvent, MCPMessage


@dataclass
class GuardrailResult:
    """Result from guardrail evaluation."""

    action: DecisionAction
    event: GuardrailEvent
    reasons: list[str]
    modified_message: MCPMessage | None = None


class BaseGuardrail(ABC):
    """Abstract base class for guardrails."""

    # Class attributes to be overridden by subclasses
    name: ClassVar[str] = "base"
    display_name: ClassVar[str] = "Base Guardrail"
    description: ClassVar[str] = "Base guardrail class"
    supported_directions: ClassVar[list[Direction]] = [
        Direction.REQUEST,
        Direction.RESPONSE,
    ]

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize guardrail with configuration.

        Args:
            config: Guardrail-specific configuration
        """
        self.config = config
        self.enabled = config.get("enabled", True)

    @classmethod
    def supports_direction(cls, direction: Direction) -> bool:
        """Check if guardrail supports the given direction.

        Args:
            direction: Message direction

        Returns:
            True if supported
        """
        return direction in cls.supported_directions

    @abstractmethod
    async def evaluate(
        self,
        message: MCPMessage,
        request: DecisionRequest,
    ) -> GuardrailResult:
        """Evaluate a message against this guardrail.

        Args:
            message: MCP message to evaluate (may be modified by prior guardrails)
            request: Full decision request containing context

        Returns:
            Guardrail evaluation result
        """

    def _create_event(
        self,
        triggered: bool,
        action_taken: str,
        details: dict[str, Any] | None = None,
        severity: Severity = Severity.INFO,
    ) -> GuardrailEvent:
        """Create a guardrail event.

        Args:
            triggered: Whether the guardrail was triggered
            action_taken: Action taken by the guardrail
            details: Additional details
            severity: Event severity

        Returns:
            GuardrailEvent instance
        """
        return GuardrailEvent(
            guardrail_type=self.name,
            triggered=triggered,
            action_taken=action_taken,
            details=details or {},
            severity=severity,
        )

    def _allow(
        self,
        details: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """Create an allow result.

        Args:
            details: Optional details

        Returns:
            GuardrailResult with ALLOW action
        """
        return GuardrailResult(
            action=DecisionAction.ALLOW,
            event=self._create_event(
                triggered=False,
                action_taken="allow",
                details=details,
            ),
            reasons=[],
        )

    def _block(
        self,
        reason: str,
        details: dict[str, Any] | None = None,
        is_request: bool = True,
        severity: Severity = Severity.WARNING,
    ) -> GuardrailResult:
        """Create a block result.

        Args:
            reason: Human-readable reason
            details: Optional details
            is_request: Whether this is a request (vs response)
            severity: Event severity

        Returns:
            GuardrailResult with BLOCK action
        """
        action = (
            DecisionAction.BLOCK_REQUEST
            if is_request
            else DecisionAction.BLOCK_RESPONSE
        )
        return GuardrailResult(
            action=action,
            event=self._create_event(
                triggered=True,
                action_taken="block",
                details=details,
                severity=severity,
            ),
            reasons=[reason],
        )

    def _modify(
        self,
        modified_message: MCPMessage,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """Create a modify result.

        Args:
            modified_message: Modified message
            reason: Human-readable reason
            details: Optional details

        Returns:
            GuardrailResult with MODIFY action
        """
        return GuardrailResult(
            action=DecisionAction.MODIFY,
            event=self._create_event(
                triggered=True,
                action_taken="modify",
                details=details,
            ),
            reasons=[reason],
            modified_message=modified_message,
        )

    def _log_only(
        self,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """Create a log-only result.

        Args:
            reason: Human-readable reason
            details: Optional details

        Returns:
            GuardrailResult with LOG_ONLY action
        """
        return GuardrailResult(
            action=DecisionAction.LOG_ONLY,
            event=self._create_event(
                triggered=True,
                action_taken="log_only",
                details=details,
            ),
            reasons=[reason],
        )

    def _extract_content(self, message: MCPMessage) -> str:
        """Extract text content from message.

        Args:
            message: MCP message

        Returns:
            Extracted text content
        """
        content_parts = []

        if message.params:
            content_parts.append(json.dumps(message.params))

        if message.result:
            if isinstance(message.result, dict):
                if "content" in message.result:
                    for item in message.result.get("content", []):
                        if isinstance(item, dict) and item.get("type") == "text":
                            content_parts.append(item.get("text", ""))
                else:
                    content_parts.append(json.dumps(message.result))
            else:
                content_parts.append(str(message.result))

        return "\n".join(content_parts)
