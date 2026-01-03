"""
Agent Access Service

Business logic for agent access key management.

Agents use AgentAccess keys to connect through Cerberus Gateway to MCP servers.
Unlike the old UserAccessKey model, AgentAccess is NOT tied to a User.
Agents are standalone entities scoped directly to an MCP Server Workspace.

Access Control:
- Agent permissions are controlled entirely by Policies and Guardrails
- No "scopes" field - RBAC guardrail controls tool access
- Rate limiting guardrails control request limits
- PII/Content guardrails control data handling
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key, get_api_key_prefix
from app.db.repositories import AgentAccessRepository, McpServerWorkspaceRepository
from app.schemas.agent_access import (
    AgentAccessCreatedResponse,
    AgentAccessResponse,
    AgentAccessRotateResponse,
)


class AgentAccessService:
    """Service for agent access operations.

    Agent permissions are controlled by Policies and Guardrails, not scopes.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AgentAccessRepository(session)
        self.workspace_repo = McpServerWorkspaceRepository(session)

    async def create_agent_access(
        self,
        mcp_server_workspace_id: UUID,
        name: str,
        description: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentAccessCreatedResponse:
        """Create a new agent access key.

        Args:
            mcp_server_workspace_id: Workspace UUID this agent can access
            name: Agent name (e.g., "Production AI Agent")
            description: Optional description
            expires_at: Optional expiration
            metadata: Optional custom metadata

        Returns:
            Created agent access with the actual key value (shown only once!)

        Raises:
            ValueError: If workspace not found
        """
        # Validate workspace exists
        workspace = await self.workspace_repo.get(mcp_server_workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")

        # Generate key with "ca-" prefix (Cerberus Agent)
        plain_key, key_hash = generate_api_key(prefix="ca-")
        key_prefix = get_api_key_prefix(plain_key)

        agent_access = await self.repo.create(
            mcp_server_workspace_id=mcp_server_workspace_id,
            name=name,
            description=description,
            key_hash=key_hash,
            key_prefix=key_prefix,
            expires_at=expires_at,
            metadata_=metadata or {},
        )

        return AgentAccessCreatedResponse(
            id=str(agent_access.id),
            key=plain_key,  # Only returned once!
            mcp_server_workspace_id=str(agent_access.mcp_server_workspace_id),
            organisation_id=str(workspace.organisation_id),
            name=agent_access.name,
            description=agent_access.description,
            key_prefix=agent_access.key_prefix,
            expires_at=agent_access.expires_at,
            created_at=agent_access.created_at,
        )

    async def get_agent_access(
        self, agent_access_id: UUID
    ) -> Optional[AgentAccessResponse]:
        """Get agent access by ID.

        Args:
            agent_access_id: Agent access UUID

        Returns:
            Agent access response or None (also None if revoked)
        """
        agent_access = await self.repo.get(agent_access_id)
        if not agent_access:
            return None

        # Revoked keys should not be accessible via GET
        if agent_access.is_revoked:
            return None

        # Load workspace to get organisation_id
        workspace = await self.workspace_repo.get(
            agent_access.mcp_server_workspace_id
        )
        organisation_id = str(workspace.organisation_id) if workspace else ""

        return self._to_response(agent_access, organisation_id)

    async def list_agent_accesses_by_workspace(
        self,
        mcp_server_workspace_id: UUID,
        offset: int = 0,
        limit: int = 100,
        include_revoked: bool = False,
    ) -> Tuple[list[AgentAccessResponse], int]:
        """List agent accesses for a workspace.

        Args:
            mcp_server_workspace_id: Workspace UUID
            offset: Pagination offset
            limit: Pagination limit
            include_revoked: Include revoked accesses

        Returns:
            Tuple of (agent_accesses, total_count)
        """
        # Get workspace to get organisation_id
        workspace = await self.workspace_repo.get(mcp_server_workspace_id)
        organisation_id = str(workspace.organisation_id) if workspace else ""

        accesses = await self.repo.get_by_workspace(
            mcp_server_workspace_id,
            offset=offset,
            limit=limit,
            include_revoked=include_revoked,
        )
        total = await self.repo.count_by_workspace(
            mcp_server_workspace_id, include_revoked
        )

        return [self._to_response(a, organisation_id) for a in accesses], total

    async def list_agent_accesses_by_organisation(
        self,
        organisation_id: UUID,
        offset: int = 0,
        limit: int = 100,
        include_revoked: bool = False,
    ) -> Tuple[list[AgentAccessResponse], int]:
        """List agent accesses for an organisation.

        Args:
            organisation_id: Organisation UUID
            offset: Pagination offset
            limit: Pagination limit
            include_revoked: Include revoked accesses

        Returns:
            Tuple of (agent_accesses, total_count)
        """
        accesses = await self.repo.get_by_organisation(
            organisation_id,
            offset=offset,
            limit=limit,
            include_revoked=include_revoked,
        )
        total = await self.repo.count_by_organisation(organisation_id, include_revoked)

        return [self._to_response(a, str(organisation_id)) for a in accesses], total

    async def update_agent_access(
        self,
        agent_access_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[AgentAccessResponse]:
        """Update agent access.

        Args:
            agent_access_id: Agent access UUID
            name: Optional new name
            description: Optional new description
            is_active: Optional active status
            metadata: Optional new metadata

        Returns:
            Updated agent access response or None (also None if revoked)
        """
        agent_access = await self.repo.get(agent_access_id)
        if not agent_access:
            return None

        # Revoked keys cannot be updated
        if agent_access.is_revoked:
            return None

        update_data: dict[str, Any] = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if is_active is not None:
            update_data["is_active"] = is_active
        if metadata is not None:
            update_data["metadata_"] = metadata

        if not update_data:
            # No updates to apply
            workspace = await self.workspace_repo.get(
                agent_access.mcp_server_workspace_id
            )
            organisation_id = str(workspace.organisation_id) if workspace else ""
            return self._to_response(agent_access, organisation_id)

        updated = await self.repo.update(agent_access_id, **update_data)
        if not updated:
            return None

        workspace = await self.workspace_repo.get(updated.mcp_server_workspace_id)
        organisation_id = str(workspace.organisation_id) if workspace else ""
        return self._to_response(updated, organisation_id)

    async def revoke_agent_access(self, agent_access_id: UUID) -> bool:
        """Revoke an agent access.

        Revocation is PERMANENT - a revoked access cannot be reactivated.

        Args:
            agent_access_id: Agent access UUID

        Returns:
            True if revoked
        """
        result = await self.repo.revoke(agent_access_id)
        return result is not None

    async def rotate_agent_access(
        self,
        agent_access_id: UUID,
        grace_period_hours: int = 24,
    ) -> AgentAccessRotateResponse:
        """Rotate an agent access key.

        Creates a new key with the same settings and sets
        a grace period for the old key.

        Args:
            agent_access_id: Agent access UUID
            grace_period_hours: Hours before old key expires

        Returns:
            New key and old key expiration

        Raises:
            ValueError: If agent access not found or already revoked
        """
        # Get existing access
        old_access = await self.repo.get(agent_access_id)
        if not old_access:
            raise ValueError("Agent access not found")

        # Revoked keys cannot be rotated
        if old_access.is_revoked:
            raise ValueError("Cannot rotate a revoked agent access")

        # Create new access with same settings
        new_access_result = await self.create_agent_access(
            mcp_server_workspace_id=old_access.mcp_server_workspace_id,
            name=f"{old_access.name} (rotated)",
            description=old_access.description,
            expires_at=old_access.expires_at,
            metadata=dict(old_access.metadata_) if old_access.metadata_ else None,
        )

        # Set expiration on old access
        old_access_expires = datetime.now(timezone.utc) + timedelta(
            hours=grace_period_hours
        )
        await self.repo.update(agent_access_id, expires_at=old_access_expires)

        return AgentAccessRotateResponse(
            new_agent_access=new_access_result,
            old_access_valid_until=old_access_expires,
        )

    def _to_response(
        self, agent_access: Any, organisation_id: str
    ) -> AgentAccessResponse:
        """Convert model to response schema."""
        return AgentAccessResponse(
            id=str(agent_access.id),
            mcp_server_workspace_id=str(agent_access.mcp_server_workspace_id),
            organisation_id=organisation_id,
            name=agent_access.name,
            description=agent_access.description,
            key_prefix=agent_access.key_prefix,
            is_active=agent_access.is_active,
            is_revoked=agent_access.is_revoked,
            expires_at=agent_access.expires_at,
            last_used_at=agent_access.last_used_at,
            usage_count=agent_access.usage_count,
            metadata=agent_access.metadata_,
            created_at=agent_access.created_at,
            updated_at=agent_access.updated_at,
        )
