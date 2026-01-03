"""
Policy Model (Simplified)

A Policy links a Guardrail to an entity (Organisation, Workspace, or Agent).
Each policy configures ONE guardrail for ONE scope.

Policy Hierarchy:
    Organisation Policy (org-wide defaults)
    MCP Server Workspace Policy (workspace-level overrides)
    Agent Policy (agent-specific rules)

Unlike the previous complex model, this simplified approach:
- ONE guardrail per policy (not a nested JSON of all guardrails)
- NO priority-based merging (each policy is independent)
- Policies attach to entities directly via foreign keys

SAMPLE POLICIES:

Organisation-level policy (blocks SSN org-wide):
┌──────────────────────────────────────────────────────────────────────────────┐
│ id                       │ aa0e8400-e29b-41d4-a716-446655440010              │
│ organisation_id          │ 550e8400-e29b-41d4-a716-446655440000              │
│ mcp_server_workspace_id  │ null  (org-level)                                  │
│ agent_access_id          │ null  (applies to all agents)                      │
│ guardrail_id             │ 111e8400-e29b-41d4-a716-446655440001 (pii_ssn)     │
│ name                     │ "Block SSN Org-wide"                               │
│ config                   │ {"direction": "both"}                              │
│ action                   │ "block"                                            │
│ is_enabled               │ true                                               │
└──────────────────────────────────────────────────────────────────────────────┘

Workspace-level policy (rate limit for production):
┌──────────────────────────────────────────────────────────────────────────────┐
│ id                       │ bb0e8400-e29b-41d4-a716-446655440011              │
│ organisation_id          │ 550e8400-e29b-41d4-a716-446655440000              │
│ mcp_server_workspace_id  │ 660e8400-e29b-41d4-a716-446655440001 (production) │
│ agent_access_id          │ null  (applies to all agents in workspace)        │
│ guardrail_id             │ 222e8400-e29b-41d4-a716-446655440002 (rate_limit) │
│ name                     │ "Production Rate Limit"                            │
│ config                   │ {"limit": 30}                                      │
│ action                   │ "block"                                            │
│ is_enabled               │ true                                               │
└──────────────────────────────────────────────────────────────────────────────┘

Agent-level policy (RBAC for specific agent):
┌──────────────────────────────────────────────────────────────────────────────┐
│ id                       │ cc0e8400-e29b-41d4-a716-446655440012              │
│ organisation_id          │ 550e8400-e29b-41d4-a716-446655440000              │
│ mcp_server_workspace_id  │ 660e8400-e29b-41d4-a716-446655440001              │
│ agent_access_id          │ dd0e8400-e29b-41d4-a716-446655440020              │
│ guardrail_id             │ 333e8400-e29b-41d4-a716-446655440003 (rbac)       │
│ name                     │ "Claude Agent RBAC"                                │
│ config                   │ {"allowed_tools": ["filesystem/*", "git/*"]}      │
│ action                   │ "block"                                            │
│ is_enabled               │ true                                               │
└──────────────────────────────────────────────────────────────────────────────┘
"""

import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import PolicyAction, PolicyLevel
from app.models.base import Base, EnumValidationMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.agent_access import AgentAccess
    from app.models.guardrail import Guardrail
    from app.models.mcp_server_workspace import McpServerWorkspace
    from app.models.organisation import Organisation


class Policy(Base, TimestampMixin, SoftDeleteMixin, EnumValidationMixin):
    """
    Policy model linking a guardrail to an entity.

    Each policy configures ONE guardrail for ONE scope:
    - Organisation level: mcp_server_workspace_id=NULL, agent_access_id=NULL
    - Workspace level: mcp_server_workspace_id set, agent_access_id=NULL
    - Agent level: both mcp_server_workspace_id and agent_access_id set

    Attributes:
        id: Unique identifier (UUID v4)
        organisation_id: Reference to parent organisation (required)
        mcp_server_workspace_id: Reference to workspace (NULL for org-level)
        agent_access_id: Reference to agent (NULL for workspace/org-level)
        guardrail_id: Reference to the guardrail this policy configures
        name: Human-readable policy name
        description: Optional description of policy purpose
        config: Guardrail-specific configuration overrides
        action: Action to take (block, redact, alert, audit_only)
        is_enabled: Whether this policy is active

    Relationships:
        organisation: Parent organisation
        mcp_server_workspace: Parent workspace (if workspace/agent-level)
        agent_access: Target agent (if agent-level)
        guardrail: The guardrail this policy configures
    """

    __tablename__ = "policies"

    # Enum field validation mapping
    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "action": PolicyAction,
    }

    # ==========================================================================
    # PRIMARY KEY
    # ==========================================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the policy",
    )

    # ==========================================================================
    # SCOPE FOREIGN KEYS
    # ==========================================================================

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the parent organisation (always required)",
    )

    mcp_server_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_server_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Reference to workspace (NULL = org-level policy)",
    )

    agent_access_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_accesses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Reference to agent (NULL = workspace/org-level policy)",
    )

    # ==========================================================================
    # GUARDRAIL REFERENCE
    # ==========================================================================

    guardrail_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guardrails.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the guardrail this policy configures",
    )

    # ==========================================================================
    # BASIC INFORMATION
    # ==========================================================================

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable name for the policy",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description explaining the policy's purpose",
    )

    # ==========================================================================
    # POLICY CONFIGURATION
    # ==========================================================================

    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Guardrail-specific configuration overrides",
    )

    action: Mapped[str] = mapped_column(
        String(50),
        default=PolicyAction.BLOCK.value,
        nullable=False,
        doc="Action to take when guardrail triggers (block, redact, alert, audit_only)",
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether this policy is currently active",
    )

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    organisation: Mapped["Organisation"] = relationship(
        "Organisation",
        back_populates="policies",
    )

    mcp_server_workspace: Mapped["McpServerWorkspace | None"] = relationship(
        "McpServerWorkspace",
        back_populates="policies",
    )

    agent_access: Mapped["AgentAccess | None"] = relationship(
        "AgentAccess",
        back_populates="policies",
    )

    guardrail: Mapped["Guardrail"] = relationship(
        "Guardrail",
        back_populates="policies",
    )

    # ==========================================================================
    # TABLE CONSTRAINTS & INDEXES
    # ==========================================================================

    __table_args__ = (
        # Ensure only one policy per guardrail per scope (for non-deleted policies)
        # This prevents duplicate policies for the same guardrail at the same level
        Index(
            "uq_policy_guardrail_per_scope",
            "organisation_id",
            "mcp_server_workspace_id",
            "agent_access_id",
            "guardrail_id",
            unique=True,
            postgresql_where=(Column("deleted_at").is_(None)),
        ),
        # CRITICAL: Hot path index for get_effective_policies()
        # Used on every governance decision to load applicable policies
        Index(
            "ix_policies_effective_lookup",
            "organisation_id",
            "deleted_at",
            "is_enabled",
        ),
        # Index for workspace-level policy lookups
        Index(
            "ix_policies_workspace_lookup",
            "mcp_server_workspace_id",
            "deleted_at",
        ),
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Policy(id={self.id}, name={self.name})>"

    @property
    def level(self) -> str:
        """
        Determine the policy level based on foreign keys.

        Returns:
            "organisation" - Organisation-wide default
            "workspace" - MCP Server Workspace-specific
            "agent" - Agent-specific policy
        """
        if self.agent_access_id:
            return PolicyLevel.AGENT.value
        if self.mcp_server_workspace_id:
            return PolicyLevel.WORKSPACE.value
        return PolicyLevel.ORGANISATION.value
