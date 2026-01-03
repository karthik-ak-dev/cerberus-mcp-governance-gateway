"""
MCP Server Workspace Management Endpoints

CRUD operations for MCP server workspace resources.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

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
from app.core.utils import slugify
from app.schemas.common import PaginatedResponse, PaginationMeta, PaginationParams
from app.schemas.mcp_server_workspace import (
    McpServerWorkspaceCreate,
    McpServerWorkspaceResponse,
    McpServerWorkspaceUpdate,
)


router = APIRouter()


# =============================================================================
# MCP SERVER WORKSPACE ENDPOINTS
# =============================================================================


@router.get(
    "/organisations/{organisation_id}/mcp-server-workspaces",
    response_model=PaginatedResponse[McpServerWorkspaceResponse],
    summary="List organisation workspaces",
    description="List all MCP server workspaces for an organisation with pagination.",
)
async def list_workspaces(
    organisation_id: str,
    current_user: CurrentUser,
    db: DbSession,
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginatedResponse[McpServerWorkspaceResponse]:
    """List MCP server workspaces for an organisation.

    Args:
        organisation_id: Organisation UUID
        current_user: Current authenticated user
        db: Database session
        pagination: Pagination parameters

    Returns:
        Paginated list of workspaces

    Raises:
        400: Invalid UUID format
        403: Access denied
    """
    organisation_uuid = validate_uuid(organisation_id, "organisation_id")

    # Check access BEFORE querying
    check_organisation_access(current_user, organisation_id, "list workspaces in")

    service = McpServerWorkspaceService(db)
    workspaces, total = await service.list_workspaces(
        organisation_id=organisation_uuid,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse[McpServerWorkspaceResponse](
        data=workspaces,
        pagination=PaginationMeta.create(
            page=pagination.page, per_page=pagination.per_page, total=total
        ),
    )


@router.post(
    "/organisations/{organisation_id}/mcp-server-workspaces",
    response_model=McpServerWorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workspace",
    description="Create a new MCP server workspace in an organisation.",
)
async def create_workspace(
    organisation_id: str,
    data: McpServerWorkspaceCreate,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> McpServerWorkspaceResponse:
    """Create a new MCP server workspace.

    Args:
        organisation_id: Organisation UUID
        data: Workspace creation data
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Created workspace

    Raises:
        400: Invalid UUID format
        403: Access denied
    """
    organisation_uuid = validate_uuid(organisation_id, "organisation_id")

    # Check access BEFORE creating
    check_organisation_access(current_user, organisation_id, "create workspaces in")

    service = McpServerWorkspaceService(db)

    workspace = await service.create_workspace(
        organisation_id=organisation_uuid,
        name=data.name,
        slug=slugify(data.name),
        description=data.description,
        environment_type=data.environment_type,
        mcp_server_url=data.mcp_server_url,
        settings=data.settings.model_dump() if data.settings else {},
    )

    return workspace


@router.get(
    "/mcp-server-workspaces/{mcp_server_workspace_id}",
    response_model=McpServerWorkspaceResponse,
    summary="Get workspace",
    description="Retrieve MCP server workspace details by ID.",
)
async def get_workspace(
    mcp_server_workspace_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> McpServerWorkspaceResponse:
    """Get MCP server workspace by ID.

    Args:
        mcp_server_workspace_id: Workspace UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Workspace details

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Workspace not found or deleted
    """
    workspace_uuid = validate_uuid(mcp_server_workspace_id, "mcp_server_workspace_id")

    service = McpServerWorkspaceService(db)
    workspace = await service.get_workspace(workspace_uuid)

    if not workspace:
        raise_not_found("MCP Server Workspace")

    # Check access AFTER getting workspace (need organisation_id from workspace)
    check_organisation_access(current_user, workspace.organisation_id, "access")

    return workspace


@router.put(
    "/mcp-server-workspaces/{mcp_server_workspace_id}",
    response_model=McpServerWorkspaceResponse,
    summary="Update workspace",
    description="Update MCP server workspace details. Only provided fields will be updated.",
)
async def update_workspace(
    mcp_server_workspace_id: str,
    data: McpServerWorkspaceUpdate,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> McpServerWorkspaceResponse:
    """Update MCP server workspace.

    Args:
        mcp_server_workspace_id: Workspace UUID
        data: Update data (all fields optional)
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Updated workspace

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Workspace not found or deleted
    """
    workspace_uuid = validate_uuid(mcp_server_workspace_id, "mcp_server_workspace_id")

    service = McpServerWorkspaceService(db)

    # Get workspace to check organisation BEFORE updating
    workspace = await service.get_workspace(workspace_uuid)
    if not workspace:
        raise_not_found("MCP Server Workspace")

    # Check access
    check_organisation_access(
        current_user, workspace.organisation_id, "modify workspaces in"
    )

    updated = await service.update_workspace(
        workspace_id=workspace_uuid,
        **data.model_dump(exclude_unset=True),
    )

    return updated


@router.delete(
    "/mcp-server-workspaces/{mcp_server_workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace",
    description="Soft delete an MCP server workspace.",
)
async def delete_workspace(
    mcp_server_workspace_id: str,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> None:
    """Delete MCP server workspace (soft delete).

    Args:
        mcp_server_workspace_id: Workspace UUID
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Workspace not found
    """
    workspace_uuid = validate_uuid(mcp_server_workspace_id, "mcp_server_workspace_id")

    service = McpServerWorkspaceService(db)

    # Get workspace to check organisation BEFORE deleting
    workspace = await service.get_workspace(workspace_uuid)
    if not workspace:
        raise_not_found("MCP Server Workspace")

    # Check access
    check_organisation_access(
        current_user, workspace.organisation_id, "delete workspaces in"
    )

    success = await service.delete_workspace(workspace_uuid)
    if not success:
        raise_not_found("MCP Server Workspace")
