"""
Agent Access Schemas

Request/response models for agent access endpoints.
Agent Access provides authentication for AI agents connecting to MCP servers.

Access Control:
- Agent permissions are controlled entirely by Policies and Guardrails
- No "scopes" field - RBAC guardrail controls tool access
- Rate limiting guardrails control request limits
- PII/Content guardrails control data handling
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


class AgentAccessBase(BaseModel):
    """Base agent access fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: str | None = Field(None, max_length=500)


class AgentAccessCreate(AgentAccessBase):
    """Schema for creating an agent access.

    Note: Agent permissions are controlled by Policies and Guardrails,
    not by scopes on the agent access itself.
    """

    expires_at: datetime | None = Field(
        None,
        description="Expiration date (null = never expires)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata for the agent",
    )


class AgentAccessUpdate(BaseModel):
    """Schema for updating an agent access."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class AgentAccessResponse(BaseSchema):
    """Schema for agent access response (without the key itself)."""

    id: str
    mcp_server_workspace_id: str
    organisation_id: str  # Derived from workspace
    name: str
    description: str | None
    key_prefix: str  # e.g., "za-prod-xxxx"
    is_active: bool
    is_revoked: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    usage_count: int
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class AgentAccessCreatedResponse(BaseModel):
    """Schema for newly created agent access (includes the actual key).

    IMPORTANT: The `key` field is only shown once at creation time.
    Store it securely - it cannot be retrieved again.
    """

    id: str
    key: str  # The actual key - only shown once!
    mcp_server_workspace_id: str
    organisation_id: str
    name: str
    description: str | None = None
    key_prefix: str
    expires_at: datetime | None
    created_at: datetime


class AgentAccessListResponse(BaseModel):
    """Schema for listing agent accesses."""

    agent_accesses: list[AgentAccessResponse]
    pagination: dict[str, int]


class AgentAccessRotateResponse(BaseModel):
    """Schema for agent access key rotation response."""

    new_agent_access: AgentAccessCreatedResponse
    old_access_valid_until: datetime  # Grace period


# Context derived from a validated agent access key (used in gateway dependencies)
class AgentAccessContext(BaseModel):
    """Context derived from a validated agent access key.

    This is what's available after key validation in the gateway.
    All IDs are derived directly from the key and its relationships.

    Note: No scopes - permissions are controlled by Policies and Guardrails.
    """

    agent_access_id: str = Field(..., description="The agent access ID")
    agent_name: str = Field(..., description="Agent name")
    mcp_server_workspace_id: str = Field(..., description="Workspace ID (from key)")
    organisation_id: str = Field(..., description="Organisation ID (from workspace)")
    mcp_server_url: str | None = Field(None, description="MCP server URL (from workspace)")
