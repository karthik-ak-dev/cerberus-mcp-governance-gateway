"""
Decision Schemas

Request/response models for decision API endpoints.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.config.constants import DecisionAction, Direction, Severity, Transport


class MCPMessage(BaseModel):
    """MCP JSON-RPC message structure."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Optional[int | str] = Field(None, description="Request ID")
    method: Optional[str] = Field(None, description="Method name for requests")
    params: Optional[dict[str, Any]] = Field(None, description="Method parameters")
    result: Optional[Any] = Field(None, description="Success result for responses")
    error: Optional[dict[str, Any]] = Field(None, description="Error for responses")


class DecisionMetadata(BaseModel):
    """Metadata about the decision request context."""

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Request timestamp",
    )
    gateway_id: Optional[str] = Field(None, description="Gateway identifier")
    gateway_version: Optional[str] = Field(None, description="Gateway version")
    client_agent: Optional[str] = Field(None, description="MCP client agent")
    session_id: Optional[str] = Field(None, description="Session identifier")
    request_id: str = Field(..., description="Unique request ID for correlation")
    original_request_decision_id: Optional[str] = Field(
        None,
        description="Decision ID of the original request (for response evaluation)",
    )


class DecisionRequest(BaseModel):
    """Request payload for decision API."""

    # Identification (using new terminology)
    organisation_id: str = Field(..., description="Organisation identifier")
    mcp_server_workspace_id: str = Field(
        ..., description="MCP Server Workspace identifier"
    )
    agent_access_id: str = Field(..., description="Agent access identifier")

    # Message context
    direction: Direction = Field(..., description="Request or response")
    transport: Transport = Field(..., description="STDIO or HTTP")

    # The actual MCP message
    message: MCPMessage = Field(..., description="MCP JSON-RPC message")

    # Additional context
    metadata: DecisionMetadata = Field(..., description="Request metadata")


class GuardrailEvent(BaseModel):
    """Event from a guardrail evaluation."""

    guardrail_type: str = Field(..., description="Type of guardrail")
    triggered: bool = Field(..., description="Whether guardrail was triggered")
    action_taken: str = Field(..., description="Action taken by guardrail")
    details: dict[str, Any] = Field(default_factory=dict, description="Event details")
    severity: Severity = Field(default=Severity.INFO, description="Event severity")


class DecisionResponse(BaseModel):
    """Response from decision API."""

    # Core decision
    allow: bool = Field(..., description="Whether to allow the message")
    action: DecisionAction = Field(..., description="Action to take")

    # Optional modifications
    modified_message: Optional[MCPMessage] = Field(
        None,
        description="Modified message if action is MODIFY",
    )

    # Explanation
    reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable reasons",
    )

    # Detailed events
    guardrail_events: list[GuardrailEvent] = Field(
        default_factory=list,
        description="Events from guardrail evaluations",
    )

    # Metadata
    decision_id: str = Field(..., description="Unique decision ID for audit")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class DecisionErrorResponse(BaseModel):
    """Error response from decision API."""

    error: dict[str, Any] = Field(..., description="Error details")
    decision_id: Optional[str] = Field(None, description="Decision ID if available")


class BatchDecisionRequest(BaseModel):
    """Request for batch decision evaluation."""

    requests: list[DecisionRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Batch of decision requests",
    )


class BatchDecisionResponse(BaseModel):
    """Response for batch decision evaluation."""

    decisions: list[DecisionResponse] = Field(..., description="Decision results")
    batch_id: str = Field(..., description="Batch identifier")
    total_processing_time_ms: int = Field(
        ...,
        description="Total processing time",
    )
