"""
MCP Server Workspace Repository

Database operations specific to the McpServerWorkspace model.
Extends BaseRepository with workspace-specific query methods.

Common Operations:
==================
- get_by_organisation()  → List all workspaces for an organisation
- get_by_slug()          → Find workspace by organisation + slug combo
- count_by_organisation()→ Count workspaces for an organisation
- slug_exists()          → Check if slug is taken within organisation
- get_by_environment()   → Find workspaces by type (prod/staging/dev)

Key Concept - Slug Uniqueness:
==============================
Workspace slugs are unique WITHIN an organisation, not globally.
This means different organisations can have workspaces with the same slug:

    Organisation "acme-corp" → workspace "prod" ✓
    Organisation "other-co"  → workspace "prod" ✓  (allowed, different org)
    Organisation "acme-corp" → workspace "prod" ✗  (not allowed, same org)

Usage Example:
==============
    async def get_workspace_context(
        db: AsyncSession,
        org_slug: str,
        workspace_slug: str
    ):
        org_repo = OrganisationRepository(db)
        workspace_repo = McpServerWorkspaceRepository(db)

        # Get organisation first
        org = await org_repo.get_by_slug(org_slug)
        if not org:
            raise NotFoundError("Organisation not found")

        # Get workspace within organisation
        workspace = await workspace_repo.get_by_slug(org.id, workspace_slug)
        if not workspace:
            raise NotFoundError("Workspace not found")

        return {"organisation": org, "workspace": workspace}
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count

from app.db.repositories.base import BaseRepository
from app.models.mcp_server_workspace import McpServerWorkspace


class McpServerWorkspaceRepository(BaseRepository[McpServerWorkspace]):
    """
    Repository for McpServerWorkspace database operations.

    Provides methods for common workspace queries:
    - Looking up workspaces by organisation and slug
    - Listing workspaces for an organisation
    - Filtering by environment type
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize McpServerWorkspaceRepository.

        Args:
            session: Async database session
        """
        super().__init__(McpServerWorkspace, session)

    # ═══════════════════════════════════════════════════════════════════════════
    # LIST METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_by_organisation(
        self,
        organisation_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[McpServerWorkspace]:
        """
        Get all workspaces for an organisation.

        Returns workspaces belonging to a specific organisation,
        excluding soft-deleted ones.

        Args:
            organisation_id: UUID of the organisation
            offset: Pagination offset
            limit: Max records to return

        Returns:
            List of workspaces for the organisation

        Example:
            workspaces = await repo.get_by_organisation(org.id)
            for ws in workspaces:
                print(f"{ws.name} ({ws.environment_type})")
            # Output:
            # Production (production)
            # Staging (staging)
            # Development (development)

        SQL Generated:
            SELECT * FROM mcp_server_workspaces
            WHERE organisation_id = '...' AND deleted_at IS NULL
            ORDER BY created_at DESC
            OFFSET 0 LIMIT 100
        """
        result = await self.session.execute(
            select(McpServerWorkspace)
            .where(
                McpServerWorkspace.organisation_id == organisation_id,
                McpServerWorkspace.deleted_at.is_(None),
            )
            .order_by(McpServerWorkspace.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_environment(
        self,
        organisation_id: UUID,
        environment_type: str,
    ) -> list[McpServerWorkspace]:
        """
        Get workspaces by environment type.

        Filters workspaces by their environment classification.

        Args:
            organisation_id: UUID of the organisation
            environment_type: Type of environment
                             ("production", "staging", "development")

        Returns:
            List of workspaces with that environment type

        Example:
            # Get all production workspaces
            prod_workspaces = await repo.get_by_environment(
                org.id,
                "production"
            )

        SQL Generated:
            SELECT * FROM mcp_server_workspaces
            WHERE organisation_id = '...'
              AND environment_type = 'production'
              AND deleted_at IS NULL
        """
        result = await self.session.execute(
            select(McpServerWorkspace).where(
                McpServerWorkspace.organisation_id == organisation_id,
                McpServerWorkspace.environment_type == environment_type,
                McpServerWorkspace.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    # ═══════════════════════════════════════════════════════════════════════════
    # LOOKUP METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_by_slug(
        self,
        organisation_id: UUID,
        slug: str,
    ) -> McpServerWorkspace | None:
        """
        Get workspace by organisation ID and slug.

        Looks up a workspace using the organisation + slug combination.
        This is the primary lookup method for API requests.

        Args:
            organisation_id: UUID of the organisation
            slug: Workspace slug (e.g., "prod", "staging", "dev")

        Returns:
            McpServerWorkspace if found, None otherwise

        Example:
            workspace = await repo.get_by_slug(org.id, "prod")
            if workspace:
                print(f"Found: {workspace.name}")  # "Production"

        SQL Generated:
            SELECT * FROM mcp_server_workspaces
            WHERE organisation_id = '...'
              AND slug = 'prod'
              AND deleted_at IS NULL

        Note:
            Slug uniqueness is per-organisation, so we need both
            organisation_id and slug to identify a workspace.
        """
        result = await self.session.execute(
            select(McpServerWorkspace).where(
                McpServerWorkspace.organisation_id == organisation_id,
                McpServerWorkspace.slug == slug,
                McpServerWorkspace.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    # ═══════════════════════════════════════════════════════════════════════════
    # COUNT METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def count_by_organisation(self, organisation_id: UUID) -> int:
        """
        Count workspaces for an organisation.

        Returns total number of non-deleted workspaces for an organisation.
        Useful for enforcing workspace limits and pagination.

        Args:
            organisation_id: UUID of the organisation

        Returns:
            Number of workspaces

        Example:
            count = await repo.count_by_organisation(org.id)
            if count >= org.max_mcp_server_workspaces:
                raise LimitExceededError("Max workspaces reached")

        SQL Generated:
            SELECT COUNT(*) FROM mcp_server_workspaces
            WHERE organisation_id = '...' AND deleted_at IS NULL
        """
        result = await self.session.execute(
            select(count(McpServerWorkspace.id))
            .select_from(McpServerWorkspace)
            .where(
                McpServerWorkspace.organisation_id == organisation_id,
                McpServerWorkspace.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    # ═══════════════════════════════════════════════════════════════════════════
    # VALIDATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def slug_exists(
        self,
        organisation_id: UUID,
        slug: str,
        exclude_id: UUID | None = None,
    ) -> bool:
        """
        Check if slug exists within an organisation.

        Validates slug uniqueness within an organisation's scope.
        Different organisations CAN have the same slug.
        Only checks non-deleted workspaces (deleted slugs can be reused).

        Uses ix_mcp_server_workspaces_org_deleted composite index.

        Args:
            organisation_id: UUID of the organisation
            slug: Slug to check
            exclude_id: Workspace ID to exclude (for updates)

        Returns:
            True if slug exists (taken), False if available

        Example (create):
            if await repo.slug_exists(org.id, "new-workspace"):
                raise ValidationError("Slug already exists in this organisation")

        Example (update):
            if await repo.slug_exists(org.id, "new-slug", exclude_id=workspace.id):
                raise ValidationError("Slug already exists in this organisation")

        SQL Generated:
            SELECT COUNT(*) FROM mcp_server_workspaces
            WHERE organisation_id = '...'
              AND slug = 'new-workspace'
              AND deleted_at IS NULL
        """
        query = (
            select(count(McpServerWorkspace.id))
            .select_from(McpServerWorkspace)
            .where(
                McpServerWorkspace.organisation_id == organisation_id,
                McpServerWorkspace.slug == slug,
                McpServerWorkspace.deleted_at.is_(None),
            )
        )

        if exclude_id:
            query = query.where(McpServerWorkspace.id != exclude_id)

        result = await self.session.execute(query)
        return (result.scalar() or 0) > 0
