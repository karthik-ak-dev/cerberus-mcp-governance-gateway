"""
Agent Access Repository

Database operations for the AgentAccess model.
Extends BaseRepository with key-specific query methods.

Key Concept - Hash-Based Lookup:
================================
We NEVER store the actual key, only its SHA-256 hash.

    When created:
        actual_key = "za-abc123xyz789..."
        key_hash = SHA256(actual_key) = "a1b2c3d4..."
        → Store: key_hash in database
        → Return: actual_key to user (shown only ONCE)

    When authenticating:
        Request: Authorization: Bearer za-abc123xyz789...
        → Compute: SHA256("za-abc123xyz789...") = "a1b2c3d4..."
        → Query: SELECT * FROM agent_accesses WHERE key_hash = "a1b2c3d4..."
        → Found? → Authenticated!

Agent Access vs User Access Keys:
=================================
Unlike the old UserAccessKey model, AgentAccess is NOT tied to a User.
Agents are standalone entities scoped directly to an MCP Server Workspace.

    AgentAccess:
    - Belongs to: MCP Server Workspace (not User)
    - Used by: AI agents connecting through Cerberus Gateway
    - Derives: organisation_id from workspace.organisation_id
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import count

from app.db.repositories.base import BaseRepository
from app.models.agent_access import AgentAccess
from app.models.mcp_server_workspace import McpServerWorkspace


class AgentAccessRepository(BaseRepository[AgentAccess]):
    """
    Repository for AgentAccess database operations.

    Provides methods for:
    - Authentication (lookup by hash with eager loading of workspace)
    - Validation (check active, not expired, not revoked)
    - Lifecycle management (revoke, update usage)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize AgentAccessRepository."""
        super().__init__(AgentAccess, session)

    # ═══════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION METHODS (Critical Path!)
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_valid_key_with_context(
        self, key_hash: str
    ) -> AgentAccess | None:
        """
        Get a valid agent access key with workspace eagerly loaded.

        This is the primary authentication method for the gateway.
        Returns the agent access with all relationships needed to derive context.

        The context includes:
        - mcp_server_workspace: The workspace this agent can access
        - organisation_id: Derived from workspace.organisation_id
        - mcp_server_url: The target MCP server URL

        Args:
            key_hash: SHA-256 hash of the key

        Returns:
            Valid AgentAccess with workspace loaded, or None
        """
        result = await self.session.execute(
            select(AgentAccess)
            .options(
                joinedload(AgentAccess.mcp_server_workspace),
            )
            .where(
                AgentAccess.key_hash == key_hash,
                AgentAccess.is_active.is_(True),
                AgentAccess.is_revoked.is_(False),
            )
        )
        agent_access = result.scalar_one_or_none()

        # Check expiration
        if agent_access and agent_access.is_expired:
            return None

        return agent_access

    async def get_by_hash(self, key_hash: str) -> AgentAccess | None:
        """
        Get agent access by its SHA-256 hash (basic lookup without relationships).

        Args:
            key_hash: SHA-256 hash of the key

        Returns:
            AgentAccess if found and active, None otherwise
        """
        result = await self.session.execute(
            select(AgentAccess).where(
                AgentAccess.key_hash == key_hash,
                AgentAccess.is_active.is_(True),
                AgentAccess.is_revoked.is_(False),
            )
        )
        return result.scalar_one_or_none()

    # ═══════════════════════════════════════════════════════════════════════════
    # USAGE TRACKING
    # ═══════════════════════════════════════════════════════════════════════════

    async def update_usage(self, agent_access_id: UUID) -> None:
        """
        Update last used timestamp and increment usage count.

        Called after successful authentication.
        """
        await self.session.execute(
            update(AgentAccess)
            .where(AgentAccess.id == agent_access_id)
            .values(
                last_used_at=datetime.now(UTC),
                usage_count=AgentAccess.usage_count + 1,
            )
        )
        await self.session.flush()

    # ═══════════════════════════════════════════════════════════════════════════
    # LIST METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_by_workspace(
        self,
        mcp_server_workspace_id: UUID,
        offset: int = 0,
        limit: int = 100,
        include_revoked: bool = False,
        include_inactive: bool = False,
    ) -> list[AgentAccess]:
        """
        Get agent accesses for a specific workspace.

        Uses ix_agent_accesses_workspace_status composite index for efficient
        filtering by (mcp_server_workspace_id, is_active, is_revoked).

        Args:
            mcp_server_workspace_id: UUID of the workspace
            offset: Pagination offset
            limit: Max records to return
            include_revoked: If True, include revoked accesses
            include_inactive: If True, include inactive accesses

        Returns:
            List of agent accesses for the workspace
        """
        # Build query to leverage composite index
        # ix_agent_accesses_workspace_status(mcp_server_workspace_id, is_active, is_revoked)
        query = select(AgentAccess).where(
            AgentAccess.mcp_server_workspace_id == mcp_server_workspace_id
        )

        # Filter by is_active first (matches index order)
        if not include_inactive:
            query = query.where(AgentAccess.is_active.is_(True))

        if not include_revoked:
            query = query.where(AgentAccess.is_revoked.is_(False))

        query = (
            query.order_by(AgentAccess.created_at.desc()).offset(offset).limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_organisation(
        self,
        organisation_id: UUID,
        offset: int = 0,
        limit: int = 100,
        include_revoked: bool = False,
    ) -> list[AgentAccess]:
        """
        Get all agent accesses for an organisation (via workspace relationship).

        Args:
            organisation_id: UUID of the organisation
            offset: Pagination offset
            limit: Max records to return
            include_revoked: If True, include revoked accesses

        Returns:
            List of agent accesses for the organisation
        """
        query = (
            select(AgentAccess)
            .join(
                McpServerWorkspace,
                AgentAccess.mcp_server_workspace_id == McpServerWorkspace.id,
            )
            .where(McpServerWorkspace.organisation_id == organisation_id)
        )

        if not include_revoked:
            query = query.where(AgentAccess.is_revoked.is_(False))

        query = (
            query.order_by(AgentAccess.created_at.desc()).offset(offset).limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ═══════════════════════════════════════════════════════════════════════════
    # COUNT METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def count_by_workspace(
        self,
        mcp_server_workspace_id: UUID,
        include_revoked: bool = False,
        include_inactive: bool = False,
    ) -> int:
        """
        Count agent accesses for a workspace.

        Uses ix_agent_accesses_workspace_status composite index.
        """
        query = (
            select(count(AgentAccess.id))
            .select_from(AgentAccess)
            .where(AgentAccess.mcp_server_workspace_id == mcp_server_workspace_id)
        )

        if not include_inactive:
            query = query.where(AgentAccess.is_active.is_(True))

        if not include_revoked:
            query = query.where(AgentAccess.is_revoked.is_(False))

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def count_by_organisation(
        self,
        organisation_id: UUID,
        include_revoked: bool = False,
    ) -> int:
        """Count agent accesses for an organisation."""
        query = (
            select(count(AgentAccess.id))
            .select_from(AgentAccess)
            .join(
                McpServerWorkspace,
                AgentAccess.mcp_server_workspace_id == McpServerWorkspace.id,
            )
            .where(McpServerWorkspace.organisation_id == organisation_id)
        )

        if not include_revoked:
            query = query.where(AgentAccess.is_revoked.is_(False))

        result = await self.session.execute(query)
        return result.scalar() or 0

    # ═══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def revoke(self, agent_access_id: UUID) -> AgentAccess | None:
        """
        Permanently revoke an agent access.

        Revocation is PERMANENT - a revoked access cannot be reactivated.

        Args:
            agent_access_id: UUID of the agent access to revoke

        Returns:
            Revoked agent access or None if not found
        """
        agent_access = await self.get(agent_access_id)
        if not agent_access:
            return None

        agent_access.is_revoked = True
        agent_access.is_active = False

        await self.session.flush()
        await self.session.refresh(agent_access)

        return agent_access
