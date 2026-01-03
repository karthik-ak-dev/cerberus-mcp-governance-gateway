"""
Authentication Endpoints

Login, token refresh, and user session management.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.db.repositories import UserRepository, OrganisationRepository
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    AuthResponse,
    UserDetails,
)


router = APIRouter()


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """Authenticate user and return tokens with user details.

    Two login flows are supported:
    1. Regular users: Must provide organisation_slug to identify their organisation
    2. SuperAdmins: Omit organisation_slug (they don't belong to any organisation)

    Args:
        request: Login credentials
        db: Database session

    Returns:
        Access and refresh tokens with user details

    Raises:
        HTTPException: If authentication fails
    """
    user_repo = UserRepository(db)
    organisation_slug = None

    if request.organisation_slug:
        # Regular user flow: lookup by organisation + email
        org_repo = OrganisationRepository(db)
        organisation = await org_repo.get_by_slug(request.organisation_slug)

        if not organisation or not organisation.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        user = await user_repo.get_by_email(organisation.id, request.email)
        organisation_id = str(organisation.id)
        organisation_slug = organisation.slug
    else:
        # SuperAdmin flow: lookup globally (no organisation)
        user = await user_repo.get_super_admin_by_email(request.email)
        organisation_id = None

        # If no SuperAdmin found and no organisation_slug provided, reject
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Verify password
    if not user.password_hash or not verify_password(
        request.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Create tokens
    # For SuperAdmins, organisation_id is omitted from the token
    token_data = {
        "sub": str(user.id),
        "role": user.role,
    }
    if organisation_id:
        token_data["organisation_id"] = organisation_id

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserDetails(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            organisation_id=organisation_id,
            organisation_slug=organisation_slug,
        ),
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_tokens(
    request: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """Refresh access token.

    Args:
        request: Refresh token
        db: Database session

    Returns:
        New access and refresh tokens with user details

    Raises:
        HTTPException: If refresh token is invalid
    """
    payload = decode_token(request.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify user still exists and is active
    user_repo = UserRepository(db)
    user = await user_repo.get(payload["sub"])

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Get organisation info if user belongs to an organisation
    organisation_id = payload.get("organisation_id")
    organisation_slug = None
    if organisation_id:
        org_repo = OrganisationRepository(db)
        organisation = await org_repo.get(organisation_id)
        if organisation:
            organisation_slug = organisation.slug

    # Create new tokens
    # Preserve organisation_id from original token (None for SuperAdmins)
    token_data = {
        "sub": str(user.id),
        "role": user.role,
    }
    if organisation_id:
        token_data["organisation_id"] = organisation_id

    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return AuthResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserDetails(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            organisation_id=organisation_id,
            organisation_slug=organisation_slug,
        ),
    )
