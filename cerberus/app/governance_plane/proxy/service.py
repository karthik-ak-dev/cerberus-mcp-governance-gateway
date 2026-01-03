"""
Proxy Service

Orchestrates the complete proxy flow with inline governance:
1. Validate access key (already done via dependency)
2. Evaluate request against policies
3. Forward to upstream MCP server
4. Evaluate response against policies
5. Return final response

This eliminates the need for a separate HTTP gateway service.
"""

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import DecisionAction, Direction, Transport
from app.core.logging import logger
from app.core.utils import generate_short_id
from app.governance_plane.engine.decision_engine import DecisionEngine
from app.governance_plane.proxy.client import MCPClient, get_mcp_client
from app.schemas.decision import (
    DecisionMetadata,
    DecisionRequest,
    DecisionResponse,
    MCPMessage,
)
from app.schemas.proxy import (
    MCPErrorCodes,
    ProxyContext,
    ProxyDecisionInfo,
    ProxyResponse,
)
from app.schemas.agent_access import AgentAccessContext


class ProxyService:
    """
    Service for proxying MCP requests with inline governance.

    This service replaces the external HTTP gateway by:
    - Running governance checks inline (no network hop to Cerberus)
    - Forwarding directly to MCP servers
    - Evaluating responses inline
    - Returning final response to client

    Benefits:
    - Reduced latency (no gateway → Cerberus round trips)
    - Simplified deployment (single service)
    - Unified logging and monitoring
    """

    def __init__(
        self,
        db: AsyncSession,
        mcp_client: MCPClient | None = None,
    ):
        """Initialize the proxy service.

        Args:
            db: Database session for policy lookups
            mcp_client: MCP client for upstream communication (uses global if not provided)
        """
        self.db = db
        self.mcp_client = mcp_client or get_mcp_client()
        self.decision_engine = DecisionEngine(db)

    async def proxy_request(
        self,
        context: ProxyContext,
    ) -> tuple[ProxyResponse, ProxyDecisionInfo]:
        """
        Proxy an MCP request with inline governance.

        This is the main entry point that handles the complete flow:
        1. Evaluate request against policies (inline)
        2. Forward to upstream if allowed
        3. Evaluate response against policies (inline)
        4. Return final response

        Args:
            context: Proxy context with all request information

        Returns:
            Tuple of (ProxyResponse, ProxyDecisionInfo)
        """
        start_time = time.time()
        governance_time_ms = 0

        logger.info(
            "Starting proxy request flow",
            request_id=context.request_id,
            organisation_id=context.organisation_id,
            mcp_server_workspace_id=context.mcp_server_workspace_id,
            agent_access_id=context.agent_access_id,
            agent_name=context.agent_name,
            mcp_method=context.mcp_method,
            http_method=context.http_method,
            request_path=context.request_path,
            upstream_url=context.mcp_server_url,
        )

        # Step 1: Evaluate request against policies
        request_decision_id = generate_short_id("dec")
        request_decision_start = time.time()

        logger.info(
            "Step 1: Evaluating request against governance policies",
            request_id=context.request_id,
            decision_id=request_decision_id,
            direction="request",
        )

        request_decision = await self._evaluate_request(
            context=context,
            decision_id=request_decision_id,
        )

        request_decision_time = int((time.time() - request_decision_start) * 1000)
        governance_time_ms += request_decision_time

        logger.info(
            "Request governance decision complete",
            request_id=context.request_id,
            decision_id=request_decision_id,
            action=request_decision.action.value,
            allowed=request_decision.allow,
            processing_time_ms=request_decision_time,
            guardrails_triggered=[
                e.guardrail_type for e in request_decision.guardrail_events if e.triggered
            ],
            reasons=request_decision.reasons,
        )

        # Initialize decision info
        decision_info = ProxyDecisionInfo(
            request_decision_id=request_decision_id,
            request_action=request_decision.action,
            request_allowed=request_decision.allow,
            total_governance_time_ms=governance_time_ms,
        )

        # Check if request is blocked
        if not request_decision.allow:
            logger.warning(
                "Request BLOCKED by governance",
                request_id=context.request_id,
                decision_id=request_decision_id,
                action=request_decision.action.value,
                reasons=request_decision.reasons,
                guardrails_triggered=[
                    e.guardrail_type for e in request_decision.guardrail_events if e.triggered
                ],
                agent_name=context.agent_name,
                mcp_method=context.mcp_method,
            )
            return self._create_blocked_response(
                context=context,
                decision=request_decision,
            ), decision_info

        # Determine message to forward (may be modified)
        message_to_forward = self._get_message_to_forward(
            context=context,
            decision=request_decision,
        )

        # Step 2: Forward to upstream MCP server
        logger.info(
            "Step 2: Forwarding request to upstream MCP server",
            request_id=context.request_id,
            upstream_url=context.mcp_server_url,
            request_path=context.request_path,
            message_modified=request_decision.action.value == "modify",
        )

        proxy_result = await self.mcp_client.forward(
            context=context,
            message=message_to_forward,
        )

        if not proxy_result.success:
            logger.error(
                "Upstream request FAILED",
                request_id=context.request_id,
                error=proxy_result.error_message,
                upstream_url=proxy_result.upstream_url,
                status_code=proxy_result.status_code,
                response_time_ms=round(proxy_result.response_time_ms, 2),
            )
            return ProxyResponse.from_error(
                request_id=context.mcp_id,
                code=MCPErrorCodes.UPSTREAM_ERROR,
                message=f"Upstream error: {proxy_result.error_message}",
            ), decision_info

        logger.info(
            "Upstream request successful",
            request_id=context.request_id,
            upstream_url=proxy_result.upstream_url,
            status_code=proxy_result.status_code,
            response_time_ms=round(proxy_result.response_time_ms, 2),
        )

        # Step 3: Evaluate response against policies
        response_decision_id = generate_short_id("dec")
        response_decision_start = time.time()

        logger.info(
            "Step 3: Evaluating response against governance policies",
            request_id=context.request_id,
            decision_id=response_decision_id,
            direction="response",
            original_request_decision_id=request_decision_id,
        )

        response_decision = await self._evaluate_response(
            context=context,
            response_body=proxy_result.response_body,
            decision_id=response_decision_id,
            original_request_decision_id=request_decision_id,
        )

        response_decision_time = int((time.time() - response_decision_start) * 1000)
        governance_time_ms += response_decision_time

        # Update decision info with response evaluation
        decision_info.response_decision_id = response_decision_id
        decision_info.response_action = response_decision.action
        decision_info.response_allowed = response_decision.allow
        decision_info.total_governance_time_ms = governance_time_ms

        logger.info(
            "Response governance decision complete",
            request_id=context.request_id,
            decision_id=response_decision_id,
            action=response_decision.action.value,
            allowed=response_decision.allow,
            processing_time_ms=response_decision_time,
            guardrails_triggered=[
                e.guardrail_type for e in response_decision.guardrail_events if e.triggered
            ],
            reasons=response_decision.reasons,
        )

        # Check if response is blocked
        if not response_decision.allow:
            logger.warning(
                "Response BLOCKED by governance",
                request_id=context.request_id,
                decision_id=response_decision_id,
                action=response_decision.action.value,
                reasons=response_decision.reasons,
                guardrails_triggered=[
                    e.guardrail_type for e in response_decision.guardrail_events if e.triggered
                ],
                agent_name=context.agent_name,
                mcp_method=context.mcp_method,
            )
            return self._create_blocked_response(
                context=context,
                decision=response_decision,
                is_response=True,
            ), decision_info

        # Step 4: Return final response (potentially modified)
        final_response = self._get_final_response(
            context=context,
            original_response=proxy_result.response_body,
            decision=response_decision,
        )

        total_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "Proxy request flow completed successfully",
            request_id=context.request_id,
            total_time_ms=total_time_ms,
            governance_time_ms=governance_time_ms,
            request_governance_time_ms=request_decision_time,
            response_governance_time_ms=response_decision_time,
            upstream_time_ms=round(proxy_result.response_time_ms, 2),
            upstream_url=proxy_result.upstream_url,
            request_decision_id=request_decision_id,
            response_decision_id=response_decision_id,
            request_allowed=request_decision.allow,
            response_allowed=response_decision.allow,
            response_modified=response_decision.action.value == "modify",
        )

        return final_response, decision_info

    async def _evaluate_request(
        self,
        context: ProxyContext,
        decision_id: str,
    ) -> DecisionResponse:
        """Evaluate the request against governance policies.

        Args:
            context: Proxy context
            decision_id: Unique decision ID

        Returns:
            Decision response
        """
        # Build the MCP message for evaluation
        # For requests without body (GET, HEAD, OPTIONS), create a minimal message
        if context.mcp_message:
            mcp_message = MCPMessage(**context.mcp_message)
        else:
            # Create a minimal message for non-body requests
            mcp_message = MCPMessage(
                jsonrpc="2.0",
                method=f"{context.http_method}:{context.request_path}",
            )

        # Build the decision request
        decision_request = DecisionRequest(
            organisation_id=context.organisation_id,
            mcp_server_workspace_id=context.mcp_server_workspace_id,
            agent_access_id=context.agent_access_id,
            direction=Direction.REQUEST,
            transport=Transport.HTTP,
            message=mcp_message,
            metadata=DecisionMetadata(
                timestamp=context.received_at,
                gateway_id="cerberus-proxy",
                gateway_version="1.0.0",
                client_agent=context.client_agent,
                request_id=context.request_id,
            ),
        )

        # Run the decision engine
        return await self.decision_engine.evaluate(
            decision_id=decision_id,
            request=decision_request,
        )

    async def _evaluate_response(
        self,
        context: ProxyContext,
        response_body: dict[str, Any],
        decision_id: str,
        original_request_decision_id: str,
    ) -> DecisionResponse:
        """Evaluate the response against governance policies.

        Args:
            context: Proxy context
            response_body: Response from upstream
            decision_id: Unique decision ID
            original_request_decision_id: Decision ID of the original request

        Returns:
            Decision response
        """
        # Build the decision request for response evaluation
        decision_request = DecisionRequest(
            organisation_id=context.organisation_id,
            mcp_server_workspace_id=context.mcp_server_workspace_id,
            agent_access_id=context.agent_access_id,
            direction=Direction.RESPONSE,
            transport=Transport.HTTP,
            message=MCPMessage(**response_body),
            metadata=DecisionMetadata(
                timestamp=datetime.now(UTC),
                gateway_id="cerberus-proxy",
                gateway_version="1.0.0",
                client_agent=context.client_agent,
                request_id=context.request_id,
                original_request_decision_id=original_request_decision_id,
            ),
        )

        # Run the decision engine
        return await self.decision_engine.evaluate(
            decision_id=decision_id,
            request=decision_request,
        )

    def _get_message_to_forward(
        self,
        context: ProxyContext,
        decision: DecisionResponse,
    ) -> dict[str, Any] | None:
        """Get the message to forward to upstream.

        If the decision includes a modified message, use that.
        Otherwise use the original message.
        For GET/HEAD/OPTIONS/DELETE requests, this may return None.

        Args:
            context: Proxy context
            decision: Request decision

        Returns:
            Message to forward (or None for requests without body)
        """
        if decision.action == DecisionAction.MODIFY and decision.modified_message:
            logger.info(
                "Using modified message for upstream",
                request_id=context.request_id,
            )
            return decision.modified_message.model_dump(exclude_none=True)
        return context.mcp_message

    def _get_final_response(
        self,
        context: ProxyContext,
        original_response: dict[str, Any],
        decision: DecisionResponse,
    ) -> ProxyResponse:
        """Get the final response to return to client.

        If the decision includes a modified message, use that.
        Otherwise use the original response.

        Args:
            context: Proxy context
            original_response: Response from upstream
            decision: Response decision

        Returns:
            Final response
        """
        if decision.action == DecisionAction.MODIFY and decision.modified_message:
            logger.info(
                "Using modified response",
                request_id=context.request_id,
            )
            return ProxyResponse.from_upstream(
                decision.modified_message.model_dump(exclude_none=True)
            )
        return ProxyResponse.from_upstream(original_response)

    def _create_blocked_response(
        self,
        context: ProxyContext,
        decision: DecisionResponse,
        is_response: bool = False,
    ) -> ProxyResponse:
        """Create a blocked response.

        Args:
            context: Proxy context
            decision: The blocking decision
            is_response: Whether this is blocking a response (vs request)

        Returns:
            Error response
        """
        # Format the block reasons
        reasons_str = "; ".join(decision.reasons) if decision.reasons else "Policy violation"

        message = (
            f"Response blocked by governance policy: {reasons_str}"
            if is_response
            else f"Request blocked by governance policy: {reasons_str}"
        )

        return ProxyResponse.from_error(
            request_id=context.mcp_id,
            code=MCPErrorCodes.GOVERNANCE_BLOCKED,
            message=message,
            data={
                "decision_id": decision.decision_id,
                "action": decision.action.value,
                "guardrails_triggered": [
                    event.guardrail_type
                    for event in decision.guardrail_events
                    if event.triggered
                ],
            },
        )


