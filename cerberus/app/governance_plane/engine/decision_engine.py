"""
Decision Engine

Core engine for evaluating governance decisions.
Uses the simplified policy model where each policy links ONE guardrail to ONE entity.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import DecisionAction, Direction, Severity
from app.control_plane.services.policy_service import PolicyService
from app.core.exceptions import GuardrailExecutionError
from app.core.logging import logger
from app.governance_plane.engine.pipeline import GuardrailPipeline
from app.governance_plane.events.emitter import EventEmitter
from app.schemas.decision import DecisionRequest, DecisionResponse, GuardrailEvent
from app.schemas.policy import EffectivePolicyResponse


class DecisionEngine:
    """Engine for evaluating MCP messages against policies.

    Uses the simplified policy model:
    - Each policy links ONE guardrail to ONE entity
    - Policies are independent and evaluated separately
    - No complex merging - just collect all applicable policies
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize decision engine.

        Args:
            session: Database session
        """
        self.session = session
        self.policy_service = PolicyService(session)
        self.event_emitter = EventEmitter(session)

    async def evaluate(
        self,
        decision_id: str,
        request: DecisionRequest,
    ) -> DecisionResponse:
        """Evaluate a decision request.

        Args:
            decision_id: Unique decision identifier
            request: Decision request payload

        Returns:
            Decision response
        """
        logger.info(
            "Starting decision evaluation",
            decision_id=decision_id,
            direction=request.direction.value,
            organisation_id=request.organisation_id,
            mcp_server_workspace_id=request.mcp_server_workspace_id,
            agent_access_id=request.agent_access_id,
            mcp_method=request.message.method,
        )

        try:
            # 1. Load effective policies
            effective_policy = await self._load_policies(decision_id, request)

            # 2. Build and execute guardrail pipeline
            result = await self._execute_pipeline(
                decision_id=decision_id,
                request=request,
                effective_policy=effective_policy,
            )

            logger.info(
                "Decision evaluation complete",
                decision_id=decision_id,
                action=result.action.value,
                allowed=result.allow,
                guardrail_events_count=len(result.guardrail_events),
                triggered_guardrails=[
                    e.guardrail_type for e in result.guardrail_events if e.triggered
                ],
            )

            # 3. Log the decision event (non-blocking)
            await self._log_decision(decision_id, request, result)

            return result

        except GuardrailExecutionError as e:
            # Guardrail-specific error - already logged
            logger.error(
                "Guardrail execution error during decision evaluation",
                decision_id=decision_id,
                guardrail_type=e.guardrail_type,
                error=str(e),
            )
            return self._create_error_response(
                decision_id=decision_id,
                direction=request.direction,
                error=e,
                error_type="guardrail_error",
            )

        except SQLAlchemyError as e:
            logger.exception(
                "Database error during decision evaluation",
                decision_id=decision_id,
                organisation_id=request.organisation_id,
            )
            return self._create_error_response(
                decision_id=decision_id,
                direction=request.direction,
                error=e,
                error_type="database_error",
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            # Catch-all to ensure we always return a response, never crash
            logger.exception(
                "Unexpected error during decision evaluation",
                decision_id=decision_id,
                error_type=type(e).__name__,
            )
            return self._create_error_response(
                decision_id=decision_id,
                direction=request.direction,
                error=e,
                error_type="internal_error",
            )

    async def _load_policies(
        self,
        decision_id: str,
        request: DecisionRequest,
    ) -> EffectivePolicyResponse:
        """Load effective policies for the request.

        Args:
            decision_id: Decision ID for logging
            request: Decision request

        Returns:
            Effective policies response
        """
        logger.info(
            "Loading effective policies",
            decision_id=decision_id,
            organisation_id=request.organisation_id,
            mcp_server_workspace_id=request.mcp_server_workspace_id,
            agent_access_id=request.agent_access_id,
        )

        effective_policy = await self.policy_service.get_effective_policies(
            organisation_id=UUID(request.organisation_id),
            mcp_server_workspace_id=UUID(request.mcp_server_workspace_id),
            agent_access_id=UUID(request.agent_access_id),
        )

        enabled_policies = [p for p in effective_policy.policies if p.is_enabled]
        guardrail_types = list({p.guardrail_type for p in enabled_policies})

        logger.info(
            "Loaded effective policies",
            decision_id=decision_id,
            total_policies=len(effective_policy.policies),
            enabled_policies=len(enabled_policies),
            guardrail_types=guardrail_types,
            organisation_id=request.organisation_id,
        )

        return effective_policy

    async def _execute_pipeline(
        self,
        decision_id: str,
        request: DecisionRequest,
        effective_policy: EffectivePolicyResponse,
    ) -> DecisionResponse:
        """Build and execute the guardrail pipeline.

        Args:
            decision_id: Decision ID
            request: Decision request
            effective_policy: Loaded policies

        Returns:
            Decision response
        """
        guardrails_config = self._build_guardrails_config(effective_policy)

        enabled_guardrails = [k for k, v in guardrails_config.items() if v.get("enabled")]
        logger.info(
            "Built guardrails config from policies",
            decision_id=decision_id,
            enabled_guardrails=enabled_guardrails,
            config_keys=list(guardrails_config.keys()),
        )

        pipeline = GuardrailPipeline(guardrails_config=guardrails_config)

        logger.info(
            "Executing guardrail pipeline",
            decision_id=decision_id,
            direction=request.direction.value,
            mcp_method=request.message.method,
        )

        return await pipeline.execute(
            decision_id=decision_id,
            request=request,
        )

    async def _log_decision(
        self,
        decision_id: str,
        request: DecisionRequest,
        result: DecisionResponse,
    ) -> None:
        """Log the decision event.

        Non-blocking - errors are logged but don't fail the request.

        Args:
            decision_id: Decision ID
            request: Original request
            result: Decision result
        """
        try:
            await self.event_emitter.emit_decision(
                decision_id=decision_id,
                request=request,
                result=result,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            # Log but don't fail the request - event logging is non-critical
            logger.exception(
                "Failed to emit decision event",
                decision_id=decision_id,
            )

    def _build_guardrails_config(
        self, effective_policy: EffectivePolicyResponse
    ) -> dict[str, Any]:
        """Build guardrail configuration from effective policies.

        Each policy in the response contains ONE guardrail.
        We build a config dict keyed by guardrail_type.

        Args:
            effective_policy: Effective policies response

        Returns:
            Dictionary of guardrail_type -> config
        """
        config: dict[str, Any] = {}

        for policy in effective_policy.policies:
            if not policy.is_enabled:
                continue

            guardrail_type = policy.guardrail_type

            guardrail_config = {
                "enabled": True,
                "action": policy.action.value,
                "policy_id": policy.id,
                "policy_name": policy.name,
                "level": policy.level.value,
                **policy.config,
            }

            # More specific level wins (agent > workspace > org)
            if guardrail_type in config:
                if self._should_override(
                    existing_level=config[guardrail_type].get("level", "organisation"),
                    new_level=policy.level.value,
                ):
                    config[guardrail_type] = guardrail_config
            else:
                config[guardrail_type] = guardrail_config

        return config

    def _should_override(self, existing_level: str, new_level: str) -> bool:
        """Check if new policy level should override existing.

        Args:
            existing_level: Current policy level
            new_level: New policy level

        Returns:
            True if new level takes precedence
        """
        level_priority = {"organisation": 0, "workspace": 1, "agent": 2}
        return level_priority.get(new_level, 0) > level_priority.get(existing_level, 0)

    def _create_error_response(
        self,
        decision_id: str,
        direction: Direction,
        error: Exception,
        error_type: str,
    ) -> DecisionResponse:
        """Create a safe error response.

        Args:
            decision_id: Decision ID
            direction: Request direction
            error: The exception that occurred
            error_type: Type classification for the error

        Returns:
            Error decision response (blocks the request)
        """
        return DecisionResponse(
            allow=False,
            action=(
                DecisionAction.BLOCK_REQUEST
                if direction == Direction.REQUEST
                else DecisionAction.BLOCK_RESPONSE
            ),
            reasons=[f"Internal error: {error_type}"],
            guardrail_events=[
                GuardrailEvent(
                    guardrail_type="system",
                    triggered=True,
                    action_taken="block",
                    details={
                        "error": str(error),
                        "error_type": error_type,
                    },
                    severity=Severity.CRITICAL,
                )
            ],
            decision_id=decision_id,
            processing_time_ms=0,
        )
