"""
User Management Endpoints

CRUD operations for user resources.
Users are for DASHBOARD access only - they are NOT used for MCP authentication.
AI agents use AgentAccess keys to authenticate with MCP servers.

MVP Roles:
- super_admin: Platform admin (system administrators)
- org_admin: Full admin for their organisation
- org_viewer: Read-only access to dashboards/logs

Note: No workspace-level user management for MVP. Users have org-wide access
based on their role.
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
from app.control_plane.services.user_service import UserService
from app.core.exceptions import ConflictError
from app.schemas.common import PaginatedResponse, PaginationMeta, PaginationParams
from app.schemas.user import UserCreate, UserResponse, UserUpdate


router = APIRouter()


# =============================================================================
# USER ENDPOINTS
# =============================================================================


@router.get(
    "/organisations/{organisation_id}/users",
    response_model=PaginatedResponse[UserResponse],
    summary="List organisation users",
    description="List all dashboard users for an organisation with pagination.",
)
async def list_users(
    organisation_id: str,
    current_user: CurrentUser,
    db: DbSession,
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginatedResponse[UserResponse]:
    """List users for an organisation.

    Args:
        organisation_id: Organisation UUID
        current_user: Current authenticated user
        db: Database session
        pagination: Pagination parameters

    Returns:
        Paginated list of users

    Raises:
        400: Invalid UUID format
        403: Access denied
    """
    organisation_uuid = validate_uuid(organisation_id, "organisation_id")

    # Check access BEFORE querying
    check_organisation_access(current_user, organisation_id, "list users in")

    service = UserService(db)
    users, total = await service.list_users(
        organisation_id=organisation_uuid,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse[UserResponse](
        data=users,
        pagination=PaginationMeta.create(
            page=pagination.page, per_page=pagination.per_page, total=total
        ),
    )


@router.post(
    "/organisations/{organisation_id}/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="""
Create a new dashboard user in an organisation.

Dashboard users can log in to the admin portal to manage resources.
They are NOT used for MCP agent authentication - use Agent Access for that.

MVP Roles: org_admin (full access) or org_viewer (read-only).
Users have org-wide access based on their role.

**Validation Performed:**
- Organisation access authorization
- Email uniqueness within organisation
""",
)
async def create_user(
    organisation_id: str,
    data: UserCreate,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> UserResponse:
    """Create a new dashboard user.

    Args:
        organisation_id: Organisation UUID
        data: User creation data
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Created user

    Raises:
        400: Validation error (duplicate email, etc.)
        403: Access denied
    """
    organisation_uuid = validate_uuid(organisation_id, "organisation_id")

    # Check access BEFORE creating
    check_organisation_access(current_user, organisation_id, "create users in")

    service = UserService(db)

    try:
        user = await service.create_user(
            organisation_id=organisation_uuid,
            display_name=data.display_name,
            email=data.email,
            password=data.password,
            role=data.role.value if data.role else "org_viewer",
            metadata=data.metadata,
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "code": "VALIDATION_ERROR"},
        ) from e

    return user


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Get user",
    description="Retrieve user details by ID.",
)
async def get_user(
    user_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    """Get user by ID.

    Args:
        user_id: User UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        User details

    Raises:
        400: Invalid UUID format
        403: Access denied (user in different organisation)
        404: User not found
    """
    user_uuid = validate_uuid(user_id, "user_id")

    service = UserService(db)
    user = await service.get_user(user_uuid)

    if not user:
        raise_not_found("User")

    # Check access AFTER getting user (need organisation_id from user)
    check_organisation_access(current_user, user.organisation_id, "access")

    return user


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update user details. Only provided fields will be updated.",
)
async def update_user(
    user_id: str,
    data: UserUpdate,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> UserResponse:
    """Update user.

    Args:
        user_id: User UUID
        data: Update data (all fields optional)
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Updated user

    Raises:
        400: Invalid UUID format or validation error
        403: Access denied (user in different organisation)
        404: User not found
    """
    user_uuid = validate_uuid(user_id, "user_id")

    service = UserService(db)

    # Get user to check organisation BEFORE updating
    user = await service.get_user(user_uuid)
    if not user:
        raise_not_found("User")

    # Check access
    check_organisation_access(current_user, user.organisation_id, "modify users in")

    try:
        updated = await service.update_user(
            user_id=user_uuid,
            **data.model_dump(exclude_unset=True),
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "code": "VALIDATION_ERROR"},
        ) from e

    return updated


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Soft delete a user.",
)
async def delete_user(
    user_id: str,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> None:
    """Delete user (soft delete).

    Args:
        user_id: User UUID
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Raises:
        400: Invalid UUID format
        403: Access denied (user in different organisation)
        404: User not found
    """
    user_uuid = validate_uuid(user_id, "user_id")

    service = UserService(db)

    # Get user to check organisation BEFORE deleting
    user = await service.get_user(user_uuid)
    if not user:
        raise_not_found("User")

    # Check access
    check_organisation_access(current_user, user.organisation_id, "delete users in")

    success = await service.delete_user(user_uuid)
    if not success:
        raise_not_found("User")
