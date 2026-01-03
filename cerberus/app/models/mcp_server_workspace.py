"""
MCP Server Workspace Model

An MCP Server Workspace represents an environment within an organisation.
This is where AI agents connect to MCP servers through the Cerberus Gateway.

Common examples include production, staging, and development environments.

Hierarchy:
    Organisation
       └── MCP Server Workspace (this model)
              └── Agent Accesses (AI agents connecting to this workspace)
              └── Policies (workspace-level guardrail configurations)
              └── Audit Logs (per-workspace logging)

SAMPLE MCP SERVER WORKSPACE RECORD:
┌──────────────────────────────────────────────────────────────────────────────┐
│ id               │ 660e8400-e29b-41d4-a716-446655440001                      │
│ organisation_id  │ 550e8400-e29b-41d4-a716-446655440000                      │
│ name             │ "Production"                                               │
│ slug             │ "prod"                                                     │
│ description      │ "Production MCP server with strict governance"            │
│ environment_type │ "production"                                               │
│ is_active        │ true                                                       │
│ mcp_server_url   │ "https://mcp.example.com/production"                      │
│ settings         │ {                                                          │
│                  │   "fail_mode": "closed",                                   │
│                  │   "decision_timeout_ms": 5000,                             │
│                  │   "log_level": "verbose"                                   │
│                  │ }                                                          │
│ created_at       │ 2024-01-02T00:00:00Z                                      │
│ updated_at       │ 2024-01-15T10:30:00Z                                      │
│ deleted_at       │ null                                                       │
└──────────────────────────────────────────────────────────────────────────────┘
"""

import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import EnvironmentType
from app.models.base import Base, EnumValidationMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.agent_access import AgentAccess
    from app.models.audit_log import AuditLog
    from app.models.organisation import Organisation
    from app.models.policy import Policy


class McpServerWorkspace(Base, TimestampMixin, SoftDeleteMixin, EnumValidationMixin):
    """
    MCP Server Workspace model representing an environment within an organisation.

    Workspaces provide isolation between different environments
    (production, staging, development) within the same organization.
    Each workspace connects to a specific MCP server.

    Attributes:
        id: Unique identifier (UUID v4)
        organisation_id: Reference to parent organisation
        name: Human-readable workspace name
        slug: URL-safe identifier (unique within organisation)
        description: Optional description
        environment_type: Type of environment (production/staging/development)
        is_active: Whether the workspace is active
        mcp_server_url: URL of the MCP server to proxy to
        settings: JSON configuration overriding organisation defaults

    Relationships:
        organisation: Parent organisation
        agent_accesses: AI agents configured to use this workspace
        policies: Workspace-level policy overrides
        audit_logs: Audit logs for this workspace
    """

    __tablename__ = "mcp_server_workspaces"

    # Enum field validation mapping
    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "environment_type": EnvironmentType,
    }

    # ==========================================================================
    # PRIMARY KEY
    # ==========================================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the workspace",
    )

    # ==========================================================================
    # FOREIGN KEYS
    # ==========================================================================

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the parent organisation",
    )

    # ==========================================================================
    # BASIC INFORMATION
    # ==========================================================================

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable name of the workspace",
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="URL-safe identifier for the workspace (unique within organisation)",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description of the workspace purpose",
    )

    # ==========================================================================
    # ENVIRONMENT CONFIGURATION
    # ==========================================================================

    environment_type: Mapped[str] = mapped_column(
        String(50),
        default=EnvironmentType.DEVELOPMENT.value,
        nullable=False,
        doc="Type of environment (production/staging/development)",
    )

    # ==========================================================================
    # STATUS FLAGS
    # ==========================================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the workspace is currently active",
    )

    # ==========================================================================
    # MCP SERVER CONFIGURATION
    # ==========================================================================

    mcp_server_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="URL of the MCP server this workspace routes to",
    )

    # ==========================================================================
    # SETTINGS (JSON CONFIGURATION)
    # ==========================================================================

    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Workspace-specific settings that override organisation defaults",
    )

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    # Many-to-One: Workspace belongs to one Organisation
    organisation: Mapped["Organisation"] = relationship(
        "Organisation",
        back_populates="mcp_server_workspaces",
    )

    # Note: Removed users relationship for MVP.
    # Users have org-wide access based on role (org_admin or org_viewer).

    # One-to-Many: Workspace can have many policies
    policies: Mapped[list["Policy"]] = relationship(
        "Policy",
        back_populates="mcp_server_workspace",
        cascade="all, delete-orphan",
    )

    # One-to-Many: Workspace has many audit logs
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="mcp_server_workspace",
        cascade="all, delete-orphan",
    )

    # One-to-Many: Workspace has many agent accesses
    agent_accesses: Mapped[list["AgentAccess"]] = relationship(
        "AgentAccess",
        back_populates="mcp_server_workspace",
        cascade="all, delete-orphan",
    )

    # ==========================================================================
    # TABLE CONSTRAINTS & INDEXES
    # ==========================================================================

    __table_args__ = (
        # Unique slug per organisation (for non-deleted workspaces)
        Index(
            "uq_mcp_server_workspaces_org_slug",
            "organisation_id",
            "slug",
            unique=True,
            postgresql_where=(Column("deleted_at").is_(None)),
        ),
        # Composite index for listing workspaces in an organisation (soft delete aware)
        Index(
            "ix_mcp_server_workspaces_org_deleted",
            "organisation_id",
            "deleted_at",
        ),
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<McpServerWorkspace(id={self.id}, slug={self.slug})>"

    @property
    def fail_mode(self) -> str | None:
        """Get fail mode from settings (None means inherit from organisation)."""
        return self.settings.get("fail_mode")

    @property
    def decision_timeout_ms(self) -> int:
        """Get maximum time to wait for a governance decision."""
        return self.settings.get("decision_timeout_ms", 5000)

    @property
    def log_level(self) -> str:
        """Get audit log verbosity level."""
        return self.settings.get("log_level", "standard")

    @property
    def is_production(self) -> bool:
        """Check if this is a production environment."""
        return self.environment_type == EnvironmentType.PRODUCTION.value
