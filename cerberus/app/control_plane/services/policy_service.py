"""
Policy Service

Business logic for policy management.

Simplified policy model:
- Each policy links ONE guardrail to ONE entity
- Policy levels: organisation, workspace, agent
- No priority-based merging - policies are independent
"""

from datetime import datetime, timezone
from typing import Any, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.policy_cache import policy_cache
from app.config.constants import (
    GuardrailType,
    PolicyAction,
    PolicyLevel,
    validate_guardrail_config,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.repositories import GuardrailRepository, PolicyRepository
from app.models.policy import Policy
from app.schemas.policy import (
    EffectivePolicyResponse,
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
)


class PolicyService:
    """Service for policy operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PolicyRepository(session)
        self.guardrail_repo = GuardrailRepository(session)

    async def create_policy(
        self,
        data: PolicyCreate,
    ) -> PolicyResponse:
        """Create a new policy.

        Args:
            data: PolicyCreate schema with all policy details

        Returns:
            Created policy response

        Raises:
            NotFoundError: If guardrail not found
            ConflictError: If policy already exists for same guardrail at same level
        """
        # Validate guardrail exists
        guardrail = await self.guardrail_repo.get(UUID(data.guardrail_id))
        if not guardrail:
            raise NotFoundError(f"Guardrail with ID '{data.guardrail_id}' not found")

        # Parse UUIDs
        organisation_uuid = UUID(data.organisation_id)
        workspace_uuid = (
            UUID(data.mcp_server_workspace_id)
            if data.mcp_server_workspace_id
            else None
        )
        agent_uuid = (
            UUID(data.agent_access_id) if data.agent_access_id else None
        )

        # Check for duplicate policy (same guardrail at same level)
        duplicate_exists = await self.repo.policy_exists_for_guardrail(
            guardrail_id=guardrail.id,
            organisation_id=organisation_uuid,
            mcp_server_workspace_id=workspace_uuid,
            agent_access_id=agent_uuid,
        )
        if duplicate_exists:
            level = data.level.value
            raise ConflictError(
                f"A policy for guardrail '{guardrail.guardrail_type}' already exists "
                f"at the {level} level"
            )

        # Validate policy config against guardrail type schema
        if data.config:
            guardrail_type = GuardrailType(guardrail.guardrail_type)
            is_valid, error = validate_guardrail_config(
                guardrail_type, data.config, strict=True
            )
            if not is_valid:
                raise ValidationError(error)

        # Create the policy
        policy = await self.repo.create(
            organisation_id=organisation_uuid,
            mcp_server_workspace_id=workspace_uuid,
            agent_access_id=agent_uuid,
            guardrail_id=guardrail.id,
            name=data.name,
            description=data.description,
            config=data.config or {},
            action=data.action.value,
            is_enabled=data.is_enabled,
        )

        # Invalidate cache based on policy level
        await self._invalidate_cache(policy)

        return await self._to_response(policy)

    async def get_policy(self, policy_id: UUID) -> Optional[PolicyResponse]:
        """Get policy by ID.

        Args:
            policy_id: Policy UUID

        Returns:
            Policy response or None
        """
        policy = await self.repo.get(policy_id)
        if not policy or policy.deleted_at:
            return None

        return await self._to_response(policy)

    async def list_organisation_policies(
        self,
        organisation_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> Tuple[list[PolicyResponse], int]:
        """List organisation-level policies.

        Args:
            organisation_id: Organisation UUID
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (policies, total_count)
        """
        policies = await self.repo.get_organisation_policies(
            organisation_id, offset=offset, limit=limit
        )
        total = await self.repo.count_organisation_policies(organisation_id)

        responses = [await self._to_response(p) for p in policies]
        return responses, total

    async def list_workspace_policies(
        self,
        mcp_server_workspace_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> Tuple[list[PolicyResponse], int]:
        """List workspace-level policies.

        Args:
            mcp_server_workspace_id: Workspace UUID
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (policies, total_count)
        """
        policies = await self.repo.get_workspace_policies(
            mcp_server_workspace_id, offset=offset, limit=limit
        )
        total = await self.repo.count_workspace_policies(mcp_server_workspace_id)

        responses = [await self._to_response(p) for p in policies]
        return responses, total

    async def list_agent_policies(
        self,
        agent_access_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> Tuple[list[PolicyResponse], int]:
        """List agent-level policies.

        Args:
            agent_access_id: Agent access UUID
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (policies, total_count)
        """
        policies = await self.repo.get_agent_policies(
            agent_access_id, offset=offset, limit=limit
        )
        total = await self.repo.count_agent_policies(agent_access_id)

        responses = [await self._to_response(p) for p in policies]
        return responses, total

    async def update_policy(
        self,
        policy_id: UUID,
        data: PolicyUpdate,
    ) -> Optional[PolicyResponse]:
        """Update policy.

        Args:
            policy_id: Policy UUID
            data: PolicyUpdate schema

        Returns:
            Updated policy response or None
        """
        policy = await self.repo.get(policy_id)
        if not policy or policy.deleted_at:
            return None

        update_kwargs: dict[str, Any] = {}
        if data.name is not None:
            update_kwargs["name"] = data.name
        if data.description is not None:
            update_kwargs["description"] = data.description
        if data.config is not None:
            # Validate config against guardrail type schema
            guardrail = await self.guardrail_repo.get(policy.guardrail_id)
            if guardrail:
                guardrail_type = GuardrailType(guardrail.guardrail_type)
                is_valid, error = validate_guardrail_config(
                    guardrail_type, data.config, strict=True
                )
                if not is_valid:
                    raise ValidationError(error)
            update_kwargs["config"] = data.config
        if data.action is not None:
            update_kwargs["action"] = data.action.value
        if data.is_enabled is not None:
            update_kwargs["is_enabled"] = data.is_enabled

        if not update_kwargs:
            return await self._to_response(policy)

        updated_policy = await self.repo.update(policy_id, **update_kwargs)
        if not updated_policy:
            return None

        # Invalidate cache
        await self._invalidate_cache(updated_policy)

        return await self._to_response(updated_policy)

    async def delete_policy(self, policy_id: UUID) -> bool:
        """Soft delete policy.

        Args:
            policy_id: Policy UUID

        Returns:
            True if deleted
        """
        policy = await self.repo.get(policy_id)
        if not policy:
            return False

        result = await self.repo.soft_delete(policy_id)

        if result:
            await self._invalidate_cache(policy)

        return result is not None

    async def get_effective_policies(
        self,
        organisation_id: UUID,
        mcp_server_workspace_id: UUID,
        agent_access_id: Optional[UUID] = None,
    ) -> EffectivePolicyResponse:
        """Get all effective policies for an agent.

        Returns all applicable policies from all levels:
        - Organisation level
        - Workspace level
        - Agent level (if agent_access_id provided)

        Args:
            organisation_id: Organisation UUID
            mcp_server_workspace_id: Workspace UUID
            agent_access_id: Optional agent access UUID

        Returns:
            Effective policies response
        """
        # Check cache first
        cached = await policy_cache.get_effective_policy(
            str(organisation_id),
            str(mcp_server_workspace_id),
            str(agent_access_id) if agent_access_id else None,
        )
        if cached:
            return EffectivePolicyResponse(**cached)

        # Get all applicable policies
        policies = await self.repo.get_effective_policies(
            organisation_id, mcp_server_workspace_id, agent_access_id
        )

        # Build response
        policy_responses = [await self._to_response(p) for p in policies]

        result = EffectivePolicyResponse(
            organisation_id=str(organisation_id),
            mcp_server_workspace_id=str(mcp_server_workspace_id),
            agent_access_id=str(agent_access_id) if agent_access_id else None,
            policies=policy_responses,
            computed_at=datetime.now(timezone.utc),
        )

        # Cache the result
        await policy_cache.set_effective_policy(
            str(organisation_id),
            str(mcp_server_workspace_id),
            str(agent_access_id) if agent_access_id else None,
            result.model_dump(mode="json"),
        )

        return result

    async def _invalidate_cache(self, policy: Policy) -> None:
        """Invalidate cache based on policy level."""
        if policy.mcp_server_workspace_id:
            await policy_cache.invalidate_workspace(
                str(policy.organisation_id), str(policy.mcp_server_workspace_id)
            )
        else:
            await policy_cache.invalidate_tenant(str(policy.organisation_id))

    async def _to_response(self, policy: Policy) -> PolicyResponse:
        """Convert model to response schema."""
        # Determine policy level
        if policy.agent_access_id:
            level = PolicyLevel.AGENT
        elif policy.mcp_server_workspace_id:
            level = PolicyLevel.WORKSPACE
        else:
            level = PolicyLevel.ORGANISATION

        # Get guardrail info (type and display_name)
        guardrail = await self.guardrail_repo.get(policy.guardrail_id)
        guardrail_type = guardrail.guardrail_type if guardrail else "unknown"
        guardrail_display_name = guardrail.display_name if guardrail else "Unknown"

        return PolicyResponse(
            id=str(policy.id),
            organisation_id=str(policy.organisation_id),
            mcp_server_workspace_id=(
                str(policy.mcp_server_workspace_id)
                if policy.mcp_server_workspace_id
                else None
            ),
            agent_access_id=(
                str(policy.agent_access_id) if policy.agent_access_id else None
            ),
            guardrail_id=str(policy.guardrail_id),
            guardrail_type=guardrail_type,
            guardrail_display_name=guardrail_display_name,
            name=policy.name,
            description=policy.description,
            config=policy.config,
            action=PolicyAction(policy.action),
            is_enabled=policy.is_enabled,
            level=level,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
