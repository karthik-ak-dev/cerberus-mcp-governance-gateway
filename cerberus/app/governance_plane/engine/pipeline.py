"""
Guardrail Pipeline

Executes guardrails in order and aggregates results.
"""

from typing import Any

from app.config.constants import DecisionAction, Severity
from app.core.exceptions import GuardrailExecutionError
from app.core.logging import logger
from app.governance_plane.guardrails.registry import guardrail_registry
from app.schemas.decision import (
    DecisionRequest,
    DecisionResponse,
    GuardrailEvent,
    MCPMessage,
)


class GuardrailPipeline:
    """Pipeline for executing guardrails in sequence.

    Executes configured guardrails in a defined order, aggregating results.
    Supports short-circuit on block actions and message modification.
    """

    def __init__(self, guardrails_config: dict[str, Any]) -> None:
        """Initialize pipeline.

        Args:
            guardrails_config: Effective guardrail configuration
        """
        self.config = guardrails_config

    async def execute(
        self,
        decision_id: str,
        request: DecisionRequest,
    ) -> DecisionResponse:
        """Execute the guardrail pipeline.

        Args:
            decision_id: Unique decision identifier for tracing
            request: Decision request containing message and context

        Returns:
            Aggregated decision response
        """
        events: list[GuardrailEvent] = []
        reasons: list[str] = []
        modified_message: MCPMessage | None = None
        current_message = request.message

        guardrail_order = self._get_guardrail_order(request)

        logger.info(
            "Starting guardrail pipeline execution",
            decision_id=decision_id,
            direction=request.direction.value,
            guardrail_order=guardrail_order,
            total_guardrails=len(guardrail_order),
        )

        for idx, guardrail_type in enumerate(guardrail_order):
            logger.info(
                "Processing guardrail in pipeline",
                decision_id=decision_id,
                guardrail_type=guardrail_type,
                guardrail_index=idx + 1,
                total_guardrails=len(guardrail_order),
            )

            result = await self._execute_guardrail(
                guardrail_type=guardrail_type,
                decision_id=decision_id,
                message=current_message,
                request=request,
                events=events,
            )

            if result is None:
                # Guardrail was skipped (disabled or not applicable)
                logger.info(
                    "Guardrail skipped (disabled or not applicable for direction)",
                    decision_id=decision_id,
                    guardrail_type=guardrail_type,
                )
                continue

            # Short circuit on block
            if result.action in (
                DecisionAction.BLOCK_REQUEST,
                DecisionAction.BLOCK_RESPONSE,
            ):
                logger.info(
                    "Guardrail pipeline short-circuited on BLOCK",
                    decision_id=decision_id,
                    blocking_guardrail=guardrail_type,
                    action=result.action.value,
                    reasons=result.reasons,
                    guardrails_executed=idx + 1,
                    guardrails_remaining=len(guardrail_order) - idx - 1,
                )
                return DecisionResponse(
                    allow=False,
                    action=result.action,
                    modified_message=None,
                    reasons=result.reasons,
                    guardrail_events=events,
                    decision_id=decision_id,
                    processing_time_ms=0,
                )

            # Handle modification
            if result.action == DecisionAction.MODIFY and result.modified_message:
                logger.info(
                    "Guardrail modified message",
                    decision_id=decision_id,
                    guardrail_type=guardrail_type,
                )
                current_message = result.modified_message
                modified_message = result.modified_message

            # Collect reasons
            reasons.extend(result.reasons)

        # All guardrails passed
        triggered_guardrails = [e.guardrail_type for e in events if e.triggered]
        logger.info(
            "Guardrail pipeline execution complete",
            decision_id=decision_id,
            result="ALLOW" if not modified_message else "MODIFY",
            guardrails_executed=len(guardrail_order),
            guardrails_triggered=triggered_guardrails,
            message_modified=modified_message is not None,
        )

        return DecisionResponse(
            allow=True,
            action=DecisionAction.MODIFY if modified_message else DecisionAction.ALLOW,
            modified_message=modified_message,
            reasons=reasons,
            guardrail_events=events,
            decision_id=decision_id,
            processing_time_ms=0,
        )

    async def _execute_guardrail(
        self,
        guardrail_type: str,
        decision_id: str,
        message: MCPMessage,
        request: DecisionRequest,
        events: list[GuardrailEvent],
    ):
        """Execute a single guardrail.

        Args:
            guardrail_type: Type of guardrail to execute
            decision_id: Decision ID for tracing
            message: Current message (may be modified by previous guardrails)
            request: Original decision request for context
            events: List to append events to

        Returns:
            GuardrailResult or None if skipped
        """
        # Get guardrail configuration
        guardrail_config = self.config.get(guardrail_type, {})
        if not guardrail_config.get("enabled", False):
            logger.info(
                "Guardrail not enabled in config",
                guardrail_type=guardrail_type,
                decision_id=decision_id,
            )
            return None

        # Get guardrail class from registry
        guardrail_class = guardrail_registry.get(guardrail_type)
        if not guardrail_class:
            logger.error(
                "Guardrail not registered in registry",
                guardrail_type=guardrail_type,
                decision_id=decision_id,
            )
            return None

        # Check direction support
        if not guardrail_class.supports_direction(request.direction):
            logger.info(
                "Guardrail does not support current direction",
                guardrail_type=guardrail_type,
                decision_id=decision_id,
                direction=request.direction.value,
                supported_directions=[d.value for d in guardrail_class.supported_directions],
            )
            return None

        logger.info(
            "Executing guardrail evaluation",
            guardrail_type=guardrail_type,
            decision_id=decision_id,
            direction=request.direction.value,
            mcp_method=message.method,
            policy_id=guardrail_config.get("policy_id"),
            policy_name=guardrail_config.get("policy_name"),
        )

        try:
            guardrail = guardrail_class(guardrail_config)
            result = await guardrail.evaluate(message=message, request=request)
            events.append(result.event)

            logger.info(
                "Guardrail evaluation complete",
                guardrail_type=guardrail_type,
                decision_id=decision_id,
                action=result.action.value,
                triggered=result.event.triggered,
                action_taken=result.event.action_taken,
            )

            return result

        except Exception as e:
            # Log with full context for debugging
            logger.exception(
                "Guardrail execution FAILED",
                guardrail_type=guardrail_type,
                decision_id=decision_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )

            # Record error event
            events.append(
                GuardrailEvent(
                    guardrail_type=guardrail_type,
                    triggered=True,
                    action_taken="error",
                    details={
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    severity=Severity.ERROR,
                )
            )

            # Wrap in our exception type for upstream handling
            raise GuardrailExecutionError(
                message=f"Guardrail '{guardrail_type}' failed: {e}",
                guardrail_type=guardrail_type,
                original_error=e,
            ) from e

    def _get_guardrail_order(self, request: DecisionRequest) -> list[str]:
        """Get guardrail execution order based on direction.

        Returns guardrails that support the current direction, ordered by priority.
        Priority is determined by the guardrail's position in the registry.

        Args:
            request: Decision request containing direction

        Returns:
            Ordered list of guardrail type names
        """
        all_guardrails = guardrail_registry.get_all()
        return [
            name
            for name, guardrail_class in all_guardrails.items()
            if guardrail_class.supports_direction(request.direction)
        ]
