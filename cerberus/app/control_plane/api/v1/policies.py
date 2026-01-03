"""
Policy Management Endpoints

CRUD operations for policy resources.

Policies link guardrails to entities (organisations, workspaces, or agents).
Each policy configures ONE guardrail for ONE entity - no complex merging.

Policy levels are determined by which IDs are set:
- organisation_id only -> Organisation-level policy
- organisation_id + mcp_server_workspace_id -> Workspace-level policy
- organisation_id + mcp_server_workspace_id + agent_access_id -> Agent-level policy
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.control_plane.api.dependencies import (
    CurrentUser,
    DbSession,
    OrganisationAdmin,
)
from app.control_plane.api.utils import (
    check_organisation_access,
    raise_not_found,
    validate_uuid,
)
from app.control_plane.services.mcp_server_workspace_service import (
    McpServerWorkspaceService,
)
from app.control_plane.services.agent_access_service import AgentAccessService
from app.control_plane.services.policy_service import PolicyService
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.schemas.common import PaginatedResponse, PaginationMeta, PaginationParams
from app.schemas.policy import (
    EffectivePolicyResponse,
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
)


router = APIRouter()


# =============================================================================
# POLICY CREATION
# =============================================================================


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a policy",
    description="""
Create a policy that links a guardrail to an entity.

**Policy Levels (determined by which IDs are provided):**
- **Organisation-level**: Only `organisation_id`. Applies to all workspaces/agents.
- **Workspace-level**: `organisation_id` + `mcp_server_workspace_id`. Applies to all agents in workspace.
- **Agent-level**: All three IDs. Applies to specific agent only.

**Example - Organisation-level policy:**
```json
{
    "organisation_id": "550e8400-e29b-41d4-a716-446655440000",
    "guardrail_id": "pii_ssn_guardrail_uuid",
    "name": "Org-wide SSN Detection",
    "action": "redact",
    "config": {"direction": "both", "redaction_pattern": "[SSN REDACTED]"}
}
```

**Example - Agent-level policy:**
```json
{
    "organisation_id": "550e8400-e29b-41d4-a716-446655440000",
    "mcp_server_workspace_id": "660e8400-e29b-41d4-a716-446655440001",
    "agent_access_id": "770e8400-e29b-41d4-a716-446655440002",
    "guardrail_id": "rate_limit_per_minute_guardrail_uuid",
    "name": "Production Agent Rate Limit",
    "action": "block",
    "config": {"limit": 100}
}
```
""",
)
async def create_policy(
    data: PolicyCreate,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> PolicyResponse:
    """Create a new policy.

    Args:
        data: Policy creation data
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Created policy

    Raises:
        400: Validation error (invalid guardrail, config, etc.)
        403: Access denied
        404: Organisation/workspace/agent/guardrail not found
    """
    # Check organisation access
    check_organisation_access(current_user, data.organisation_id, "create policies in")

    service = PolicyService(db)

    try:
        policy = await service.create_policy(data)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except (ValidationError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return policy


# =============================================================================
# LIST ENDPOINTS
# =============================================================================


@router.get(
    "/organisations/{organisation_id}/policies",
    response_model=PaginatedResponse[PolicyResponse],
    summary="List organisation policies",
    description="List organisation-level policies (policies without workspace/agent scope).",
)
async def list_organisation_policies(
    organisation_id: str,
    current_user: CurrentUser,
    db: DbSession,
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginatedResponse[PolicyResponse]:
    """List organisation-level policies.

    Args:
        organisation_id: Organisation UUID
        current_user: Current authenticated user
        db: Database session
        pagination: Pagination parameters

    Returns:
        Paginated list of organisation-level policies

    Raises:
        400: Invalid UUID format
        403: Access denied
    """
    organisation_uuid = validate_uuid(organisation_id, "organisation_id")

    # Check access
    check_organisation_access(current_user, organisation_id, "access policies for")

    service = PolicyService(db)
    policies, total = await service.list_organisation_policies(
        organisation_id=organisation_uuid,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse[PolicyResponse](
        data=policies,
        pagination=PaginationMeta.create(
            page=pagination.page, per_page=pagination.per_page, total=total
        ),
    )


@router.get(
    "/mcp-server-workspaces/{mcp_server_workspace_id}/policies",
    response_model=PaginatedResponse[PolicyResponse],
    summary="List workspace policies",
    description="List workspace-level policies.",
)
async def list_workspace_policies(
    mcp_server_workspace_id: str,
    current_user: CurrentUser,
    db: DbSession,
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginatedResponse[PolicyResponse]:
    """List workspace-level policies.

    Args:
        mcp_server_workspace_id: Workspace UUID
        current_user: Current authenticated user
        db: Database session
        pagination: Pagination parameters

    Returns:
        Paginated list of workspace-level policies

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Workspace not found
    """
    workspace_uuid = validate_uuid(mcp_server_workspace_id, "mcp_server_workspace_id")

    # Get workspace to check organisation access
    workspace_service = McpServerWorkspaceService(db)
    workspace = await workspace_service.get_workspace(workspace_uuid)

    if not workspace:
        raise_not_found("MCP Server Workspace")

    # Check access
    check_organisation_access(
        current_user, workspace.organisation_id, "access policies for"
    )

    service = PolicyService(db)
    policies, total = await service.list_workspace_policies(
        mcp_server_workspace_id=workspace_uuid,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse[PolicyResponse](
        data=policies,
        pagination=PaginationMeta.create(
            page=pagination.page, per_page=pagination.per_page, total=total
        ),
    )


@router.get(
    "/agent-accesses/{agent_access_id}/policies",
    response_model=PaginatedResponse[PolicyResponse],
    summary="List agent policies",
    description="List agent-level policies (policies scoped to a specific agent).",
)
async def list_agent_policies(
    agent_access_id: str,
    current_user: CurrentUser,
    db: DbSession,
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginatedResponse[PolicyResponse]:
    """List agent-level policies.

    Args:
        agent_access_id: Agent access UUID
        current_user: Current authenticated user
        db: Database session
        pagination: Pagination parameters

    Returns:
        Paginated list of agent-level policies

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Agent access not found
    """
    agent_uuid = validate_uuid(agent_access_id, "agent_access_id")

    # Get agent access to check organisation access BEFORE querying policies
    agent_service = AgentAccessService(db)
    agent_access = await agent_service.get_agent_access(agent_uuid)

    if not agent_access:
        raise_not_found("Agent Access")

    # Check organisation access
    check_organisation_access(
        current_user, agent_access.organisation_id, "access policies for"
    )

    service = PolicyService(db)
    policies, total = await service.list_agent_policies(
        agent_access_id=agent_uuid,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse[PolicyResponse](
        data=policies,
        pagination=PaginationMeta.create(
            page=pagination.page, per_page=pagination.per_page, total=total
        ),
    )


# =============================================================================
# SINGLE POLICY OPERATIONS
# =============================================================================


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Get a policy",
    description="Retrieve a policy by its ID.",
)
async def get_policy(
    policy_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> PolicyResponse:
    """Get policy by ID.

    Args:
        policy_id: Policy UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Policy details

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Policy not found
    """
    policy_uuid = validate_uuid(policy_id, "policy_id")

    service = PolicyService(db)
    policy = await service.get_policy(policy_uuid)

    if not policy:
        raise_not_found("Policy")

    # Check organisation access
    check_organisation_access(current_user, policy.organisation_id, "access")

    return policy


@router.put(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Update a policy",
    description="""
