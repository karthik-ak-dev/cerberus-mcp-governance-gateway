"""
User Service

Business logic for user management.
Users are for DASHBOARD access only - they are NOT used for MCP authentication.

MVP Roles:
- super_admin: Platform admin (system administrators)
- org_admin: Full admin for their organisation
- org_viewer: Read-only access to dashboards/logs

Note: No workspace-level user management for MVP. Users have org-wide access
based on their role.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password, verify_password
from app.db.repositories import UserRepository
from app.schemas.user import UserResponse


class UserService:
    """Service for user operations.

    Users are dashboard/admin portal users with email/password login.
    They are NOT used for MCP agent authentication (use AgentAccess for that).

    For MVP, users have org-wide access based on role (org_admin or org_viewer).
    No workspace-level permissions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def create_user(
        self,
        organisation_id: UUID,
        display_name: str,
        email: str,
        password: str,
        role: str = "org_viewer",
        metadata: dict[str, Any] | None = None,
    ) -> UserResponse:
        """Create a new dashboard user.

        Args:
            organisation_id: Parent organisation UUID
            display_name: Display name
            email: Email address (used for login)
            password: Password for dashboard login
            role: User role (org_admin or org_viewer)
            metadata: Custom metadata

        Returns:
            Created user response

        Raises:
            ConflictError: If email already exists in organisation
        """
        # Check email uniqueness within organisation
        if await self.repo.email_exists(organisation_id, email):
            raise ConflictError(
                f"User with email '{email}' already exists in this organisation"
            )

        # Hash password
        password_hash = hash_password(password)

        user = await self.repo.create(
            organisation_id=organisation_id,
            display_name=display_name,
            email=email,
            role=role,
            metadata_=metadata or {},
            password_hash=password_hash,
        )

        return self._to_response(user)

    async def get_user(self, user_id: UUID) -> UserResponse | None:
        """Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User response or None
        """
        user = await self.repo.get(user_id)
        if not user or user.deleted_at:
            return None

        return self._to_response(user)

    async def get_user_by_email(
        self,
        organisation_id: UUID,
        email: str,
    ) -> UserResponse | None:
        """Get user by email within an organisation.

        Args:
            organisation_id: Organisation UUID
            email: User email

        Returns:
            User response or None
        """
        user = await self.repo.get_by_email(organisation_id, email)
        if not user or user.deleted_at:
            return None

        return self._to_response(user)

    async def list_users(
        self,
        organisation_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[UserResponse], int]:
        """List users for an organisation.

        Args:
            organisation_id: Organisation UUID
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (users, total_count)
        """
        users = await self.repo.get_by_organisation(
            organisation_id, offset=offset, limit=limit
        )
        total = await self.repo.count_by_organisation(organisation_id)

        return [self._to_response(u) for u in users], total

    async def update_user(
        self,
        user_id: UUID,
        **kwargs: Any,
    ) -> UserResponse | None:
        """Update user.

        Args:
            user_id: User UUID
            **kwargs: Fields to update (display_name, email, role, is_active, metadata)

        Returns:
            Updated user response or None

        Raises:
            ConflictError: If email already exists in organisation
        """
        existing_user = await self.repo.get(user_id)
        if not existing_user or existing_user.deleted_at:
            return None

        organisation_id = existing_user.organisation_id

        # Validate email uniqueness if being changed
        if "email" in kwargs and kwargs["email"] is not None:
            new_email = kwargs["email"]
            if new_email != existing_user.email:
                if await self.repo.email_exists(
                    organisation_id, new_email, exclude_id=user_id
                ):
                    raise ConflictError(
                        f"User with email '{new_email}' already exists in this organisation"
                    )

        user = await self.repo.update(user_id, **kwargs)
        if not user:
            return None

        return self._to_response(user)

    async def delete_user(self, user_id: UUID) -> bool:
        """Soft delete user.

        Args:
            user_id: User UUID

        Returns:
            True if deleted
        """
        result = await self.repo.soft_delete(user_id)
        return result is not None

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user's password.

        Args:
            user_id: User UUID
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password changed successfully

        Raises:
            NotFoundError: If user not found
            ConflictError: If current password is incorrect
        """
        user = await self.repo.get(user_id)
        if not user or user.deleted_at:
            raise NotFoundError("User not found")

        if not verify_password(current_password, user.password_hash):
            raise ConflictError("Current password is incorrect")

        new_hash = hash_password(new_password)
        await self.repo.update(user_id, password_hash=new_hash)
        return True

    def _to_response(self, user: Any) -> UserResponse:
        """Convert model to response schema."""
        return UserResponse(
            id=str(user.id),
            organisation_id=(
                str(user.organisation_id) if user.organisation_id else None
            ),
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
            metadata=user.metadata_ if user.metadata_ else {},
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
