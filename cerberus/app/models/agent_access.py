"""
Agent Access Model

Agent Access provides authentication for AI agents connecting to MCP servers
through the Cerberus Gateway.

Unlike the old UserAccessKey model, AgentAccess is NOT tied to a User.
Agents are standalone entities scoped directly to an MCP Server Workspace.

Key Format: "ca-{random_base64}" (e.g., "ca-abc123xyz789...")
- "ca-" prefix identifies it as a Cerberus Agent Access key
- 32 bytes of cryptographically random data (base64 encoded)

Key Security:
- The actual key is shown ONLY ONCE when created
- We store only the SHA-256 hash of the key in the database
- Keys can be rotated with a grace period for zero-downtime updates

Access Control:
- Agent permissions are controlled entirely by Policies and Guardrails
- No separate "scopes" field - RBAC guardrail controls tool access
- Rate limiting guardrails control request limits
- PII/Content guardrails control data handling

SAMPLE AGENT ACCESS RECORD:
┌──────────────────────────────────────────────────────────────────────────────┐
│ id                       │ dd0e8400-e29b-41d4-a716-446655440020              │
│ mcp_server_workspace_id  │ 660e8400-e29b-41d4-a716-446655440001              │
│ name                     │ "Production AI Agent"                              │
│ description              │ "Claude agent for production environment"          │
│ key_hash                 │ "a1b2c3d4e5f6..."  (SHA-256 hash, 64 hex chars)   │
│ key_prefix               │ "za-prod-ab12..."  (for identification in logs)   │
│ is_active                │ true                                               │
│ is_revoked               │ false                                              │
│ expires_at               │ null  (null = never expires)                       │
│ last_used_at             │ 2024-01-15T14:30:00Z                              │
│ usage_count              │ 15234                                              │
│ metadata                 │ {"created_by": "admin@acme.com"}                   │
│ created_at               │ 2024-01-01T00:00:00Z                              │
│ updated_at               │ 2024-01-15T14:30:00Z                              │
└──────────────────────────────────────────────────────────────────────────────┘

Derived Context (from relationships):
- organisation_id: workspace.organisation_id
- mcp_server_url: workspace.mcp_server_url
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.mcp_server_workspace import McpServerWorkspace
    from app.models.policy import Policy


class AgentAccess(Base, TimestampMixin):
    """
    Agent Access model for gateway authentication.

    Each agent access belongs to an MCP Server Workspace (NOT a user).
    This provides:
    - WHAT: The agent identity (name, description)
    - WHERE: mcp_server_workspace_id (required)
    - PERMISSIONS: Controlled by Policies & Guardrails (not scopes)

    The organisation_id is derived from the workspace relationship.
    The mcp_server_url is derived from the workspace relationship.

    Access Control:
    - Permissions are NOT controlled by "scopes" on this model
    - Instead, Policies link Guardrails to agents
    - RBAC guardrail = tool access control
    - Rate limit guardrail = request limits
    - PII/Content guardrails = data handling

    Security Notes:
    - Never store the actual key; only store its SHA-256 hash
    - The key is shown only once when created
    - Support key rotation with grace periods
    - Track usage for anomaly detection

    Attributes:
        id: Unique identifier (UUID v4)
        mcp_server_workspace_id: Reference to the workspace this agent accesses
        name: Human-readable name for the agent
        description: Optional description of agent purpose
        key_hash: SHA-256 hash of the actual key
        key_prefix: Visible prefix for identification
        is_active: Whether agent access is currently active
        is_revoked: Whether access has been revoked
        expires_at: Optional expiration timestamp
        last_used_at: When the agent was last used
        usage_count: Number of times agent has been used
        metadata_: Custom metadata

    Relationships:
        mcp_server_workspace: The workspace this agent can access
        policies: Policies attached to this specific agent
    """

    __tablename__ = "agent_accesses"

    # ==========================================================================
    # PRIMARY KEY
    # ==========================================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the agent access",
    )

    # ==========================================================================
    # FOREIGN KEYS
    # ==========================================================================

    # WHERE: Reference to the MCP Server Workspace this agent can access
    mcp_server_workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_server_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the workspace this agent can access",
    )

    # ==========================================================================
    # AGENT IDENTIFICATION
    # ==========================================================================

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable name for the agent",
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional description explaining the agent's purpose",
    )

    # ==========================================================================
    # KEY CREDENTIALS (SECURITY-SENSITIVE)
    # ==========================================================================

    key_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        doc="SHA-256 hash of the actual key (NEVER store the actual key)",
    )

    key_prefix: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Visible prefix of the key for identification in logs/UI",
    )

    # Note: Removed "scopes" field for MVP.
    # Agent permissions are controlled entirely by Policies and Guardrails.
    # See RBAC guardrail for tool access control.

    # ==========================================================================
    # STATUS FLAGS
    # ==========================================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the agent access is currently active",
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the agent access has been permanently revoked",
    )

    # ==========================================================================
    # EXPIRATION
    # ==========================================================================

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Optional expiration timestamp (NULL = never expires)",
    )

    # ==========================================================================
    # USAGE TRACKING
    # ==========================================================================

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the agent was last used",
    )

    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="How many times the agent has been used",
    )

    # ==========================================================================
    # CUSTOM METADATA
    # ==========================================================================

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        doc="Custom metadata for the agent access",
    )

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    # Many-to-One: Agent Access is scoped to one MCP Server Workspace
    mcp_server_workspace: Mapped["McpServerWorkspace"] = relationship(
        "McpServerWorkspace",
        back_populates="agent_accesses",
    )

    # One-to-Many: Agent Access can have policies attached to it
    policies: Mapped[list["Policy"]] = relationship(
        "Policy",
        back_populates="agent_access",
        cascade="all, delete-orphan",
    )

    # ==========================================================================
    # TABLE CONSTRAINTS & INDEXES
    # ==========================================================================

    __table_args__ = (
        # Composite index for listing active agents in a workspace
        # Used by get_valid_key_with_context() and workspace agent listings
        Index(
            "ix_agent_accesses_workspace_status",
            "mcp_server_workspace_id",
            "is_active",
            "is_revoked",
        ),
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<AgentAccess(id={self.id}, name={self.name})>"

    @property
    def is_expired(self) -> bool:
        """Check if the agent access has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the agent access is valid (can be used for authentication)."""
        return self.is_active and not self.is_revoked and not self.is_expired

    # Note: Removed has_scope() method.
    # Permission checks are done via Policies and Guardrails, not scopes.
