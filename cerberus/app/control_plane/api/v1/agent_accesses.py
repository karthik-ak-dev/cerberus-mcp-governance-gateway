"""
Agent Access Management Endpoints

CRUD operations for agent access keys.
Agent access keys are used by AI agents to authenticate with MCP servers through Cerberus Gateway.
These are NOT tied to dashboard users - agents are standalone entities scoped to workspaces.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.control_plane.api.dependencies import DbSession, OrganisationAdmin
from app.control_plane.api.utils import (
    check_organisation_access,
    raise_not_found,
    validate_uuid,
)
from app.control_plane.services.agent_access_service import AgentAccessService
from app.control_plane.services.mcp_server_workspace_service import (
    McpServerWorkspaceService,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.agent_access import (
    AgentAccessCreate,
    AgentAccessCreatedResponse,
    AgentAccessResponse,
    AgentAccessRotateResponse,
    AgentAccessUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationMeta, PaginationParams


router = APIRouter()


# =============================================================================
# AGENT ACCESS ENDPOINTS
# =============================================================================


@router.get(
    "/mcp-server-workspaces/{mcp_server_workspace_id}/agent-accesses",
    response_model=PaginatedResponse[AgentAccessResponse],
    summary="List workspace agent accesses",
    description="List all agent access keys for an MCP server workspace.",
)
async def list_agent_accesses(
    mcp_server_workspace_id: str,
    current_user: OrganisationAdmin,
    db: DbSession,
    pagination: Annotated[PaginationParams, Depends()],
    include_revoked: bool = Query(
        False, description="Include revoked keys in results"
    ),
) -> PaginatedResponse[AgentAccessResponse]:
    """List agent access keys for an MCP server workspace.

    Args:
        mcp_server_workspace_id: Workspace UUID
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session
        pagination: Pagination parameters
        include_revoked: Include revoked keys

    Returns:
        Paginated list of agent accesses

    Raises:
        400: Invalid UUID format
        403: Access denied to workspace
        404: Workspace not found
    """
    workspace_uuid = validate_uuid(mcp_server_workspace_id, "mcp_server_workspace_id")

    # Get workspace to check organisation access
    workspace_service = McpServerWorkspaceService(db)
    workspace = await workspace_service.get_workspace(workspace_uuid)

    if not workspace:
        raise_not_found("MCP Server Workspace")

    # Check organisation access BEFORE querying
    check_organisation_access(
        current_user, workspace.organisation_id, "list agent accesses for"
    )

    service = AgentAccessService(db)
    keys, total = await service.list_agent_accesses_by_workspace(
        mcp_server_workspace_id=workspace_uuid,
        offset=pagination.offset,
        limit=pagination.limit,
        include_revoked=include_revoked,
    )

    return PaginatedResponse[AgentAccessResponse](
        data=keys,
        pagination=PaginationMeta.create(
            page=pagination.page, per_page=pagination.per_page, total=total
        ),
    )


@router.post(
    "/mcp-server-workspaces/{mcp_server_workspace_id}/agent-accesses",
    response_model=AgentAccessCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create agent access",
    description="""
Create a new agent access key for an MCP server workspace.

**Important:** The actual key value is only returned once in this response.
Store it securely as it cannot be retrieved again.

