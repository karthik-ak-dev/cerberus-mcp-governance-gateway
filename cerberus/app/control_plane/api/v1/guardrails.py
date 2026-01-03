"""
Guardrail Definition Management Endpoints

CRUD operations for guardrail definitions.
Guardrails are atomic security checks that can be attached to entities via policies.

Note: These endpoints manage the guardrail definitions themselves (admin only).
Policies are used to attach guardrails to organisations/workspaces/agents.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.control_plane.api.dependencies import CurrentUser, DbSession, SuperAdmin
from app.control_plane.api.utils import raise_not_found, validate_uuid
from app.config.constants import GuardrailCategory
from app.control_plane.services.guardrail_service import GuardrailService
from app.core.exceptions import ConflictError, ValidationError
from app.schemas.common import PaginatedResponse, PaginationMeta, PaginationParams
from app.schemas.guardrail import (
    GuardrailDefinitionCreate,
    GuardrailDefinitionResponse,
    GuardrailDefinitionUpdate,
)


router = APIRouter()


# =============================================================================
# GUARDRAIL DEFINITION ENDPOINTS
# =============================================================================


@router.get(
    "",
    response_model=PaginatedResponse[GuardrailDefinitionResponse],
    summary="List guardrail definitions",
    description="""
List all available guardrail definitions with pagination.

Guardrail definitions describe the available security checks that can be
attached to organisations, workspaces, or agents via policies.

**Categories:**
- `rbac`: Role-based access control for tools/resources
- `pii`: PII detection and redaction (SSN, email, phone, etc.)
- `content`: Content filtering (large documents, structured data)
- `rate_limit`: Rate limiting (per minute, per hour)
""",
)
async def list_guardrails(
    _current_user: CurrentUser,
    db: DbSession,
    pagination: Annotated[PaginationParams, Depends()],
    category: GuardrailCategory | None = Query(
        None, description="Filter by guardrail category"
    ),
    active_only: bool = Query(True, description="Only return active guardrails"),
) -> PaginatedResponse[GuardrailDefinitionResponse]:
    """List guardrail definitions.

    Args:
        _current_user: Current authenticated user
        db: Database session
        pagination: Pagination parameters
        category: Optional category filter
        active_only: Only return active guardrails

    Returns:
        Paginated list of guardrail definitions
    """
    service = GuardrailService(db)

    if category:
        guardrails, total = await service.list_by_category(
            category=category,
            only_active=active_only,
        )
    else:
        guardrails, total = await service.list_guardrails(
            offset=pagination.offset,
            limit=pagination.limit,
        )

    return PaginatedResponse[GuardrailDefinitionResponse](
        data=guardrails,
        pagination=PaginationMeta.create(
            page=pagination.page, per_page=pagination.per_page, total=total
        ),
    )


@router.get(
    "/{guardrail_id}",
    response_model=GuardrailDefinitionResponse,
    summary="Get guardrail definition",
    description="Retrieve a guardrail definition by ID.",
)
async def get_guardrail(
    guardrail_id: str,
    _current_user: CurrentUser,
    db: DbSession,
) -> GuardrailDefinitionResponse:
    """Get guardrail definition by ID.

    Args:
        guardrail_id: Guardrail UUID
        _current_user: Current authenticated user
        db: Database session

    Returns:
        Guardrail definition details

    Raises:
        400: Invalid UUID format
        404: Guardrail not found
    """
    guardrail_uuid = validate_uuid(guardrail_id, "guardrail_id")

    service = GuardrailService(db)
    guardrail = await service.get_guardrail(guardrail_uuid)

    if not guardrail:
        raise_not_found("Guardrail")

    return guardrail


@router.post(
    "",
    response_model=GuardrailDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create guardrail definition",
    description="""
Create a new guardrail definition. Super admin only.

**Note:** This creates the guardrail type definition. To apply a guardrail
to an entity, create a policy that links the guardrail to the entity.
""",
)
async def create_guardrail(
    data: GuardrailDefinitionCreate,
    _current_user: SuperAdmin,
    db: DbSession,
) -> GuardrailDefinitionResponse:
    """Create a new guardrail definition (super admin only).

    Args:
        data: Guardrail creation data
        _current_user: Current authenticated user (must be SuperAdmin)
        db: Database session

    Returns:
        Created guardrail definition

    Raises:
        400: Validation error
        409: Guardrail type already exists
    """
    service = GuardrailService(db)

    try:
        guardrail = await service.create_guardrail(data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return guardrail


@router.put(
    "/{guardrail_id}",
    response_model=GuardrailDefinitionResponse,
    summary="Update guardrail definition",
    description="Update a guardrail definition. Super admin only.",
)
async def update_guardrail(
    guardrail_id: str,
    data: GuardrailDefinitionUpdate,
    _current_user: SuperAdmin,
    db: DbSession,
) -> GuardrailDefinitionResponse:
    """Update guardrail definition (super admin only).

    Args:
        guardrail_id: Guardrail UUID
        data: Update data
        _current_user: Current authenticated user (must be SuperAdmin)
        db: Database session

    Returns:
        Updated guardrail definition

    Raises:
        400: Invalid UUID format
        404: Guardrail not found
    """
    guardrail_uuid = validate_uuid(guardrail_id, "guardrail_id")

    service = GuardrailService(db)

    try:
        guardrail = await service.update_guardrail(guardrail_uuid, data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    if not guardrail:
        raise_not_found("Guardrail")

    return guardrail


@router.delete(
    "/{guardrail_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete guardrail definition",
    description="""
Delete a guardrail definition. Super admin only.

**Warning:** This will also delete all policies that use this guardrail.
""",
)
async def delete_guardrail(
    guardrail_id: str,
    _current_user: SuperAdmin,
    db: DbSession,
) -> None:
    """Delete guardrail definition (super admin only).

    Args:
        guardrail_id: Guardrail UUID
        _current_user: Current authenticated user (must be SuperAdmin)
        db: Database session

    Raises:
        400: Invalid UUID format
        404: Guardrail not found
    """
    guardrail_uuid = validate_uuid(guardrail_id, "guardrail_id")

    service = GuardrailService(db)
    success = await service.delete_guardrail(guardrail_uuid)

    if not success:
        raise_not_found("Guardrail")
