"""
MCP Server Workspace Schemas

Request/response models for MCP server workspace endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.config.constants import EnvironmentType, FailMode, LogLevel
from app.schemas.common import BaseSchema


class McpServerWorkspaceSettings(BaseModel):
    """MCP Server Workspace settings configuration."""

    fail_mode: FailMode | None = Field(
        None,
        description="Override organisation's fail mode (null to inherit)",
    )
    decision_timeout_ms: int = Field(
        default=5000,
        ge=100,
        le=30000,
        description="Maximum time to wait for decision",
    )
    log_level: LogLevel = Field(
        default=LogLevel.STANDARD,
        description="Audit log verbosity",
    )


class McpServerWorkspaceBase(BaseModel):
    """Base MCP server workspace fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")
    description: str | None = Field(None, max_length=1000)
    environment_type: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        description="Environment type",
    )


class McpServerWorkspaceCreate(McpServerWorkspaceBase):
    """Schema for creating an MCP server workspace."""

    mcp_server_url: str | None = Field(
        None,
        description="URL of the MCP server to proxy to",
    )
    settings: McpServerWorkspaceSettings = Field(default_factory=McpServerWorkspaceSettings)


class McpServerWorkspaceUpdate(BaseModel):
    """Schema for updating an MCP server workspace."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    environment_type: EnvironmentType | None = None
    mcp_server_url: str | None = None
    settings: McpServerWorkspaceSettings | None = None
    is_active: bool | None = None


class McpServerWorkspaceResponse(BaseSchema):
    """Schema for MCP server workspace response."""

    id: str
    organisation_id: str
    name: str
    slug: str
    description: str | None
    environment_type: EnvironmentType
    mcp_server_url: str | None
    settings: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    policy_count: int = 0
    agent_access_count: int = 0


class McpServerWorkspaceListResponse(BaseModel):
    """Schema for listing MCP server workspaces."""

    mcp_server_workspaces: list[McpServerWorkspaceResponse]
    pagination: dict[str, int]
