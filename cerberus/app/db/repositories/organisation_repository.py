"""
Organisation Repository

Database operations specific to the Organisation model.
Extends BaseRepository with organisation-specific query methods.

Common Operations:
==================
- get_by_slug()     → Find organisation by URL slug ("acme-corp")
- get_with_counts() → Get organisation with workspace/user counts
- slug_exists()     → Check if slug is taken
- list_active()     → List non-deleted, active organisations
- count_active()    → Count active organisations

Why These Methods?
==================
- get_by_slug: Organisations are often looked up by slug in URLs
  Example: GET /api/v1/organisations/acme-corp → need to find by slug

- get_with_counts: Dashboard needs to show workspace/user counts
  More efficient to load in one query than separate counts

- slug_exists: Must validate uniqueness when creating/updating
  Slug is used in URLs so must be globally unique

Usage Example:
==============
    async def get_organisation_info(db: AsyncSession, slug: str):
        repo = OrganisationRepository(db)

        # Get organisation by slug (returns None if not found)
        org = await repo.get_by_slug(slug)
        if not org:
            raise NotFoundError(f"Organisation '{slug}' not found")

        # Get with counts for dashboard
        data = await repo.get_with_counts(org.id)
        return {
            "organisation": data["organisation"],
            "workspaces": data["workspace_count"],
            "users": data["user_count"]
        }
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.functions import count

from app.db.repositories.base import BaseRepository
from app.models.organisation import Organisation


class OrganisationRepository(BaseRepository[Organisation]):
    """
    Repository for Organisation database operations.

    Provides methods for common organisation queries beyond basic CRUD:
    - Looking up organisations by slug
    - Listing active organisations
    - Checking slug availability
    - Getting organisation stats
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize OrganisationRepository.

        Args:
            session: Async database session
        """
        super().__init__(Organisation, session)

    # ═══════════════════════════════════════════════════════════════════════════
    # LOOKUP METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_by_slug(self, slug: str) -> Organisation | None:
        """
        Get organisation by its URL slug.

        Slug is the URL-safe identifier used in API paths.
        Only returns non-deleted organisations.

        Args:
            slug: URL slug (e.g., "acme-corp", "techstartup")

        Returns:
            Organisation if found, None otherwise

        Example:
            org = await repo.get_by_slug("acme-corp")
            if org:
                print(f"Found: {org.name}")  # "Acme Corporation"

        SQL Generated:
            SELECT * FROM organisations
            WHERE slug = 'acme-corp' AND deleted_at IS NULL
        """
        result = await self.session.execute(
            select(Organisation).where(
                Organisation.slug == slug,
                Organisation.deleted_at.is_(None),  # Exclude soft-deleted
            )
        )
        return result.scalar_one_or_none()

    async def get_with_counts(self, organisation_id: UUID) -> dict | None:
        """
        Get organisation with workspace and user counts.

        Loads the organisation with its related workspaces and users
        to provide counts. Useful for dashboard/admin views.

        Args:
            organisation_id: Organisation UUID

        Returns:
            Dict with organisation and counts, or None if not found:
            {
                "organisation": Organisation,
                "workspace_count": 5,
                "user_count": 23
            }

        Example:
            data = await repo.get_with_counts(organisation_id)
            if data:
                print(f"{data['organisation'].name} has {data['workspace_count']} workspaces")

        SQL Generated:
            SELECT * FROM organisations WHERE id = '...' AND deleted_at IS NULL
            -- Plus eager loading of mcp_server_workspaces and users relationships

        Note:
            Uses selectinload to eager-load relationships in separate queries,
            avoiding N+1 query problems while keeping the main query simple.
        """
        result = await self.session.execute(
            select(Organisation)
            .options(
                selectinload(Organisation.mcp_server_workspaces),  # Load workspaces
                selectinload(Organisation.users),  # Load users
            )
            .where(Organisation.id == organisation_id, Organisation.deleted_at.is_(None))
        )
        organisation = result.scalar_one_or_none()

        if not organisation:
            return None

        return {
            "organisation": organisation,
            "workspace_count": len(organisation.mcp_server_workspaces),
            "user_count": len(organisation.users),
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # VALIDATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def slug_exists(self, slug: str, exclude_id: UUID | None = None) -> bool:
        """
        Check if a slug is already taken.

        Used to validate uniqueness when creating or updating organisations.
        Can exclude a specific organisation ID (useful when updating).

        Args:
            slug: Slug to check for uniqueness
            exclude_id: Optional organisation ID to exclude from check
                       (use when updating to allow keeping current slug)

        Returns:
            True if slug exists (taken), False if available

        Example (create):
            if await repo.slug_exists("new-org"):
                raise ValidationError("Slug already taken")

        Example (update):
            # Allow keeping current slug, check others
            if await repo.slug_exists("new-slug", exclude_id=org.id):
                raise ValidationError("Slug already taken")

        SQL Generated:
            SELECT COUNT(*) FROM organisations WHERE slug = 'new-slug'
            -- or with exclude:
            SELECT COUNT(*) FROM organisations WHERE slug = 'new-slug' AND id != '...'
        """
        query = (
            select(count(Organisation.id))
            .select_from(Organisation)
            .where(Organisation.slug == slug)
        )

        if exclude_id:
            query = query.where(Organisation.id != exclude_id)

        result = await self.session.execute(query)
        return (result.scalar() or 0) > 0

    # ═══════════════════════════════════════════════════════════════════════════
    # LIST METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def list_active(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Organisation]:
        """
        List active (non-deleted, is_active=True) organisations.

        Returns organisations that are both:
        - Not soft-deleted (deleted_at IS NULL)
        - Active (is_active = True)

        Args:
            offset: Number of records to skip (for pagination)
            limit: Maximum records to return

        Returns:
            List of active organisations, ordered by creation date (newest first)

        Example:
            # Get first page of active organisations
            orgs = await repo.list_active(offset=0, limit=20)

            # Get second page
            orgs = await repo.list_active(offset=20, limit=20)

        SQL Generated:
            SELECT * FROM organisations
            WHERE deleted_at IS NULL AND is_active = true
            ORDER BY created_at DESC
            OFFSET 0 LIMIT 20
        """
        result = await self.session.execute(
            select(Organisation)
            .where(
                Organisation.deleted_at.is_(None),  # Not soft-deleted
                Organisation.is_active.is_(True),  # Account is active
            )
            .order_by(Organisation.created_at.desc())  # Newest first
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_active(self) -> int:
        """
        Count active organisations.

        Returns the total number of active, non-deleted organisations.
        Useful for pagination (total count) and analytics.

        Returns:
            Number of active organisations

        Example:
            total = await repo.count_active()
            print(f"Total active organisations: {total}")

        SQL Generated:
            SELECT COUNT(*) FROM organisations
            WHERE deleted_at IS NULL AND is_active = true
        """
        result = await self.session.execute(
            select(count(Organisation.id))
            .select_from(Organisation)
            .where(Organisation.deleted_at.is_(None), Organisation.is_active.is_(True))
        )
        return result.scalar() or 0
