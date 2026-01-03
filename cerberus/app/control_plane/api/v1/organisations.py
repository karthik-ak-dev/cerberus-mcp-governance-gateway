"""
Organisation Management Endpoints

CRUD operations for organisation resources.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.control_plane.api.dependencies import (
    CurrentUser,
    DbSession,
    OrganisationAdmin,
    SuperAdmin,
)
from app.control_plane.api.utils import (
    check_organisation_access,
    raise_not_found,
    validate_uuid,
)
from app.control_plane.services.organisation_service import OrganisationService
from app.core.utils import slugify
from app.schemas.common import PaginatedResponse, PaginationMeta, PaginationParams
from app.schemas.organisation import (
    OrganisationCreate,
    OrganisationResponse,
    OrganisationUpdate,
)


router = APIRouter()


# =============================================================================
# ORGANISATION ENDPOINTS
# =============================================================================


@router.get(
    "",
    response_model=PaginatedResponse[OrganisationResponse],
    summary="List organisations",
    description="List all organisations with pagination. Super admin only.",
)
async def list_organisations(
    _current_user: SuperAdmin,
    db: DbSession,
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginatedResponse[OrganisationResponse]:
    """List all organisations (super admin only).

    Args:
        _current_user: Current authenticated user (must be SuperAdmin)
        db: Database session
        pagination: Pagination parameters

    Returns:
        Paginated list of organisations
    """
    service = OrganisationService(db)
    organisations, total = await service.list_organisations(
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse[OrganisationResponse](
        data=organisations,
        pagination=PaginationMeta.create(
            page=pagination.page, per_page=pagination.per_page, total=total
        ),
    )


@router.post(
    "",
    response_model=OrganisationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organisation",
    description="Create a new organisation. Super admin only.",
)
async def create_organisation(
    data: OrganisationCreate,
    _current_user: SuperAdmin,
    db: DbSession,
) -> OrganisationResponse:
    """Create a new organisation (super admin only).

    Settings (max_workspaces, max_users, data_retention_days, allowed_guardrails)
    are automatically derived from the subscription_tier.

    Args:
        data: Organisation creation data
        _current_user: Current authenticated user (must be SuperAdmin)
        db: Database session

    Returns:
        Created organisation
    """
    service = OrganisationService(db)

    organisation = await service.create_organisation(
        name=data.name,
        slug=slugify(data.name),
        description=data.description,
        subscription_tier=data.subscription_tier,
        admin_email=data.admin_email,
    )

    return organisation


@router.get(
    "/{organisation_id}",
    response_model=OrganisationResponse,
    summary="Get organisation",
    description="Retrieve organisation details by ID.",
)
async def get_organisation(
    organisation_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> OrganisationResponse:
    """Get organisation by ID.

    Args:
        organisation_id: Organisation UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Organisation details

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Organisation not found
    """
    organisation_uuid = validate_uuid(organisation_id, "organisation_id")

    # Check access BEFORE querying
    check_organisation_access(current_user, organisation_id, "access")

    service = OrganisationService(db)
    organisation = await service.get_organisation(organisation_uuid)

    if not organisation:
        raise_not_found("Organisation")

    return organisation


@router.put(
    "/{organisation_id}",
    response_model=OrganisationResponse,
    summary="Update organisation",
    description="Update organisation details. Only provided fields will be updated.",
)
async def update_organisation(
    organisation_id: str,
    data: OrganisationUpdate,
    current_user: OrganisationAdmin,
    db: DbSession,
) -> OrganisationResponse:
    """Update organisation.

    Note: Settings are derived from subscription_tier and cannot be changed directly.
    To change settings, update the subscription_tier.

    Args:
        organisation_id: Organisation UUID
        data: Update data
        current_user: Current authenticated user (must be OrganisationAdmin+)
        db: Database session

    Returns:
        Updated organisation

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Organisation not found
    """
    organisation_uuid = validate_uuid(organisation_id, "organisation_id")

    # Check access BEFORE updating
    check_organisation_access(current_user, organisation_id, "modify")

    service = OrganisationService(db)
    organisation = await service.update_organisation(
        organisation_id=organisation_uuid,
        name=data.name,
        description=data.description,
        subscription_tier=data.subscription_tier,
        is_active=data.is_active,
    )

    if not organisation:
        raise_not_found("Organisation")

    return organisation


@router.delete(
    "/{organisation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete organisation",
    description="Soft delete an organisation. Super admin only.",
)
async def delete_organisation(
    organisation_id: str,
    _current_user: SuperAdmin,
    db: DbSession,
) -> None:
    """Delete organisation (soft delete, super admin only).

    Args:
        organisation_id: Organisation UUID
        _current_user: Current authenticated user (must be SuperAdmin)
        db: Database session

    Raises:
        400: Invalid UUID format
        404: Organisation not found
    """
    organisation_uuid = validate_uuid(organisation_id, "organisation_id")

    service = OrganisationService(db)
    success = await service.delete_organisation(organisation_uuid)

    if not success:
        raise_not_found("Organisation")
