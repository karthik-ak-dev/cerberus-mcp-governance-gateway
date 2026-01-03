"""
Audit Log Model

Audit Logs record every governance decision made by Cerberus.
They provide a complete audit trail for compliance, debugging, and analytics.

Each log entry captures:
- The decision context (which agent, what tool, when, where)
- The decision outcome (DecisionAction enum values)
- Policy evaluation details (which guardrails fired)
- Timing information (for performance monitoring)

Log Retention:
- Logs are retained based on organisation's data_retention_days setting
- Old logs are archived/deleted by a background job
- Sensitive data may be redacted based on log_level setting

SAMPLE AUDIT LOG (Allowed Request):
┌──────────────────────────────────────────────────────────────────────────────┐
│ id                       │ ff0e8400-e29b-41d4-a716-446655440030              │
│ organisation_id          │ 550e8400-e29b-41d4-a716-446655440000              │
│ mcp_server_workspace_id  │ 660e8400-e29b-41d4-a716-446655440001              │
│ agent_access_id          │ dd0e8400-e29b-41d4-a716-446655440020              │
│ agent_name               │ "Production Claude Agent"                          │
│ session_id               │ "sess-abc123..."                                   │
│ request_id               │ "req-xyz789..."                                    │
│ message_type             │ "request"                                          │
│ tool_name                │ "filesystem/read_file"                             │
│ decision                 │ "allow"                                            │
│ decision_reason          │ "All guardrails passed"                            │
│ guardrail_results        │ {...}                                              │
│ latency_ms               │ 12                                                 │
│ created_at               │ 2024-01-15T14:30:00Z                              │
└──────────────────────────────────────────────────────────────────────────────┘
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import DecisionAction, Direction
from app.models.base import Base, EnumValidationMixin

if TYPE_CHECKING:
    from app.models.mcp_server_workspace import McpServerWorkspace


class AuditLog(Base, EnumValidationMixin):
    """
    Audit Log model recording governance decisions.

    Every decision made by the governance engine is logged here.
    This provides an immutable audit trail for compliance and debugging.

    Note: This model doesn't use TimestampMixin because:
    - Audit logs are immutable (no updated_at needed)
    - created_at is the decision timestamp
    - We don't soft-delete audit logs (they're archived instead)

    Attributes:
        id: Unique identifier (UUID v4)
        organisation_id: Reference to organisation
        mcp_server_workspace_id: Reference to workspace
        agent_access_id: Reference to agent access that made the request
        agent_name: Name of the agent (denormalized for query convenience)
        session_id: Session identifier for grouping related requests
        request_id: Unique ID for this governance request
        message_type: "request" or "response" evaluation
        tool_name: MCP tool being invoked
        decision: DecisionAction enum value (allow, block_request, block_response, modify, log_only, throttle)
        decision_reason: Human-readable explanation
        guardrail_results: Detailed results from each guardrail
        request_summary: Summary of the request (may be redacted)
        response_summary: Summary of the response (may be redacted)
        modifications: List of modifications made
        latency_ms: Total decision time in milliseconds
        ip_address: Gateway IP address
        created_at: Timestamp of the decision

    Relationships:
        mcp_server_workspace: Associated workspace
    """

    # Enum field validation mapping
    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "message_type": Direction,
        "decision": DecisionAction,
    }

    __tablename__ = "audit_logs"

    # ==========================================================================
    # PRIMARY KEY
    # ==========================================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for this audit log entry",
    )

    # ==========================================================================
    # CONTEXT: Organisation and Workspace
    # ==========================================================================

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="Reference to organisation (denormalized for query performance)",
    )

    mcp_server_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_server_workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Reference to workspace where decision was made",
    )

    # ==========================================================================
    # AGENT CONTEXT
    # ==========================================================================

    agent_access_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="Reference to agent access that made the request",
    )

    agent_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Name of the agent (denormalized for convenience)",
    )

    # ==========================================================================
    # SESSION AND REQUEST IDENTIFICATION
    # ==========================================================================

    session_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Session ID for grouping related requests",
    )

    request_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Unique identifier for this governance request",
    )

    message_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Type of message being evaluated: 'request' or 'response'",
    )

    tool_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Name of the MCP tool being invoked",
    )

    # ==========================================================================
    # DECISION OUTCOME
    # ==========================================================================

    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Final decision: DecisionAction enum value",
    )

    decision_reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Human-readable explanation of the decision",
    )

    # ==========================================================================
    # GUARDRAIL EVALUATION DETAILS
    # ==========================================================================

    guardrail_results: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Detailed results from each guardrail evaluation",
    )

    # ==========================================================================
    # REQUEST/RESPONSE SUMMARIES
    # ==========================================================================

    request_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Summary of the request (may be redacted)",
    )

    response_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Summary of the response (may be redacted)",
    )

    # ==========================================================================
    # MODIFICATIONS MADE
    # ==========================================================================

    modifications: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="List of modifications applied to request/response",
    )

    # ==========================================================================
    # PERFORMANCE & METADATA
    # ==========================================================================

    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Total time to make the decision in milliseconds",
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        doc="IP address of the client",
    )

    # ==========================================================================
    # TIMESTAMP
    # ==========================================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
        doc="When this decision was made",
    )

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    mcp_server_workspace: Mapped["McpServerWorkspace | None"] = relationship(
        "McpServerWorkspace",
        back_populates="audit_logs",
    )

    # ==========================================================================
    # TABLE CONFIGURATION
    # ==========================================================================

    __table_args__ = (
        # Composite index for common query patterns
        Index("ix_audit_logs_org_created", "organisation_id", "created_at"),
        Index("ix_audit_logs_workspace_created", "mcp_server_workspace_id", "created_at"),
        # Index for filtering by decision type (e.g., show all blocked requests)
        Index("ix_audit_logs_org_decision", "organisation_id", "decision", "created_at"),
        # Index for agent-specific analytics
        Index("ix_audit_logs_agent_created", "agent_access_id", "created_at"),
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<AuditLog(id={self.id}, decision={self.decision})>"

    @property
    def was_blocked(self) -> bool:
        """Check if this decision was a block."""
        return self.decision in (
            DecisionAction.BLOCK_REQUEST.value,
            DecisionAction.BLOCK_RESPONSE.value,
            DecisionAction.THROTTLE.value,
        )

    @property
    def was_modified(self) -> bool:
        """Check if this decision resulted in modifications."""
        return self.decision == DecisionAction.MODIFY.value

    @property
    def was_allowed(self) -> bool:
        """Check if this decision was an allow."""
        return self.decision in (
            DecisionAction.ALLOW.value,
            DecisionAction.LOG_ONLY.value,
        )

    def get_guardrail_status(self, guardrail_type: str) -> str | None:
        """
        Get the status of a specific guardrail evaluation.

        Args:
            guardrail_type: Type of guardrail (e.g., "rbac", "pii_ssn")

        Returns:
            Status string ("pass", "fail", "skip") or None if not evaluated
        """
        result = self.guardrail_results.get(guardrail_type, {})
        return result.get("status")
