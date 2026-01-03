"""
Pydantic Schemas

Request/response models for API endpoints.
"""

from app.schemas.agent_access import (
    AgentAccessContext,
    AgentAccessCreate,
    AgentAccessCreatedResponse,
    AgentAccessListResponse,
    AgentAccessResponse,
    AgentAccessRotateResponse,
    AgentAccessUpdate,
)
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    UserDetails,
)
from app.schemas.common import (
    HealthResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationParams,
)
from app.schemas.decision import (
    DecisionMetadata,
    DecisionRequest,
    DecisionResponse,
    MCPMessage,
)
from app.schemas.guardrail import (
    ContentConfig,
    GuardrailDefinitionCreate,
    GuardrailDefinitionListResponse,
    GuardrailDefinitionResponse,
    GuardrailDefinitionUpdate,
    GuardrailEvent,
    GuardrailPolicyConfig,
    PIIConfig,
    RateLimitConfig,
    RBACConfig,
)
from app.schemas.mcp_server_workspace import (
    McpServerWorkspaceCreate,
    McpServerWorkspaceListResponse,
    McpServerWorkspaceResponse,
    McpServerWorkspaceSettings,
    McpServerWorkspaceUpdate,
)
from app.schemas.organisation import (
    OrganisationCreate,
    OrganisationListResponse,
    OrganisationResponse,
    OrganisationSettings,
    OrganisationUpdate,
)
from app.schemas.policy import (
    EffectivePolicyResponse,
    PolicyBulkCreateRequest,
    PolicyBulkCreateResponse,
    PolicyCreate,
    PolicyListResponse,
    PolicyResponse,
    PolicyUpdate,
)
from app.schemas.user import (
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)

__all__ = [
    # Auth
    "LoginRequest",
    "RefreshRequest",
    "AuthResponse",
    "UserDetails",
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "MessageResponse",
    "HealthResponse",
    # Organisation
    "OrganisationCreate",
    "OrganisationUpdate",
    "OrganisationResponse",
    "OrganisationListResponse",
    "OrganisationSettings",
    # MCP Server Workspace
    "McpServerWorkspaceCreate",
    "McpServerWorkspaceUpdate",
    "McpServerWorkspaceResponse",
    "McpServerWorkspaceListResponse",
    "McpServerWorkspaceSettings",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "PasswordChangeRequest",
    # Agent Access
    "AgentAccessCreate",
    "AgentAccessUpdate",
    "AgentAccessResponse",
    "AgentAccessCreatedResponse",
    "AgentAccessListResponse",
    "AgentAccessRotateResponse",
    "AgentAccessContext",
    # Policy
    "PolicyCreate",
    "PolicyUpdate",
    "PolicyResponse",
    "PolicyListResponse",
    "PolicyBulkCreateRequest",
    "PolicyBulkCreateResponse",
    "EffectivePolicyResponse",
    # Guardrail
    "GuardrailDefinitionCreate",
    "GuardrailDefinitionUpdate",
    "GuardrailDefinitionResponse",
    "GuardrailDefinitionListResponse",
    "GuardrailEvent",
    "GuardrailPolicyConfig",
    "RBACConfig",
    "PIIConfig",
    "ContentConfig",
    "RateLimitConfig",
    # Decision
    "DecisionRequest",
    "DecisionResponse",
    "MCPMessage",
    "DecisionMetadata",
]