Agent access keys are used by AI agents (like Claude, GPT, etc.) to authenticate
with MCP servers through Cerberus Gateway. They are NOT tied to dashboard users.
""",
)
async def create_agent_access(
    mcp_server_workspace_id: str,
    data: AgentAccessCreate,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> AgentAccessCreatedResponse:
    """Create a new agent access key.

    Args:
        mcp_server_workspace_id: Workspace UUID
        data: Agent access creation data
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Created agent access with the actual key value

    Raises:
        400: Validation error
        403: Access denied
        404: Workspace not found
    """
    workspace_uuid = validate_uuid(mcp_server_workspace_id, "mcp_server_workspace_id")

    # Get workspace to check organisation access
    workspace_service = McpServerWorkspaceService(db)
    workspace = await workspace_service.get_workspace(workspace_uuid)

    if not workspace:
        raise_not_found("MCP Server Workspace")

    # Check organisation access BEFORE creating key
    check_organisation_access(
        current_user, workspace.organisation_id, "create agent access in"
    )

    service = AgentAccessService(db)

    try:
        result = await service.create_agent_access(
            mcp_server_workspace_id=workspace_uuid,
            name=data.name,
            description=data.description,
            expires_at=data.expires_at,
            metadata=data.metadata,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()["error"],
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()["error"],
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "code": "VALIDATION_ERROR"},
        ) from e

    return result


@router.get(
    "/agent-accesses/{agent_access_id}",
    response_model=AgentAccessResponse,
    summary="Get agent access",
    description="Retrieve agent access details by ID. The actual key value is not returned.",
)
async def get_agent_access(
    agent_access_id: str,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> AgentAccessResponse:
    """Get agent access by ID.

    Args:
        agent_access_id: Agent access UUID
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Agent access details (without the actual key)

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Agent access not found
    """
    access_uuid = validate_uuid(agent_access_id, "agent_access_id")

    service = AgentAccessService(db)
    access = await service.get_agent_access(access_uuid)

    if not access:
        raise_not_found("Agent access")

    # Check organisation access
    check_organisation_access(current_user, access.organisation_id, "access")

    return access


@router.put(
    "/agent-accesses/{agent_access_id}",
    response_model=AgentAccessResponse,
    summary="Update agent access",
    description="Update agent access details.",
)
async def update_agent_access(
    agent_access_id: str,
    data: AgentAccessUpdate,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> AgentAccessResponse:
    """Update agent access.

    Args:
        agent_access_id: Agent access UUID
        data: Update data
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Updated agent access

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Agent access not found
    """
    access_uuid = validate_uuid(agent_access_id, "agent_access_id")

    service = AgentAccessService(db)

    # Get access to check organisation BEFORE updating
    access = await service.get_agent_access(access_uuid)
    if not access:
        raise_not_found("Agent access")

    # Check organisation access
    check_organisation_access(current_user, access.organisation_id, "modify")

    updated = await service.update_agent_access(
        agent_access_id=access_uuid,
        **data.model_dump(exclude_unset=True),
    )

    if not updated:
        raise_not_found("Agent access")

    return updated


@router.delete(
    "/agent-accesses/{agent_access_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke agent access",
    description="Revoke an agent access key. The key will be immediately invalidated.",
)
async def revoke_agent_access(
    agent_access_id: str,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> None:
    """Revoke an agent access key.

    Args:
        agent_access_id: Agent access UUID
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Agent access not found
    """
    access_uuid = validate_uuid(agent_access_id, "agent_access_id")

    service = AgentAccessService(db)

    # Get access to check organisation BEFORE revoking
    access = await service.get_agent_access(access_uuid)
    if not access:
        raise_not_found("Agent access")

    # Check organisation access
    check_organisation_access(current_user, access.organisation_id, "revoke")

    success = await service.revoke_agent_access(access_uuid)
    if not success:
        raise_not_found("Agent access")


@router.post(
    "/agent-accesses/{agent_access_id}/rotate",
    response_model=AgentAccessRotateResponse,
    summary="Rotate agent access key",
    description="""
Rotate an agent access key. Creates a new key and sets a grace period for the old key.

The old key will remain valid for a short grace period to allow for seamless key rotation.
""",
)
async def rotate_agent_access(
    agent_access_id: str,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> AgentAccessRotateResponse:
    """Rotate an agent access key.

    Args:
        agent_access_id: Agent access UUID
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        New agent access key and old key expiration

    Raises:
        400: Invalid UUID or key already revoked
        403: Access denied
        404: Agent access not found
    """
    access_uuid = validate_uuid(agent_access_id, "agent_access_id")

    service = AgentAccessService(db)

    # Get access to check organisation BEFORE rotating
    access = await service.get_agent_access(access_uuid)
    if not access:
        raise_not_found("Agent access")

    # Check organisation access
    check_organisation_access(current_user, access.organisation_id, "rotate")

    try:
        result = await service.rotate_agent_access(access_uuid)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()["error"],
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()["error"],
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "code": "VALIDATION_ERROR"},
        ) from e

    return result
