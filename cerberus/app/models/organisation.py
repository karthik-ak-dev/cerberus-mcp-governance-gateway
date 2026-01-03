"""
Organisation Model

An Organisation represents a customer organization using the Cerberus Platform.
This is the top-level entity in the multi-tenant hierarchy:

    Organisation
       └── MCP Server Workspaces (Environments like prod, staging, dev)
              └── Agent Accesses (AI agents connecting to MCP servers)
              └── Policies (Guardrail configurations)
       └── Users (Dashboard access for admins/viewers)

Each organisation is completely isolated from others, with their own:
- MCP Server Workspaces and environments
- Users for dashboard access
- Agent Accesses for AI agent authentication
- Policies and guardrail configurations
- Audit logs and analytics

SAMPLE ORGANISATION RECORD:
┌──────────────────────────────────────────────────────────────────────────────┐
│ id               │ 550e8400-e29b-41d4-a716-446655440000                      │
│ name             │ "Acme Corporation"                                         │
│ slug             │ "acme-corp"                                                │
│ description      │ "Enterprise software company using AI tools"              │
│ is_active        │ true                                                       │
│ subscription_tier│ "default"                                                  │
│ settings         │ {                                                          │
│                  │   "default_fail_mode": "closed",                           │
│                  │   "max_mcp_server_workspaces": 10,                         │
│                  │   "max_users": 50,                                         │
│                  │   "data_retention_days": 90,                               │
│                  │   "allowed_guardrails": ["rbac", "pii_ssn", ...]          │
│                  │ }                                                          │
│ created_at       │ 2024-01-01T00:00:00Z                                      │
│ updated_at       │ 2024-01-15T10:30:00Z                                      │
│ deleted_at       │ null                                                       │
└──────────────────────────────────────────────────────────────────────────────┘
"""

import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import Boolean, Column, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import SubscriptionTier
from app.models.base import Base, EnumValidationMixin, SoftDeleteMixin, TimestampMixin

# TYPE_CHECKING block prevents circular imports while enabling type hints
if TYPE_CHECKING:
    from app.models.mcp_server_workspace import McpServerWorkspace
    from app.models.policy import Policy
    from app.models.user import User


class Organisation(Base, TimestampMixin, SoftDeleteMixin, EnumValidationMixin):
    """
    Organisation model representing a customer organization.

    An organisation is the root entity in the multi-tenant architecture.
    All resources (workspaces, users, policies, etc.) belong to an organisation.

    Attributes:
        id: Unique identifier (UUID v4)
        name: Human-readable organization name for display
        slug: URL-safe identifier used in API paths and configs
        description: Optional longer description of the organisation
        is_active: Whether the organisation account is active
        subscription_tier: Pricing tier determining feature access
        settings: JSON configuration for organisation-wide settings

    Relationships:
        mcp_server_workspaces: All MCP server workspaces belonging to this org
        users: All users (dashboard access) in this organization
        policies: Organisation-level default policies
    """

    __tablename__ = "organisations"

    # Enum field validation mapping
    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "subscription_tier": SubscriptionTier,
    }

    # ==========================================================================
    # PRIMARY KEY
    # ==========================================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the organisation",
    )

    # ==========================================================================
    # BASIC INFORMATION
    # ==========================================================================

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable name of the organization",
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="URL-safe unique identifier for the organisation",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional longer description of the organisation",
    )

    # ==========================================================================
    # STATUS FLAGS
    # ==========================================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the organisation account is currently active",
    )

    # ==========================================================================
    # SUBSCRIPTION & BILLING
    # ==========================================================================

    subscription_tier: Mapped[str] = mapped_column(
        String(50),
        default=SubscriptionTier.DEFAULT.value,
        nullable=False,
        doc="Subscription tier determining features and limits",
    )

    # ==========================================================================
    # SETTINGS (JSON CONFIGURATION)
    # ==========================================================================

    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Flexible JSON settings for organisation configuration",
    )

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    # One-to-Many: An organisation has many MCP server workspaces
    mcp_server_workspaces: Mapped[list["McpServerWorkspace"]] = relationship(
        "McpServerWorkspace",
        back_populates="organisation",
        cascade="all, delete-orphan",
    )

    # One-to-Many: An organisation has many users (dashboard access)
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organisation",
        cascade="all, delete-orphan",
    )

    # One-to-Many: An organisation has many policies (org-level defaults)
    policies: Mapped[list["Policy"]] = relationship(
        "Policy",
        back_populates="organisation",
        cascade="all, delete-orphan",
    )

    # ==========================================================================
    # TABLE CONSTRAINTS & INDEXES
    # ==========================================================================

    __table_args__ = (
        # Unique slug globally (for non-deleted organisations)
        Index(
            "uq_organisations_slug",
            "slug",
            unique=True,
            postgresql_where=(Column("deleted_at").is_(None)),
        ),
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Organisation(id={self.id}, slug={self.slug})>"

    @property
    def default_fail_mode(self) -> str:
        """Get the default fail mode from settings."""
        return self.settings.get("default_fail_mode", "closed")

    @property
    def max_mcp_server_workspaces(self) -> int:
        """Get maximum number of MCP server workspaces allowed."""
        return self.settings.get("max_mcp_server_workspaces", 10)

    @property
    def max_users(self) -> int:
        """Get maximum number of users allowed."""
        return self.settings.get("max_users", 50)

    @property
    def data_retention_days(self) -> int:
        """Get audit log retention period in days."""
        return self.settings.get("data_retention_days", 90)
