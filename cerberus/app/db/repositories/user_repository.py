"""
User Repository

Database operations specific to the User model.
Extends BaseRepository with user-specific query methods.

Users in Cerberus are for DASHBOARD ACCESS ONLY:
- Users log into the Cerberus dashboard to manage organisations, workspaces, agents
- Users do NOT connect directly to MCP servers
- AI agents use AgentAccess keys to connect through the Cerberus Gateway

MVP Roles:
- super_admin: Platform admin (system administrators)
- org_admin: Full admin for their organisation
- org_viewer: Read-only access to dashboards/logs

Note: No workspace-level user management for MVP. Users have org-wide access
based on their role.

Common Operations:
==================
- get_by_email()              → Find user by email (for dashboard login)
- get_by_organisation()       → List all users for an organisation
- get_by_role()               → List users with a specific role
- count_by_organisation()     → Count users for an organisation
- get_super_admin_by_email()  → Find super admin (platform admin)

Key Concept - Dashboard Users vs Agents:
========================================
    Dashboard Users (this model):
    - Have email + password_hash for login
    - Access the Cerberus UI
    - Manage organisations, workspaces, policies

    Agent Access (separate model):
    - Have access keys for API authentication
    - Connect AI agents to MCP servers
    - Belong to MCP Server Workspaces (not users)

Usage Example:
==============
    async def authenticate_dashboard_user(
        db: AsyncSession,
        organisation_id: UUID,
        email: str,
        password: str
    ):
        repo = UserRepository(db)

        # Find user by email
        user = await repo.get_by_email(organisation_id, email)
        if not user:
            raise AuthError("User not found")

        # Verify password
        if not verify_password(password, user.password_hash):
            raise AuthError("Invalid password")

        return user
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count

from app.config.constants import UserRole
from app.db.repositories.base import BaseRepository
from app.models.user import User


class UserRepository(BaseRepository[User]):
    """
    Repository for User database operations.

    Provides methods for user lookups and queries:
    - Looking up users by email (for dashboard login)
    - Listing users by organisation or role
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize UserRepository.

        Args:
            session: Async database session
        """
        super().__init__(User, session)

    # ═══════════════════════════════════════════════════════════════════════════
    # PRIMARY LOOKUP METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_by_email(
        self,
        organisation_id: UUID,
        email: str,
    ) -> User | None:
        """
        Get user by organisation and email.

        Used for dashboard login and user lookups by email.

        Args:
            organisation_id: UUID of the organisation
            email: User's email address

        Returns:
            User if found, None otherwise

        Example:
            # Dashboard login flow
            user = await repo.get_by_email(org.id, "jane@acme.com")
            if user and user.password_hash:
                # Verify password and create session
                pass

        SQL Generated:
            SELECT * FROM users
            WHERE organisation_id = '...'
              AND email = 'jane@acme.com'
              AND deleted_at IS NULL
        """
        result = await self.session.execute(
            select(User).where(
                User.organisation_id == organisation_id,
                User.email == email,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_super_admin_by_email(
        self,
        email: str,
    ) -> User | None:
        """
        Get super admin user by email (no organisation scope).

        SuperAdmins are platform-level users with organisation_id = NULL.
        This method looks up users globally by email where role is super_admin.

        Args:
            email: User's email address

        Returns:
            SuperAdmin user if found, None otherwise

        Example:
            # SuperAdmin login flow (no organisation required)
            user = await repo.get_super_admin_by_email("superadmin@cerberus.local")
            if user and user.password_hash:
                # Verify password and create session
                pass

        SQL Generated:
            SELECT * FROM users
            WHERE email = 'superadmin@cerberus.local'
              AND role = 'super_admin'
              AND organisation_id IS NULL
              AND deleted_at IS NULL
        """
        result = await self.session.execute(
            select(User).where(
                User.email == email,
                User.role == UserRole.SUPER_ADMIN.value,
                User.organisation_id.is_(None),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    # ═══════════════════════════════════════════════════════════════════════════
    # LIST METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_by_organisation(
        self,
        organisation_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """
        Get all users for an organisation.

        Lists users belonging to an organisation with pagination.

        Args:
            organisation_id: UUID of the organisation
            offset: Pagination offset
            limit: Max records to return

        Returns:
            List of users

        Example:
            users = await repo.get_by_organisation(org.id)
            for user in users:
                print(f"{user.display_name} ({user.role})")

        SQL Generated:
            SELECT * FROM users
            WHERE organisation_id = '...' AND deleted_at IS NULL
            ORDER BY created_at DESC
            OFFSET 0 LIMIT 100
        """
        result = await self.session.execute(
            select(User)
            .where(
                User.organisation_id == organisation_id,
                User.deleted_at.is_(None),
            )
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_role(
        self,
        organisation_id: UUID,
        role: str,
    ) -> list[User]:
        """
        Get users with a specific role.

        Filters users by their assigned role.

        Args:
            organisation_id: UUID of the organisation
            role: Role to filter by ("org_admin", "org_viewer")

        Returns:
            List of users with that role

        Example:
            # Find all org admins
            admins = await repo.get_by_role(org.id, "org_admin")

            # Find all viewers
            viewers = await repo.get_by_role(org.id, "org_viewer")

        SQL Generated:
            SELECT * FROM users
            WHERE organisation_id = '...'
              AND role = 'org_admin'
              AND deleted_at IS NULL
        """
        result = await self.session.execute(
            select(User).where(
                User.organisation_id == organisation_id,
                User.role == role,
                User.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    # ═══════════════════════════════════════════════════════════════════════════
    # COUNT METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def count_by_organisation(self, organisation_id: UUID) -> int:
        """
        Count users for an organisation.

        Returns total number of non-deleted users.
        Useful for enforcing user limits and pagination.

        Args:
            organisation_id: UUID of the organisation

        Returns:
            Number of users

        Example:
            count = await repo.count_by_organisation(org.id)
            if count >= org.max_users:
                raise LimitExceededError("Max users reached")

        SQL Generated:
            SELECT COUNT(*) FROM users
            WHERE organisation_id = '...' AND deleted_at IS NULL
        """
        result = await self.session.execute(
            select(count(User.id))
            .select_from(User)
            .where(
                User.organisation_id == organisation_id,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    # ═══════════════════════════════════════════════════════════════════════════
    # VALIDATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def email_exists(
        self,
        organisation_id: UUID,
        email: str,
        exclude_id: UUID | None = None,
    ) -> bool:
        """
        Check if email exists within an organisation.

        Used to validate email uniqueness when creating or updating users.
        Emails must be unique within an organisation.

        Args:
            organisation_id: UUID of the organisation
            email: Email to check
            exclude_id: Optional user ID to exclude (for updates)

        Returns:
            True if email exists (taken), False if available

        Example (create):
            if await repo.email_exists(org.id, "jane@acme.com"):
                raise ConflictError("Email already exists in this organisation")

        Example (update):
            if await repo.email_exists(org.id, "new@acme.com", exclude_id=user.id):
                raise ConflictError("Email already exists in this organisation")
        """
        query = (
            select(count(User.id))
            .select_from(User)
            .where(
                User.organisation_id == organisation_id,
                User.email == email,
                User.deleted_at.is_(None),
            )
        )

        if exclude_id:
            query = query.where(User.id != exclude_id)

        result = await self.session.execute(query)
        return (result.scalar() or 0) > 0

    async def super_admin_email_exists(
        self,
        email: str,
        exclude_id: UUID | None = None,
    ) -> bool:
        """
        Check if email exists among super admins (users with no organisation).

        Super admins have organisation_id = NULL and their emails must be
        globally unique among super admins.

        Args:
            email: Email to check
            exclude_id: Optional user ID to exclude (for updates)

        Returns:
            True if email exists (taken), False if available

        Example:
            if await repo.super_admin_email_exists("admin@cerberus.local"):
                raise ConflictError("Super admin with this email already exists")
        """
        query = (
            select(count(User.id))
            .select_from(User)
            .where(
                User.organisation_id.is_(None),
                User.email == email,
                User.deleted_at.is_(None),
            )
        )

        if exclude_id:
            query = query.where(User.id != exclude_id)

        result = await self.session.execute(query)
        return (result.scalar() or 0) > 0
