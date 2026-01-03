"""
Policy Repository

Database operations specific to the Policy model.
Extends BaseRepository with policy-specific query methods.

Common Operations:
==================
- get_effective_policies() → Get all policies that apply to an agent
- get_by_guardrail_type()  → Get policies for a specific guardrail type
- get_organisation_policies() → Get organisation-level policies
- get_workspace_policies() → Get workspace-level policies
- get_agent_policies()     → Get agent-level policies

Key Concept - Simplified Policy Model:
======================================
Each policy links ONE guardrail to ONE entity. No more complex merging.

Policy Scope (determined by which IDs are set):
- organisation_id only                    → Organisation-level policy
- organisation_id + mcp_server_workspace_id → Workspace-level policy
- organisation_id + mcp_server_workspace_id + agent_access_id → Agent-level policy

Policy Resolution:
==================
When evaluating a decision for an agent, we collect all applicable policies:

    get_effective_policies(org_id, workspace_id, agent_id) returns:
    [
        Policy(guardrail_type="rbac", level="organisation"),
        Policy(guardrail_type="pii_ssn", level="workspace"),
        Policy(guardrail_type="rate_limit_per_minute", level="agent"),
    ]

Each policy is independent - evaluated separately during governance decisions.

Usage in Decision Flow:
=======================
    async def load_policies_for_decision(
        db: AsyncSession,
        organisation_id: UUID,
        workspace_id: UUID,
        agent_access_id: UUID
    ) -> list[Policy]:
        repo = PolicyRepository(db)

        # Get all applicable policies for this agent
        policies = await repo.get_effective_policies(
            organisation_id=organisation_id,
            mcp_server_workspace_id=workspace_id,
            agent_access_id=agent_access_id
        )

        # Each policy is for ONE guardrail - evaluate independently
        return policies
"""

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import count

from app.db.repositories.base import BaseRepository
from app.models.guardrail import Guardrail
from app.models.policy import Policy


