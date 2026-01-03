"""
MCP Server Workspace Service

Business logic for MCP server workspace management.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.utils import slugify
from app.db.repositories import (
    AgentAccessRepository,
    McpServerWorkspaceRepository,
    PolicyRepository,
    UserRepository,
)
from app.schemas.mcp_server_workspace import McpServerWorkspaceResponse


class McpServerWorkspaceService:
    """Service for MCP server workspace operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = McpServerWorkspaceRepository(session)
        self.policy_repo = PolicyRepository(session)
        self.user_repo = UserRepository(session)
        self.agent_access_repo = AgentAccessRepository(session)

    async def create_workspace(
        self,
        organisation_id: UUID,
        name: str,
        slug: str,
        description: str | None = None,
        environment_type: str = "development",
        mcp_server_url: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> McpServerWorkspaceResponse:
        """Create a new MCP server workspace.

        Args:
            organisation_id: Parent organisation UUID
            name: Workspace name
            slug: URL-safe identifier
            description: Optional description
            environment_type: Environment type (production, staging, development)
            mcp_server_url: URL of the MCP server
            settings: Workspace settings

        Returns:
            Created workspace response

        Raises:
            ConflictError: If slug already exists in organisation
        """
        # Check slug uniqueness within organisation
        if await self.repo.slug_exists(organisation_id, slug):
            raise ConflictError(
                f"Workspace with slug '{slug}' already exists in this organisation"
            )

        workspace = await self.repo.create(
            organisation_id=organisation_id,
            name=name,
            slug=slug,
            description=description,
            environment_type=environment_type,
            mcp_server_url=mcp_server_url,
            settings=settings or {},
        )

        return await self._to_response(workspace)

    async def get_workspace(
        self, workspace_id: UUID
    ) -> McpServerWorkspaceResponse | None:
        """Get workspace by ID.

        Args:
            workspace_id: Workspace UUID

        Returns:
            Workspace response or None
        """
        workspace = await self.repo.get(workspace_id)
        if not workspace or workspace.deleted_at:
            return None

        return await self._to_response(workspace)

    async def list_workspaces(
        self,
        organisation_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[McpServerWorkspaceResponse], int]:
        """List workspaces for an organisation.

        Args:
            organisation_id: Organisation UUID
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (workspaces, total_count)
        """
        workspaces = await self.repo.get_by_organisation(
            organisation_id, offset=offset, limit=limit
        )
        total = await self.repo.count_by_organisation(organisation_id)

        responses = [await self._to_response(w) for w in workspaces]
        return responses, total

    async def update_workspace(
        self,
        workspace_id: UUID,
        **kwargs: Any,
    ) -> McpServerWorkspaceResponse | None:
        """Update workspace.

        Args:
            workspace_id: Workspace UUID
            **kwargs: Fields to update

        Returns:
            Updated workspace response or None

        Raises:
            ConflictError: If new slug already exists in organisation
        """
        # First check if workspace exists and is not soft-deleted
        existing_workspace = await self.get_workspace(workspace_id)
        if not existing_workspace:
            return None

        organisation_id = UUID(existing_workspace.organisation_id)

        # Handle name change - regenerate slug and validate uniqueness
        if "name" in kwargs and kwargs["name"] is not None:
            new_slug = slugify(kwargs["name"])
            # Check slug uniqueness within organisation (excluding current workspace)
            if await self.repo.slug_exists(
                organisation_id, new_slug, exclude_id=workspace_id
            ):
                raise ConflictError(
                    f"Workspace with slug '{new_slug}' already exists in this organisation"
                )
            kwargs["slug"] = new_slug

        # Handle settings update
        if "settings" in kwargs and kwargs["settings"]:
            settings_obj = kwargs["settings"]
            if hasattr(settings_obj, "model_dump"):
                kwargs["settings"] = settings_obj.model_dump()

        workspace = await self.repo.update(workspace_id, **kwargs)
        if not workspace:
            return None

        return await self._to_response(workspace)

    async def delete_workspace(self, workspace_id: UUID) -> bool:
        """Soft delete workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            True if deleted
        """
        result = await self.repo.soft_delete(workspace_id)
        return result is not None

    async def _to_response(self, workspace: Any) -> McpServerWorkspaceResponse:
        """Convert model to response schema."""
        policy_count = await self.policy_repo.count_all_for_workspace(workspace.id)
        agent_count = await self.agent_access_repo.count_by_workspace(workspace.id)

        return McpServerWorkspaceResponse(
            id=str(workspace.id),
            organisation_id=str(workspace.organisation_id),
            name=workspace.name,
            slug=workspace.slug,
            description=workspace.description,
            environment_type=workspace.environment_type,
            mcp_server_url=workspace.mcp_server_url,
            settings=workspace.settings,
            is_active=workspace.is_active,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            policy_count=policy_count,
            agent_count=agent_count,
        )
