"""
User Schemas

Request/response models for user endpoints.
Users are for DASHBOARD access only - they are NOT used for MCP authentication.

MVP Roles:
- super_admin: Platform admin (system administrators)
- org_admin: Full admin for their organisation
- org_viewer: Read-only access to dashboards/logs
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.config.constants import UserRole
from app.schemas.common import BaseSchema


class UserBase(BaseModel):
    """Base user fields."""

    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Display name",
    )
    email: EmailStr = Field(..., description="Email address (used for login)")


class UserCreate(UserBase):
    """Schema for creating a user (dashboard access).

    Note: No workspace-level permissions for MVP. Users have org-wide access
    based on their role (org_admin or org_viewer).
    """

    role: UserRole = Field(
        default=UserRole.ORG_VIEWER,
        description="User role for dashboard access (org_admin or org_viewer)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom attributes",
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password for dashboard login",
    )


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    display_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    role: UserRole | None = Field(None, description="org_admin or org_viewer")
    metadata: dict[str, Any] | None = None
    is_active: bool | None = None


class UserResponse(BaseSchema):
    """Schema for user response.

    Note: organisation_id is None for SuperAdmins (platform-level users).
    """

    id: str
    organisation_id: str | None  # None for SuperAdmins
    email: str
    display_name: str
    role: UserRole
    is_active: bool
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    """Schema for listing users."""

    users: list[UserResponse]
    pagination: dict[str, int]


class UserAuthResponse(BaseModel):
    """Schema for user authentication response."""

    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for confirming password reset."""

    token: str
    new_password: str = Field(..., min_length=8)


class PasswordChangeRequest(BaseModel):
    """Schema for changing password (when logged in)."""

    current_password: str
    new_password: str = Field(..., min_length=8)
