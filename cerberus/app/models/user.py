"""
User Model

A User represents an individual who can access the Cerberus dashboard.
Users are for DASHBOARD access only - they are NOT used for MCP authentication.

AI agents use AgentAccess for MCP authentication, not Users.

User Roles (Simplified for MVP):
- super_admin: Platform admin (system administrators) - can access all organisations
- org_admin: Full admin for their organisation - manage workspaces, agents, policies
- org_viewer: Read-only access to view dashboards and logs

Note: No workspace-level user management for MVP. Users have org-wide access
based on their role. org_admin can manage ALL workspaces in their organisation.

SAMPLE USER RECORD (Admin):
┌──────────────────────────────────────────────────────────────────────────────┐
│ id               │ 770e8400-e29b-41d4-a716-446655440002                      │
│ organisation_id  │ 550e8400-e29b-41d4-a716-446655440000                      │
│ email            │ "admin@acme.com"                                          │
│ display_name     │ "Admin User"                                              │
│ password_hash    │ "$2b$12$LQv3c1yqBw..."  (bcrypt hash)                     │
│ role             │ "org_admin"                                               │
│ is_active        │ true                                                      │
│ metadata         │ {"last_login": "2024-01-15T10:00:00Z"}                    │
│ created_at       │ 2024-01-01T00:00:00Z                                      │
│ updated_at       │ 2024-01-15T10:30:00Z                                      │
│ deleted_at       │ null                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
"""

import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import Boolean, Column, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import UserRole
from app.models.base import Base, EnumValidationMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.organisation import Organisation


# Note: Removed user_mcp_server_workspaces association table for MVP.
# Users have org-wide access based on role (org_admin or org_viewer).
# Workspace-level user permissions can be added post-MVP if needed.


class User(Base, TimestampMixin, SoftDeleteMixin, EnumValidationMixin):
    """
    User model for dashboard access.

    Users access the Cerberus dashboard to manage organisations,
    workspaces, agent accesses, and policies.

    NOTE: Users are NOT used for MCP/agent authentication.
    AI agents use AgentAccess keys to authenticate with the gateway.

    MVP Roles:
    - super_admin: Platform admin, can access all organisations
    - org_admin: Full admin for their organisation
    - org_viewer: Read-only access to dashboards/logs

    Attributes:
        id: Unique identifier (UUID v4)
        organisation_id: Reference to parent organisation (NULL for super_admin)
        email: Email address (used for login)
        display_name: Human-readable name for UI display
        password_hash: Bcrypt hash for login
        role: User's role determining dashboard permissions
        is_active: Whether user account is active
        metadata_: Custom attributes

    Relationships:
        organisation: Parent organisation
    """

    __tablename__ = "users"

    # Enum field validation mapping
    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "role": UserRole,
    }

    # ==========================================================================
    # PRIMARY KEY
    # ==========================================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the user",
    )

    # ==========================================================================
    # FOREIGN KEYS
    # ==========================================================================

    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=True,  # NULL for super_admin (platform-level users)
        index=True,
        doc="Reference to the parent organisation (NULL for super_admin)",
    )

    # ==========================================================================
    # IDENTITY FIELDS
    # ==========================================================================

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Email address (used for login)",
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable display name",
    )

    # ==========================================================================
    # AUTHENTICATION
    # ==========================================================================

    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Bcrypt-hashed password for login",
    )

    # ==========================================================================
    # ROLE-BASED ACCESS CONTROL
    # ==========================================================================

    role: Mapped[str] = mapped_column(
        String(50),
        default=UserRole.ORG_VIEWER.value,
        nullable=False,
        doc="User's role determining dashboard permissions (org_admin or org_viewer)",
    )

    # ==========================================================================
    # STATUS FLAGS
    # ==========================================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the user account is active",
    )

    # ==========================================================================
    # CUSTOM METADATA
    # ==========================================================================

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        doc="Custom attributes for the user",
    )

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    organisation: Mapped["Organisation | None"] = relationship(
        "Organisation",
        back_populates="users",
    )

    # Note: Removed mcp_server_workspaces relationship for MVP.
    # Users have org-wide access based on role (org_admin or org_viewer).

    # ==========================================================================
    # TABLE CONSTRAINTS & INDEXES
    # ==========================================================================

    __table_args__ = (
        # Unique email per organisation (for non-deleted users)
        Index(
            "uq_users_org_email",
            "organisation_id",
            "email",
            unique=True,
            postgresql_where=(Column("deleted_at").is_(None)),
        ),
        # Unique email for super admins (organisation_id IS NULL)
        Index(
            "uq_users_super_admin_email",
            "email",
            unique=True,
            postgresql_where=(
                (Column("organisation_id").is_(None))
                & (Column("deleted_at").is_(None))
            ),
        ),
        # Composite index for listing users in an organisation (soft delete aware)
        Index(
            "ix_users_org_deleted",
            "organisation_id",
            "deleted_at",
        ),
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User(id={self.id}, email={self.email})>"

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return self.role == role

    def has_any_role(self, roles: list[str]) -> bool:
        """Check if user has any of the specified roles."""
        return self.role in roles

    @property
    def is_super_admin(self) -> bool:
        """Check if user is a super admin."""
        return self.role == UserRole.SUPER_ADMIN.value

    @property
    def is_org_admin(self) -> bool:
        """Check if user is an organisation admin."""
        return self.role == UserRole.ORG_ADMIN.value
