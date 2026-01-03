"""
Guardrail Repository

Database operations specific to the Guardrail model.
Extends BaseRepository with guardrail-specific query methods.

Common Operations:
==================
- get_by_type()      → Find guardrail by its type identifier
- list_active()      → List all active guardrail definitions
- list_by_category() → List guardrails by category (rbac, pii, content, rate_limit)
- get_all_types()    → Get all guardrail types as a list

Guardrails in the System:
=========================
Guardrails are atomic security checks. Each guardrail definition is stored
in the guardrails table and can be attached to entities via policies.

MVP Guardrail Types:
- RBAC: rbac
- PII: pii_credit_card, pii_ssn, pii_email, pii_phone, pii_ip_address
- Content: content_large_documents, content_structured_data, content_source_code
- Rate Limit: rate_limit_per_minute, rate_limit_per_hour

Usage Example:
==============
    async def get_available_guardrails(db: AsyncSession):
        repo = GuardrailRepository(db)

        # Get all active guardrails
        guardrails = await repo.list_active()

        # Group by category
        by_category = {}
        for g in guardrails:
            if g.category not in by_category:
                by_category[g.category] = []
            by_category[g.category].append(g)

        return by_category
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count

from app.db.repositories.base import BaseRepository
from app.models.guardrail import Guardrail


class GuardrailRepository(BaseRepository[Guardrail]):
    """
    Repository for Guardrail database operations.

    Provides methods for:
    - Looking up guardrail definitions by type
    - Listing guardrails by category
    - Checking if guardrail types exist
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize GuardrailRepository.

        Args:
            session: Async database session
        """
        super().__init__(Guardrail, session)

    # ═══════════════════════════════════════════════════════════════════════════
    # LOOKUP METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_by_type(self, guardrail_type: str) -> Guardrail | None:
        """
        Get guardrail by its type identifier.

        The guardrail_type is the unique identifier for the guardrail
        (e.g., "rbac", "pii_ssn", "rate_limit_per_minute").

        Args:
            guardrail_type: Guardrail type identifier

        Returns:
            Guardrail if found, None otherwise

        Example:
            guardrail = await repo.get_by_type("pii_ssn")
            if guardrail:
                print(f"Found: {guardrail.display_name}")  # "PII - SSN Detection"

        SQL Generated:
            SELECT * FROM guardrails
            WHERE guardrail_type = 'pii_ssn'
        """
        result = await self.session.execute(
            select(Guardrail).where(Guardrail.guardrail_type == guardrail_type)
        )
        return result.scalar_one_or_none()

    async def get_by_types(self, guardrail_types: list[str]) -> list[Guardrail]:
        """
        Get multiple guardrails by their type identifiers.

        Args:
            guardrail_types: List of guardrail type identifiers

        Returns:
            List of guardrails matching the types

        Example:
            guardrails = await repo.get_by_types(["pii_ssn", "pii_email", "rbac"])
        """
        if not guardrail_types:
            return []

        result = await self.session.execute(
            select(Guardrail).where(Guardrail.guardrail_type.in_(guardrail_types))
        )
        return list(result.scalars().all())

    # ═══════════════════════════════════════════════════════════════════════════
    # LIST METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def list_active(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Guardrail]:
        """
        List all active guardrail definitions.

        Returns guardrails that are currently active and available for use.

        Args:
            offset: Number of records to skip (for pagination)
            limit: Maximum records to return

        Returns:
            List of active guardrails, ordered by category and display name

        Example:
            guardrails = await repo.list_active()
            for g in guardrails:
                print(f"{g.category}: {g.display_name}")

        SQL Generated:
            SELECT * FROM guardrails
            WHERE is_active = true
            ORDER BY category, display_name
            OFFSET 0 LIMIT 100
        """
        result = await self.session.execute(
            select(Guardrail)
            .where(Guardrail.is_active.is_(True))
            .order_by(Guardrail.category, Guardrail.display_name)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_category(
        self,
        category: str,
        only_active: bool = True,
    ) -> list[Guardrail]:
        """
        List guardrails by category.

        Categories are: rbac, pii, content, rate_limit

        Args:
            category: Guardrail category
            only_active: If True, only return active guardrails

        Returns:
            List of guardrails in the category

        Example:
            # Get all PII detection guardrails
            pii_guardrails = await repo.list_by_category("pii")
            # Returns: pii_credit_card, pii_ssn, pii_email, etc.

        SQL Generated:
            SELECT * FROM guardrails
            WHERE category = 'pii' AND is_active = true
            ORDER BY display_name
        """
        query = select(Guardrail).where(Guardrail.category == category)

        if only_active:
            query = query.where(Guardrail.is_active.is_(True))

        query = query.order_by(Guardrail.display_name)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_types(self, only_active: bool = True) -> list[str]:
        """
        Get all guardrail types as a list of strings.

        Useful for validation - checking if a guardrail type is valid.

        Args:
            only_active: If True, only return active guardrail types

        Returns:
            List of guardrail type identifiers

        Example:
            types = await repo.get_all_types()
            if requested_type not in types:
                raise ValidationError(f"Invalid guardrail type: {requested_type}")

        SQL Generated:
            SELECT guardrail_type FROM guardrails
            WHERE is_active = true
        """
        query = select(Guardrail.guardrail_type)

        if only_active:
            query = query.where(Guardrail.is_active.is_(True))

        result = await self.session.execute(query)
        return [row[0] for row in result.all()]

    # ═══════════════════════════════════════════════════════════════════════════
    # COUNT METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def count_active(self) -> int:
        """
        Count active guardrails.

        Returns:
            Number of active guardrails

        SQL Generated:
            SELECT COUNT(*) FROM guardrails WHERE is_active = true
        """
        result = await self.session.execute(
            select(count(Guardrail.id))
            .select_from(Guardrail)
            .where(Guardrail.is_active.is_(True))
        )
        return result.scalar() or 0

    async def count_by_category(self, category: str) -> int:
        """
        Count guardrails in a category.

        Args:
            category: Guardrail category

        Returns:
            Number of guardrails in the category

        SQL Generated:
            SELECT COUNT(*) FROM guardrails
            WHERE category = '...' AND is_active = true
        """
        result = await self.session.execute(
            select(count(Guardrail.id))
            .select_from(Guardrail)
            .where(
                Guardrail.category == category,
                Guardrail.is_active.is_(True),
            )
        )
        return result.scalar() or 0

    # ═══════════════════════════════════════════════════════════════════════════
    # VALIDATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def type_exists(self, guardrail_type: str) -> bool:
        """
        Check if a guardrail type exists.

        Used to validate guardrail types when creating policies.

        Args:
            guardrail_type: Guardrail type to check

        Returns:
            True if type exists, False otherwise

        Example:
            if not await repo.type_exists("custom_rule"):
                raise ValidationError("Invalid guardrail type")

        SQL Generated:
            SELECT COUNT(*) FROM guardrails
            WHERE guardrail_type = '...'
        """
        result = await self.session.execute(
            select(count(Guardrail.id))
            .select_from(Guardrail)
            .where(Guardrail.guardrail_type == guardrail_type)
        )
        return (result.scalar() or 0) > 0
