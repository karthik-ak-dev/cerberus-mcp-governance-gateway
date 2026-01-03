"""
Organisation Service

Business logic for organisation management.
"""

import secrets
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import SubscriptionTier, UserRole, get_tier_defaults
from app.core.exceptions import ConflictError
from app.core.security import hash_password
from app.core.utils import slugify
from app.db.repositories import OrganisationRepository, UserRepository
from app.models.organisation import Organisation
from app.schemas.organisation import OrganisationResponse


class OrganisationService:
    """Service for organisation operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = OrganisationRepository(session)

    async def create_organisation(
        self,
        name: str,
        slug: str,
        description: Optional[str] = None,
        subscription_tier: SubscriptionTier = SubscriptionTier.DEFAULT,
        admin_email: Optional[str] = None,
    ) -> OrganisationResponse:
        """Create a new organisation.

        Args:
            name: Organisation name
            slug: URL-safe identifier
            description: Optional description
            subscription_tier: Subscription tier (settings are derived from this)
            admin_email: Email for initial admin user

        Returns:
            Created organisation response

        Raises:
            ConflictError: If slug already exists
        """
        # Check slug uniqueness
        if await self.repo.slug_exists(slug):
            raise ConflictError(f"Organisation with slug '{slug}' already exists")

        # Get settings from the subscription tier
        settings_dict = get_tier_defaults(subscription_tier)

        # Create organisation
        organisation = await self.repo.create(
            name=name,
            slug=slug,
            description=description,
            subscription_tier=subscription_tier.value,
            settings=settings_dict,
        )

        user_count = 0

        # Create initial admin user if admin_email provided
        if admin_email:
            user_repo = UserRepository(self.session)

            # Hash a random initial password - user will need to reset it
            initial_password = secrets.token_urlsafe(16)
            password_hash = hash_password(initial_password)

            await user_repo.create(
                organisation_id=organisation.id,
                display_name="Admin",
                email=admin_email,
                role=UserRole.ORG_ADMIN.value,
                password_hash=password_hash,
            )
            user_count = 1

        return self._to_response(
            organisation, workspace_count=0, user_count=user_count
        )

    async def get_organisation(
        self, organisation_id: UUID
    ) -> Optional[OrganisationResponse]:
        """Get organisation by ID.

        Args:
            organisation_id: Organisation UUID

        Returns:
            Organisation response or None
        """
        result = await self.repo.get_with_counts(organisation_id)
        if not result:
            return None

        return self._to_response(
            result["organisation"],
            workspace_count=result["workspace_count"],
            user_count=result["user_count"],
        )

    async def list_organisations(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> Tuple[list[OrganisationResponse], int]:
        """List all organisations.

        Args:
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (organisations, total_count)
        """
        organisations = await self.repo.list_active(offset=offset, limit=limit)
        total = await self.repo.count_active()

        return [
            self._to_response(o, workspace_count=0, user_count=0)
            for o in organisations
        ], total

    async def update_organisation(
        self,
        organisation_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        subscription_tier: Optional[SubscriptionTier] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[OrganisationResponse]:
        """Update organisation.

        Args:
            organisation_id: Organisation UUID
            name: Optional new name
            description: Optional new description
            subscription_tier: Optional new subscription tier
            is_active: Optional active status

        Returns:
            Updated organisation response or None

        Raises:
            ConflictError: If new slug already exists
        """
        # First check if organisation exists and is not soft-deleted
        existing = await self.get_organisation(organisation_id)
        if not existing:
            return None

        update_data: dict[str, object] = {}

        if name is not None:
            update_data["name"] = name
            # Regenerate slug when name changes
            new_slug = slugify(name)
            # Check slug uniqueness (excluding current organisation)
            if await self.repo.slug_exists(new_slug, exclude_id=organisation_id):
                raise ConflictError(
                    f"Organisation with slug '{new_slug}' already exists"
                )
            update_data["slug"] = new_slug
        if description is not None:
            update_data["description"] = description
        if subscription_tier is not None:
            # When tier changes, update both the tier and the settings
            update_data["subscription_tier"] = subscription_tier.value
            update_data["settings"] = get_tier_defaults(subscription_tier)
        if is_active is not None:
            update_data["is_active"] = is_active

        if not update_data:
            # No updates to apply, return current organisation
            return existing

        organisation = await self.repo.update(organisation_id, **update_data)
        if not organisation:
            return None

        return self._to_response(organisation, workspace_count=0, user_count=0)

    async def delete_organisation(self, organisation_id: UUID) -> bool:
        """Soft delete organisation.

        Args:
            organisation_id: Organisation UUID

        Returns:
            True if deleted
        """
        result = await self.repo.soft_delete(organisation_id)
        return result is not None

    def _to_response(
        self,
        organisation: Organisation,
        workspace_count: int,
        user_count: int,
    ) -> OrganisationResponse:
        """Convert model to response schema."""
        return OrganisationResponse(
            id=str(organisation.id),
            name=organisation.name,
            slug=organisation.slug,
            description=organisation.description,
            subscription_tier=SubscriptionTier(organisation.subscription_tier),
            settings=organisation.settings,
            is_active=organisation.is_active,
            created_at=organisation.created_at,
            updated_at=organisation.updated_at,
            workspace_count=workspace_count,
            user_count=user_count,
        )