Update an existing policy.

**Updatable fields:**
- `name`: Policy display name
- `config`: Guardrail-specific configuration
- `action`: Policy action (block, redact, alert, audit_only)
- `is_enabled`: Whether the policy is active
""",
)
async def update_policy(
    policy_id: str,
    data: PolicyUpdate,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> PolicyResponse:
    """Update policy.

    Args:
        policy_id: Policy UUID
        data: Update data
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Updated policy

    Raises:
        400: Validation error
        403: Access denied
        404: Policy not found
    """
    policy_uuid = validate_uuid(policy_id, "policy_id")

    service = PolicyService(db)

    # Get policy to check organisation access BEFORE updating
    existing = await service.get_policy(policy_uuid)
    if not existing:
        raise_not_found("Policy")

    # Check access
    check_organisation_access(current_user, existing.organisation_id, "modify")

    try:
        policy = await service.update_policy(policy_uuid, data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    if not policy:
        raise_not_found("Policy")

    return policy


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a policy",
    description="Soft delete a policy.",
)
async def delete_policy(
    policy_id: str,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> None:
    """Delete policy (soft delete).

    Args:
        policy_id: Policy UUID
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Policy not found
    """
    policy_uuid = validate_uuid(policy_id, "policy_id")

    service = PolicyService(db)

    # Get policy to check organisation access BEFORE deleting
    existing = await service.get_policy(policy_uuid)
    if not existing:
        raise_not_found("Policy")

    # Check access
    check_organisation_access(current_user, existing.organisation_id, "delete")

    success = await service.delete_policy(policy_uuid)
    if not success:
        raise_not_found("Policy")


# =============================================================================
# EFFECTIVE POLICIES
# =============================================================================


@router.get(
    "/mcp-server-workspaces/{mcp_server_workspace_id}/effective-policies",
    response_model=EffectivePolicyResponse,
    summary="Get effective policies",
    description="""
Get all applicable policies for a workspace/agent.

Returns policies from all levels that apply:
- Organisation-level policies
- Workspace-level policies
- Agent-level policies (if agent_access_id provided)

**Note:** Unlike the old system, policies are NOT merged. Each policy is
independent and evaluated separately. The response contains all applicable
policies that the governance engine will evaluate.
""",
)
async def get_effective_policies(
    mcp_server_workspace_id: str,
    current_user: CurrentUser,
    db: DbSession,
    agent_access_id: str | None = None,
) -> EffectivePolicyResponse:
    """Get all effective policies for a workspace/agent.

    Args:
        mcp_server_workspace_id: Workspace UUID
        current_user: Current authenticated user
        db: Database session
        agent_access_id: Optional agent access UUID

    Returns:
        All applicable policies

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Workspace not found
    """
    workspace_uuid = validate_uuid(mcp_server_workspace_id, "mcp_server_workspace_id")

    agent_uuid = None
    if agent_access_id:
        agent_uuid = validate_uuid(agent_access_id, "agent_access_id")

    # Get workspace to check organisation access
    workspace_service = McpServerWorkspaceService(db)
    workspace = await workspace_service.get_workspace(workspace_uuid)

    if not workspace:
        raise_not_found("MCP Server Workspace")

    # Check access
    check_organisation_access(
        current_user, workspace.organisation_id, "access policies for"
    )

    service = PolicyService(db)
    effective = await service.get_effective_policies(
        organisation_id=validate_uuid(workspace.organisation_id, "organisation_id"),
        mcp_server_workspace_id=workspace_uuid,
        agent_access_id=agent_uuid,
    )

    return effective
