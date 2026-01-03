"""
API Dependencies

Common dependencies for Control Plane APIs.
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import UserRole
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_token
from app.db.repositories import (
    McpServerWorkspaceRepository,
    OrganisationRepository,
    UserRepository,
)
from app.db.session import get_db


# Security scheme for Swagger UI - shows "Authorize" button
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user_token(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(security_scheme)
    ],
) -> dict:
    """Extract and validate JWT token from Authorization header.

    Args:
        credentials: HTTP Bearer credentials from Authorization header

    Returns:
        Decoded token payload

    Raises:
        AuthenticationError: If token is missing or invalid
    """
    if not credentials:
        raise AuthenticationError("Authorization header required")

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise AuthenticationError("Invalid or expired token")

    return payload


async def get_current_user(
    token: Annotated[dict, Depends(get_current_user_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get current authenticated user.

    Args:
        token: Decoded JWT token
        db: Database session

    Returns:
        User data dict with organisation_id (None for SuperAdmins)

    Raises:
        AuthenticationError: If user not found
    """
    user_id = token.get("sub")
    organisation_id = token.get("organisation_id")  # None for SuperAdmins
    role = token.get("role")

    if not user_id:
        raise AuthenticationError("Invalid token payload")

    # SuperAdmins don't have organisation_id in token, regular users must have it
    if role != UserRole.SUPER_ADMIN.value and not organisation_id:
        raise AuthenticationError("Invalid token payload")

    repo = UserRepository(db)
    user = await repo.get(UUID(user_id))

    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")

    return {
        "id": str(user.id),
        "organisation_id": str(user.organisation_id) if user.organisation_id else None,
        "email": user.email,
        "role": user.role,
    }


def require_role(*roles: str):
    """Dependency factory to require specific roles.

    Args:
        *roles: Allowed roles

    Returns:
        Dependency function
    """

    async def check_role(
        current_user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        if current_user["role"] not in roles:
            raise AuthorizationError(
                f"This action requires one of these roles: {', '.join(roles)}"
            )
        return current_user

    return check_role


async def get_organisation_from_path(
    organisation_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Validate organisation access from path parameter.

    Args:
        organisation_id: Organisation ID from path
        db: Database session
        current_user: Current user

    Returns:
        Organisation data dict

    Raises:
        AuthorizationError: If user cannot access organisation
        HTTPException: If organisation not found
    """
    # Super admin can access any organisation
    if current_user["role"] != UserRole.SUPER_ADMIN.value:
        if current_user["organisation_id"] != organisation_id:
            raise AuthorizationError("Cannot access this organisation")

    repo = OrganisationRepository(db)
    organisation = await repo.get(UUID(organisation_id))

    if not organisation or organisation.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    return {
        "id": str(organisation.id),
        "name": organisation.name,
        "slug": organisation.slug,
        "settings": organisation.settings,
    }


async def get_workspace_from_path(
    mcp_server_workspace_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Validate MCP server workspace access from path parameter.

    Args:
        mcp_server_workspace_id: Workspace ID from path
        db: Database session
        current_user: Current user

    Returns:
        Workspace data dict

    Raises:
        AuthorizationError: If user cannot access workspace
        HTTPException: If workspace not found
    """
    repo = McpServerWorkspaceRepository(db)
    workspace = await repo.get(UUID(mcp_server_workspace_id))

    if not workspace or workspace.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP Server Workspace not found",
        )

    # Check organisation access
    if current_user["role"] != UserRole.SUPER_ADMIN.value:
        if str(workspace.organisation_id) != current_user["organisation_id"]:
            raise AuthorizationError("Cannot access this workspace")

    return {
        "id": str(workspace.id),
        "organisation_id": str(workspace.organisation_id),
        "name": workspace.name,
        "slug": workspace.slug,
        "environment_type": workspace.environment_type,
        "settings": workspace.settings,
    }


# Type aliases for cleaner signatures
CurrentUser = Annotated[dict, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
OrganisationAdmin = Annotated[
    dict, Depends(require_role(UserRole.SUPER_ADMIN.value, UserRole.ORG_ADMIN.value))
]
SuperAdmin = Annotated[dict, Depends(require_role(UserRole.SUPER_ADMIN.value))]
OrganisationViewer = Annotated[
    dict,
    Depends(
        require_role(
            UserRole.SUPER_ADMIN.value, UserRole.ORG_ADMIN.value, UserRole.ORG_VIEWER.value
        )
    ),
]
