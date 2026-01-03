"""
Auth Schemas

Request/response models for authentication endpoints.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.config.constants import UserRole


class LoginRequest(BaseModel):
    """Login request schema.

    For regular users: organisation_slug is required.
    For SuperAdmins: organisation_slug should be omitted (they don't belong to an organisation).
    """

    email: EmailStr
    password: str
    organisation_slug: Optional[str] = None


class RefreshRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Token-only response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserDetails(BaseModel):
    """User details included in auth responses."""

    id: str
    email: Optional[str]
    display_name: str
    role: UserRole
    organisation_id: Optional[str] = Field(
        None, description="Organisation ID (None for SuperAdmins)"
    )
    organisation_slug: Optional[str] = Field(
        None, description="Organisation slug (None for SuperAdmins)"
    )


class AuthResponse(BaseModel):
    """Authentication response with tokens and user details."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserDetails
