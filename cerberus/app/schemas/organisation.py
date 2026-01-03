"""
Organisation Schemas

Request/response models for organisation endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.config.constants import FailMode, GuardrailType, SubscriptionTier
from app.schemas.common import BaseSchema


class OrganisationSettings(BaseModel):
    """Organisation settings configuration.

    Note: These settings are derived from the subscription tier.
    They are stored in the database but initially populated from TIER_DEFAULTS.
    """

    default_fail_mode: FailMode = Field(
        default=FailMode.CLOSED,
        description="Default gateway behavior when governance service is unreachable",
    )
    max_mcp_server_workspaces: int = Field(
        default=10,
        ge=1,
        description="Maximum MCP server workspaces allowed",
    )
    max_users: int = Field(default=50, ge=1, description="Maximum dashboard users allowed")
    max_agent_accesses_per_workspace: int = Field(
        default=100,
        ge=1,
        description="Maximum agent accesses per workspace",
    )
    data_retention_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Audit log retention period in days",
    )
    allowed_guardrails: list[str] = Field(
        default_factory=lambda: [g.value for g in GuardrailType],
        description="Guardrails available for this organisation",
    )


class OrganisationBase(BaseModel):
    """Base organisation fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Organisation name")
    description: str | None = Field(None, max_length=1000)


class OrganisationCreate(OrganisationBase):
    """Schema for creating an organisation.

    Settings (max_workspaces, max_users, data_retention_days, allowed_guardrails)
    are automatically derived from the subscription_tier via get_tier_defaults().
    """

    subscription_tier: SubscriptionTier = Field(
        default=SubscriptionTier.DEFAULT,
        description="Subscription tier - determines all organisation settings",
    )
    admin_email: str = Field(
        ...,
        description="Email for the initial admin user (required)",
    )


class OrganisationUpdate(BaseModel):
    """Schema for updating an organisation."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    subscription_tier: SubscriptionTier | None = Field(
        None,
        description="Subscription tier - updating this will update all settings",
    )
    is_active: bool | None = None


class OrganisationResponse(BaseSchema):
    """Schema for organisation response."""

    id: str
    name: str
    slug: str
    description: str | None
    subscription_tier: SubscriptionTier
    settings: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    workspace_count: int = 0
    user_count: int = 0


class OrganisationListResponse(BaseModel):
    """Schema for listing organisations."""

    organisations: list[OrganisationResponse]
    pagination: dict[str, int]