def create_proxy_context(
    key_context: AgentAccessContext,
    mcp_message: dict[str, Any] | None = None,
    request_path: str = "/",
    http_method: str = "POST",
    client_ip: str | None = None,
    client_agent: str | None = None,
    request_id: str | None = None,
    client_headers: dict[str, str] | None = None,
    query_params: str | None = None,
) -> ProxyContext:
    """Create a proxy context from agent access key context and request data.

    This is a helper function to build the ProxyContext from the
    validated agent access key and incoming request.

    Args:
        key_context: Validated agent access key context
        mcp_message: The MCP message to proxy (None for GET/HEAD/OPTIONS)
        request_path: Request path to forward
        http_method: HTTP method
        client_ip: Client IP address
        client_agent: Client user agent
        request_id: Optional request ID (generated if not provided)
        client_headers: Original client headers (for forwarding)
        query_params: Query string (without leading ?)

    Returns:
        ProxyContext ready for proxying
    """
    return ProxyContext(
        request_id=request_id or generate_short_id("req"),
        organisation_id=key_context.organisation_id,
        mcp_server_workspace_id=key_context.mcp_server_workspace_id,
        agent_access_id=key_context.agent_access_id,
        agent_name=key_context.agent_name,
        mcp_server_url=key_context.mcp_server_url or "",
        request_path=request_path,
        http_method=http_method,
        client_ip=client_ip,
        client_agent=client_agent,
        received_at=datetime.now(UTC),
        mcp_message=mcp_message,
        client_headers=client_headers or {},
        query_params=query_params,
    )
