"""
Guardrail Service

Business logic for guardrail definition management.

Guardrails are atomic security checks that can be attached to entities
via policies. This service manages the guardrail definitions themselves,
not the policies that use them.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import (
    GUARDRAIL_CATEGORIES,
    GUARDRAIL_DEFAULTS,
    GUARDRAIL_METADATA,
    GuardrailCategory,
    GuardrailType,
    validate_guardrail_config,
)
from app.core.exceptions import ConflictError, ValidationError
from app.db.repositories import GuardrailRepository
from app.schemas.guardrail import (
    GuardrailDefinitionCreate,
    GuardrailDefinitionResponse,
    GuardrailDefinitionUpdate,
)


class GuardrailService:
    """Service for guardrail definition operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = GuardrailRepository(session)

    async def create_guardrail(
        self,
        data: GuardrailDefinitionCreate,
    ) -> GuardrailDefinitionResponse:
        """Create a new guardrail definition.

        Note: This is typically only used by admins to seed the system.
        Normal users attach existing guardrails to entities via policies.

        Auto-fills from constants if not provided:
        - default_config: Uses GUARDRAIL_DEFAULTS for the guardrail type
        - category: Validated against GUARDRAIL_CATEGORIES (must match expected)
        - display_name/description: Uses GUARDRAIL_METADATA if available

        Args:
            data: Guardrail definition data

        Returns:
            Created guardrail response

        Raises:
            ConflictError: If guardrail type already exists
            ValidationError: If category doesn't match expected for guardrail type
        """
        # Check if type already exists
        if await self.repo.type_exists(data.guardrail_type.value):
            raise ConflictError(
                f"Guardrail with type '{data.guardrail_type.value}' already exists"
            )

        # Validate category matches expected category for this guardrail type
        expected_category = GUARDRAIL_CATEGORIES.get(data.guardrail_type)
        if expected_category and data.category != expected_category:
            raise ValidationError(
                f"Guardrail type '{data.guardrail_type.value}' must have category "
                f"'{expected_category.value}', not '{data.category.value}'"
            )

        # Use GUARDRAIL_DEFAULTS if no config provided
        default_config = data.default_config
        if not default_config:
            default_config = GUARDRAIL_DEFAULTS.get(data.guardrail_type, {})
        else:
            # Validate config against schema if custom config provided
            is_valid, error = validate_guardrail_config(
                data.guardrail_type, default_config, strict=True
            )
            if not is_valid:
                raise ValidationError(error)

        # Use GUARDRAIL_METADATA for display_name/description if not provided
        metadata = GUARDRAIL_METADATA.get(data.guardrail_type, {})
        display_name = data.display_name or metadata.get(
            "display_name", data.guardrail_type.value
        )
        description = data.description or metadata.get("description")

        guardrail = await self.repo.create(
            guardrail_type=data.guardrail_type.value,
            display_name=display_name,
            description=description,
            category=data.category.value,
            default_config=default_config,
            is_active=data.is_active,
        )

        return self._to_response(guardrail)

    async def get_guardrail(
        self, guardrail_id: UUID
    ) -> Optional[GuardrailDefinitionResponse]:
        """Get guardrail by ID.

        Args:
            guardrail_id: Guardrail UUID

        Returns:
            Guardrail response or None
        """
        guardrail = await self.repo.get(guardrail_id)
        if not guardrail:
            return None

        return self._to_response(guardrail)

    async def get_guardrail_by_type(
        self, guardrail_type: str
    ) -> Optional[GuardrailDefinitionResponse]:
        """Get guardrail by type.

        Args:
            guardrail_type: Guardrail type identifier

        Returns:
            Guardrail response or None
        """
        guardrail = await self.repo.get_by_type(guardrail_type)
        if not guardrail:
            return None

        return self._to_response(guardrail)

    async def list_guardrails(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[GuardrailDefinitionResponse], int]:
        """List all active guardrails.

        Args:
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (guardrails, total_count)
        """
        guardrails = await self.repo.list_active(offset=offset, limit=limit)
        total = await self.repo.count_active()

        return [self._to_response(g) for g in guardrails], total

    async def list_by_category(
        self,
        category: GuardrailCategory,
        only_active: bool = True,
    ) -> tuple[list[GuardrailDefinitionResponse], int]:
        """List guardrails by category.

        Args:
            category: Guardrail category (rbac, pii, content, rate_limit)
            only_active: Only return active guardrails

        Returns:
            Tuple of (guardrails, total_count)
        """
        guardrails = await self.repo.list_by_category(
            category.value, only_active=only_active
        )
        total = await self.repo.count_by_category(category.value)
        return [self._to_response(g) for g in guardrails], total

    async def update_guardrail(
        self,
        guardrail_id: UUID,
        data: GuardrailDefinitionUpdate,
    ) -> Optional[GuardrailDefinitionResponse]:
        """Update guardrail definition.

        Args:
            guardrail_id: Guardrail UUID
            data: Update data

        Returns:
            Updated guardrail response or None
        """
        guardrail = await self.repo.get(guardrail_id)
        if not guardrail:
            return None

        update_data: dict = {}
        if data.display_name is not None:
            update_data["display_name"] = data.display_name
        if data.description is not None:
            update_data["description"] = data.description
        if data.default_config is not None:
            # Validate config against schema
            guardrail_type = GuardrailType(guardrail.guardrail_type)
            is_valid, error = validate_guardrail_config(
                guardrail_type, data.default_config, strict=True
            )
            if not is_valid:
                raise ValidationError(error)
            update_data["default_config"] = data.default_config
        if data.is_active is not None:
            update_data["is_active"] = data.is_active

        if not update_data:
            return self._to_response(guardrail)

        updated = await self.repo.update(guardrail_id, **update_data)
        if not updated:
            return None

        return self._to_response(updated)

    async def delete_guardrail(self, guardrail_id: UUID) -> bool:
        """Delete guardrail definition.

        Args:
            guardrail_id: Guardrail UUID

        Returns:
            True if deleted, False if not found
        """
        guardrail = await self.repo.get(guardrail_id)
        if not guardrail:
            return False

        await self.repo.delete(guardrail_id)
        return True

    def _to_response(self, guardrail) -> GuardrailDefinitionResponse:
        """Convert model to response schema."""
        return GuardrailDefinitionResponse(
            id=str(guardrail.id),
            guardrail_type=GuardrailType(guardrail.guardrail_type),
            display_name=guardrail.display_name,
            description=guardrail.description,
            category=GuardrailCategory(guardrail.category),
            default_config=guardrail.default_config,
            is_active=guardrail.is_active,
            created_at=guardrail.created_at,
            updated_at=guardrail.updated_at,
        )
