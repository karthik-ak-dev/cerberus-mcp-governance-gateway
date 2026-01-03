"""
API Utilities

Shared helper functions for API endpoints.
"""

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.config.constants import UserRole


def validate_uuid(value: str, field_name: str) -> UUID:
    """
    Validate and convert a string to UUID.

    Args:
        value: String value to convert
        field_name: Field name for error message

    Returns:
        UUID object

    Raises:
        HTTPException: If value is not a valid UUID (400 Bad Request)

    Example:
        workspace_uuid = validate_uuid(workspace_id, "mcp_server_workspace_id")
    """
    try:
        return UUID(value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: must be a valid UUID",
        ) from e


def check_organisation_access(
    current_user: dict[str, Any],
    target_organisation_id: str,
    action: str = "access",
) -> None:
    """
    Check if current user has access to the target organisation.

    Super admins can access any organisation. Other users can only access their own organisation.

    Args:
        current_user: Current authenticated user dict (must have 'role' and 'organisation_id')
        target_organisation_id: Organisation ID to check access for
        action: Action being performed (for error message)

    Raises:
        HTTPException: If user doesn't have access (403 Forbidden)

    Example:
        check_organisation_access(current_user, organisation_id, "modify users in")
    """
    if current_user["role"] != UserRole.SUPER_ADMIN:
        if current_user["organisation_id"] != target_organisation_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot {action} resources in different organisation",
            )


# Alias for backwards compatibility during migration
check_tenant_access = check_organisation_access


def raise_not_found(resource: str) -> None:
    """
    Raise a 404 Not Found exception.

    Args:
        resource: Name of the resource (e.g., "MCP Server Workspace", "User")

    Raises:
        HTTPException: 404 Not Found

    Example:
        if not workspace:
            raise_not_found("MCP Server Workspace")
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found",
    )


def raise_forbidden(message: str) -> None:
    """
    Raise a 403 Forbidden exception.

    Args:
        message: Error message

    Raises:
        HTTPException: 403 Forbidden

    Example:
        raise_forbidden("Cannot access this workspace")
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message,
    )


def raise_bad_request(message: str) -> None:
    """
    Raise a 400 Bad Request exception.

    Args:
        message: Error message

    Raises:
        HTTPException: 400 Bad Request

    Example:
        raise_bad_request("start_time must be before end_time")
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message,
    )