class PolicyRepository(BaseRepository[Policy]):
    """
    Repository for Policy database operations.

    Provides methods for policy queries, especially for loading
    all applicable policies during governance decisions.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize PolicyRepository.

        Args:
            session: Async database session
        """
        super().__init__(Policy, session)

    # ═══════════════════════════════════════════════════════════════════════════
    # DECISION-TIME QUERIES (Most Important!)
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_effective_policies(
        self,
        organisation_id: UUID,
        mcp_server_workspace_id: UUID,
        agent_access_id: UUID | None = None,
    ) -> list[Policy]:
        """
        Get all policies that apply to an agent in a workspace.

        THIS IS THE MOST IMPORTANT METHOD FOR GOVERNANCE DECISIONS.

        Returns policies from all applicable levels:
        1. Organisation-level (applies to everyone in the org)
        2. Workspace-level (applies to this workspace)
        3. Agent-level (applies to this specific agent)

        Only returns enabled policies with their guardrail eagerly loaded.

        Args:
            organisation_id: UUID of the organisation
            mcp_server_workspace_id: UUID of the workspace
            agent_access_id: Optional UUID of the agent (None = no agent-specific policies)

        Returns:
            List of policies with guardrail relationship loaded

        Example:
            policies = await repo.get_effective_policies(
                organisation_id=org.id,
                mcp_server_workspace_id=workspace.id,
                agent_access_id=agent.id
            )
            # Returns all policies at all levels for this agent

        SQL Generated:
            SELECT * FROM policies
            WHERE organisation_id = '...'
              AND deleted_at IS NULL
              AND is_enabled = true
              AND (
                (mcp_server_workspace_id IS NULL AND agent_access_id IS NULL)  -- Org level
                OR (mcp_server_workspace_id = '...' AND agent_access_id IS NULL)  -- Workspace level
                OR (mcp_server_workspace_id = '...' AND agent_access_id = '...')  -- Agent level
              )
        """
        # Base conditions that apply to all policy levels
        conditions = [
            Policy.organisation_id == organisation_id,
            Policy.deleted_at.is_(None),  # Not soft-deleted
            Policy.is_enabled.is_(True),  # Only enabled policies
        ]

        # Build OR conditions for each policy level
        level_conditions = [
            # Level 1: Organisation-level policies (no workspace, no agent)
            and_(
                Policy.mcp_server_workspace_id.is_(None),
                Policy.agent_access_id.is_(None),
            ),
            # Level 2: Workspace-level policies (this workspace, no agent)
            and_(
                Policy.mcp_server_workspace_id == mcp_server_workspace_id,
                Policy.agent_access_id.is_(None),
            ),
        ]

        # Level 3: Agent-level policies (only if agent_access_id provided)
        if agent_access_id:
            level_conditions.append(
                and_(
                    Policy.mcp_server_workspace_id == mcp_server_workspace_id,
                    Policy.agent_access_id == agent_access_id,
                )
            )

        result = await self.session.execute(
            select(Policy)
            .options(joinedload(Policy.guardrail))  # Eager load guardrail
            .where(
                and_(*conditions),  # All base conditions
                or_(*level_conditions),  # Any of the level conditions
            )
            .order_by(Policy.created_at.desc())
        )
        return list(result.scalars().unique().all())

    async def get_by_guardrail_type(
        self,
        organisation_id: UUID,
        guardrail_type: str,
        mcp_server_workspace_id: UUID | None = None,
        agent_access_id: UUID | None = None,
    ) -> list[Policy]:
        """
        Get policies for a specific guardrail type.

        Useful when you need to find all policies for a particular
        guardrail (e.g., all PII SSN detection policies).

        Args:
            organisation_id: UUID of the organisation
            guardrail_type: The guardrail type (e.g., "pii_ssn", "rbac")
            mcp_server_workspace_id: Optional workspace filter
            agent_access_id: Optional agent filter

        Returns:
            List of policies for this guardrail type
        """
        query = (
            select(Policy)
            .join(Guardrail, Policy.guardrail_id == Guardrail.id)
            .where(
                Policy.organisation_id == organisation_id,
                Guardrail.guardrail_type == guardrail_type,
                Policy.deleted_at.is_(None),
            )
        )

        if mcp_server_workspace_id:
            query = query.where(
                Policy.mcp_server_workspace_id == mcp_server_workspace_id
            )

        if agent_access_id:
            query = query.where(Policy.agent_access_id == agent_access_id)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ═══════════════════════════════════════════════════════════════════════════
    # LEVEL-SPECIFIC QUERIES
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_organisation_policies(
        self,
        organisation_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Policy]:
        """
        Get organisation-level policies only.

        These are organization-wide default policies that apply
        to all workspaces and all agents.

        Args:
            organisation_id: UUID of the organisation
            offset: Pagination offset
            limit: Max records to return

        Returns:
            List of organisation-level policies

        Example:
            org_policies = await repo.get_organisation_policies(org.id)
            # Returns only policies where workspace_id=NULL and agent_id=NULL

        SQL Generated:
            SELECT * FROM policies
            WHERE organisation_id = '...'
              AND mcp_server_workspace_id IS NULL
              AND agent_access_id IS NULL
              AND deleted_at IS NULL
            ORDER BY created_at DESC
        """
        result = await self.session.execute(
            select(Policy)
            .options(joinedload(Policy.guardrail))
            .where(
                Policy.organisation_id == organisation_id,
                Policy.mcp_server_workspace_id.is_(None),  # No workspace = org level
                Policy.agent_access_id.is_(None),  # No agent = not agent-specific
                Policy.deleted_at.is_(None),
            )
            .order_by(Policy.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().unique().all())

    async def count_organisation_policies(self, organisation_id: UUID) -> int:
        """Count organisation-level policies."""
        result = await self.session.execute(
            select(count(Policy.id))
            .select_from(Policy)
            .where(
                Policy.organisation_id == organisation_id,
                Policy.mcp_server_workspace_id.is_(None),
                Policy.agent_access_id.is_(None),
                Policy.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    async def get_workspace_policies(
        self,
        mcp_server_workspace_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Policy]:
        """
        Get workspace-level policies.

        Returns policies attached to a specific workspace
        (NOT agent-level policies within that workspace).

        Args:
            mcp_server_workspace_id: UUID of the workspace
            offset: Pagination offset
            limit: Max records to return

        Returns:
            List of workspace-level policies

        SQL Generated:
            SELECT * FROM policies
            WHERE mcp_server_workspace_id = '...'
              AND agent_access_id IS NULL
              AND deleted_at IS NULL
        """
        result = await self.session.execute(
            select(Policy)
            .options(joinedload(Policy.guardrail))
            .where(
                Policy.mcp_server_workspace_id == mcp_server_workspace_id,
                Policy.agent_access_id.is_(None),  # Workspace level only
                Policy.deleted_at.is_(None),
            )
            .order_by(Policy.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().unique().all())

    async def count_workspace_policies(self, mcp_server_workspace_id: UUID) -> int:
        """Count workspace-level policies."""
        result = await self.session.execute(
            select(count(Policy.id))
            .select_from(Policy)
            .where(
                Policy.mcp_server_workspace_id == mcp_server_workspace_id,
                Policy.agent_access_id.is_(None),
                Policy.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    async def get_agent_policies(
        self,
        agent_access_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Policy]:
        """
        Get agent-specific policies.

        Returns policies that target a specific agent.
        These are the most specific policies.

        Args:
            agent_access_id: UUID of the agent access
            offset: Pagination offset
            limit: Max records to return

        Returns:
            List of agent-specific policies

        SQL Generated:
            SELECT * FROM policies
            WHERE agent_access_id = '...'
              AND deleted_at IS NULL
        """
        result = await self.session.execute(
            select(Policy)
            .options(joinedload(Policy.guardrail))
            .where(
                Policy.agent_access_id == agent_access_id,
                Policy.deleted_at.is_(None),
            )
            .order_by(Policy.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().unique().all())

    async def count_agent_policies(self, agent_access_id: UUID) -> int:
        """Count agent-specific policies."""
        result = await self.session.execute(
            select(count(Policy.id))
            .select_from(Policy)
            .where(
                Policy.agent_access_id == agent_access_id,
                Policy.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    # ═══════════════════════════════════════════════════════════════════════════
    # ALL POLICIES FOR AN ENTITY
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_all_for_workspace(
        self,
        mcp_server_workspace_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Policy]:
        """
        Get all policies for a workspace.

        Returns both workspace-level and agent-level policies
        within this workspace (NOT organisation-level policies).

        Args:
            mcp_server_workspace_id: UUID of the workspace
            offset: Pagination offset
            limit: Max records to return

        Returns:
            List of all policies for this workspace

        SQL Generated:
            SELECT * FROM policies
            WHERE mcp_server_workspace_id = '...'
              AND deleted_at IS NULL
            ORDER BY created_at DESC
        """
        result = await self.session.execute(
            select(Policy)
            .options(joinedload(Policy.guardrail))
            .where(
                Policy.mcp_server_workspace_id == mcp_server_workspace_id,
                Policy.deleted_at.is_(None),
            )
            .order_by(Policy.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().unique().all())

    async def count_all_for_workspace(self, mcp_server_workspace_id: UUID) -> int:
        """Count all policies for a workspace."""
        result = await self.session.execute(
            select(count(Policy.id))
            .select_from(Policy)
            .where(
                Policy.mcp_server_workspace_id == mcp_server_workspace_id,
                Policy.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    # ═══════════════════════════════════════════════════════════════════════════
    # VALIDATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def policy_exists_for_guardrail(
        self,
        guardrail_id: UUID,
        organisation_id: UUID,
        mcp_server_workspace_id: UUID | None = None,
        agent_access_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> bool:
        """
        Check if a policy already exists for a guardrail at the given level.

        Used to prevent duplicate policies for the same guardrail
        at the same level.

        Args:
            guardrail_id: UUID of the guardrail
            organisation_id: UUID of the organisation
            mcp_server_workspace_id: Optional workspace ID
            agent_access_id: Optional agent ID
            exclude_id: Optional policy ID to exclude (for updates)

        Returns:
            True if policy exists, False otherwise
        """
        query = (
            select(count(Policy.id))
            .select_from(Policy)
            .where(
                Policy.guardrail_id == guardrail_id,
                Policy.organisation_id == organisation_id,
                Policy.deleted_at.is_(None),
            )
        )

        # Match the exact level
        if mcp_server_workspace_id:
            query = query.where(
                Policy.mcp_server_workspace_id == mcp_server_workspace_id
            )
        else:
            query = query.where(Policy.mcp_server_workspace_id.is_(None))

        if agent_access_id:
            query = query.where(Policy.agent_access_id == agent_access_id)
        else:
            query = query.where(Policy.agent_access_id.is_(None))

        if exclude_id:
            query = query.where(Policy.id != exclude_id)

        result = await self.session.execute(query)
        return (result.scalar() or 0) > 0
