"""
Event Emitter

Emits governance events to storage and external systems.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.repositories import AuditLogRepository
from app.schemas.decision import DecisionRequest, DecisionResponse


class EventEmitter:
    """Emits decision and guardrail events."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize event emitter.

        Args:
            session: Database session
        """
        self.session = session
        self.audit_repo = AuditLogRepository(session)

    async def emit_decision(
        self,
        decision_id: str,
        request: DecisionRequest,
        result: DecisionResponse,
    ) -> None:
        """Emit a decision event to audit log.

        Args:
            decision_id: Decision identifier
            request: Original decision request
            result: Decision result
        """
        logger.info(
            "EventEmitter: Emitting decision event",
            decision_id=decision_id,
            direction=request.direction.value,
            action=result.action.value,
            guardrail_events_count=len(result.guardrail_events),
        )

        try:
            # Extract tool name if present
            tool_name = None
            method = request.message.method
            if method == "tools/call" and request.message.params:
                tool_name = request.message.params.get("name")

            logger.info(
                "EventEmitter: Creating audit log entry",
                decision_id=decision_id,
                organisation_id=request.organisation_id,
                mcp_method=method,
                tool_name=tool_name,
            )

            # Create audit log entry
            await self.audit_repo.create_decision_log(
                organisation_id=UUID(request.organisation_id),
                mcp_server_workspace_id=UUID(request.mcp_server_workspace_id),
                request_id=request.metadata.request_id,
                agent_name=request.agent_access_id,  # Using agent_access_id as agent_name for now
                message_type=request.direction.value,
                decision=result.action.value,
                decision_reason=(
                    "; ".join(result.reasons) if result.reasons else "All guardrails passed"
                ),
                latency_ms=result.processing_time_ms,
                tool_name=tool_name or method or "unknown",
                agent_access_id=UUID(request.agent_access_id) if request.agent_access_id else None,
                session_id=request.metadata.session_id,
                guardrail_results={
                    e.guardrail_type: {
                        "triggered": e.triggered,
                        "action_taken": e.action_taken,
                        "details": e.details,
                        "severity": str(e.severity),
                    }
                    for e in result.guardrail_events
                },
            )

            logger.info(
                "EventEmitter: Decision event logged successfully",
                decision_id=decision_id,
                action=result.action.value,
                allowed=result.allow,
            )

        except (SQLAlchemyError, ValueError, AttributeError, KeyError, TypeError) as e:
            # Log error but don't fail the decision
            logger.error(
                "EventEmitter: Failed to log decision event",
                decision_id=decision_id,
                error_type=type(e).__name__,
                error=str(e),
            )

    async def emit_guardrail_event(
        self,
        decision_id: str,
        guardrail_type: str,
        triggered: bool,
        action_taken: str,
        details: dict[str, Any],
    ) -> None:
        """Emit a standalone guardrail event.

        Args:
            decision_id: Decision identifier
            guardrail_type: Type of guardrail
            triggered: Whether guardrail was triggered
            action_taken: Action taken
            details: Event details
        """
        logger.info(
            "Guardrail event",
            decision_id=decision_id,
            guardrail=guardrail_type,
            triggered=triggered,
            action=action_taken,
            details=details,
        )
