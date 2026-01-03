"""
Policy Schemas (Simplified)

Request/response models for policy endpoints.

A Policy links ONE guardrail to ONE entity (Organisation, Workspace, or Agent).
Each policy configures a specific guardrail with a specific action.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.config.constants import PolicyAction, PolicyLevel
from app.schemas.common import BaseSchema


class PolicyBase(BaseModel):
    """Base policy fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Policy name")
    description: str | None = Field(None, max_length=1000)


class PolicyCreate(PolicyBase):
    """Schema for creating a policy.

    The policy level is determined by which IDs are provided:
    - organisation_id only → Organisation-level policy
    - organisation_id + mcp_server_workspace_id → Workspace-level policy
    - organisation_id + mcp_server_workspace_id + agent_access_id → Agent-level policy

    Example payloads:

        # Organisation-level policy (block SSN across entire org)
        {
            "organisation_id": "uuid",
            "name": "Block SSN Org-wide",
            "guardrail_id": "pii_ssn_guardrail_uuid",
            "action": "block",
            "config": {"direction": "both"}
        }

        # Workspace-level policy (rate limit for production)
        {
            "organisation_id": "uuid",
            "mcp_server_workspace_id": "uuid",
            "name": "Production Rate Limit",
            "guardrail_id": "rate_limit_guardrail_uuid",
            "action": "block",
            "config": {"limit": 30}
        }

        # Agent-level policy (RBAC for specific agent)
        {
            "organisation_id": "uuid",
            "mcp_server_workspace_id": "uuid",
            "agent_access_id": "uuid",
            "name": "Claude Agent RBAC",
            "guardrail_id": "rbac_guardrail_uuid",
            "action": "block",
            "config": {"allowed_tools": ["filesystem/*", "git/*"]}
        }
    """

    # Required organisation scope
    organisation_id: str = Field(..., description="Organisation UUID")

    # Optional scope fields for workspace/agent level
    mcp_server_workspace_id: str | None = Field(
        None,
        description="Workspace UUID. If omitted, creates org-level policy.",
    )
    agent_access_id: str | None = Field(
        None,
        description="Agent access UUID. Requires mcp_server_workspace_id.",
    )

    # Guardrail reference (by ID, not type)
    guardrail_id: str = Field(..., description="Guardrail UUID to attach")

    # Policy configuration
    action: PolicyAction = Field(
        default=PolicyAction.BLOCK,
        description="Action to take when guardrail triggers",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Guardrail-specific configuration overrides",
    )
    is_enabled: bool = Field(default=True, description="Whether policy is active")

    @model_validator(mode="after")
    def validate_policy_level(self) -> "PolicyCreate":
        """Validate that agent_access_id requires mcp_server_workspace_id."""
        if self.agent_access_id and not self.mcp_server_workspace_id:
            raise ValueError(
                "agent_access_id requires mcp_server_workspace_id. "
                "Agent-level policies must be scoped to a workspace."
            )
        return self

    @property
    def level(self) -> PolicyLevel:
        """Determine the policy level based on provided IDs."""
        if self.agent_access_id:
            return PolicyLevel.AGENT
        if self.mcp_server_workspace_id:
            return PolicyLevel.WORKSPACE
        return PolicyLevel.ORGANISATION


class PolicyUpdate(BaseModel):
    """Schema for updating a policy."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    action: PolicyAction | None = None
    config: dict[str, Any] | None = None
    is_enabled: bool | None = None


class PolicyResponse(BaseSchema):
    """Schema for policy response."""

    id: str
    organisation_id: str
    mcp_server_workspace_id: str | None
    agent_access_id: str | None
    guardrail_id: str
    guardrail_type: str  # Guardrail type string from guardrail relationship
    guardrail_display_name: str  # Display name from guardrail relationship
    name: str
    description: str | None
    action: PolicyAction
    config: dict[str, Any]
    is_enabled: bool
    level: PolicyLevel  # organisation, workspace, or agent
    created_at: datetime
    updated_at: datetime


class PolicyListResponse(BaseModel):
    """Schema for listing policies."""

    policies: list[PolicyResponse]
    pagination: dict[str, int]


class PolicyBulkCreateRequest(BaseModel):
    """Schema for bulk creating policies (attach multiple guardrails at once)."""

    policies: list[PolicyCreate] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of policies to create (max 50)",
    )


class PolicyBulkCreateResponse(BaseModel):
    """Schema for bulk policy creation response."""

    created: list[PolicyResponse]
    errors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Any errors that occurred during creation",
    )


# =============================================================================
# EFFECTIVE POLICY (computed view)
# =============================================================================


class EffectivePolicyResponse(BaseModel):
    """Schema for computed effective policies for an agent.

    This shows all policies that apply to a specific agent,
    including org-level, workspace-level, and agent-level policies.
    """

    organisation_id: str
    mcp_server_workspace_id: str
    agent_access_id: str | None  # None if not querying for specific agent
    policies: list[PolicyResponse]  # All applicable policies
    computed_at: datetime
