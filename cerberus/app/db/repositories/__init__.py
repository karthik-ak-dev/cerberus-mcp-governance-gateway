"""
Repository Pattern Implementations

This module provides the Repository pattern for database operations.
Repositories encapsulate database queries and provide a clean API for data access.

Repository Hierarchy:
=====================
    BaseRepository[ModelType]               ← Generic CRUD operations
         │
         ├── OrganisationRepository         ← Organisation-specific queries
         ├── McpServerWorkspaceRepository   ← Workspace-specific queries
         ├── UserRepository                 ← User-specific queries (dashboard access)
         ├── AgentAccessRepository          ← Agent access key queries (MCP auth)
         ├── PolicyRepository               ← Policy-specific queries
         ├── GuardrailRepository            ← Guardrail definition queries
         └── AuditLogRepository             ← Audit log queries & analytics

Key Concepts:
=============
- Users are for DASHBOARD ACCESS only (Cerberus UI login)
- Agents use AgentAccess keys to connect through Cerberus Gateway to MCP servers
- Organisations contain workspaces and users
- MCP Server Workspaces contain agent accesses and policies

Usage Example:
==============
    from app.db import get_db
    from app.db.repositories import OrganisationRepository, AgentAccessRepository

    async def authenticate_agent(db: AsyncSession, key_hash: str):
        repo = AgentAccessRepository(db)
        agent_access = await repo.get_valid_key_with_context(key_hash)
        if not agent_access:
            raise AuthenticationError("Invalid access key")

        # Agent access has workspace eagerly loaded
        workspace = agent_access.mcp_server_workspace
        organisation_id = workspace.organisation_id
        mcp_server_url = workspace.mcp_server_url

        return {
            "agent_access_id": str(agent_access.id),
            "agent_name": agent_access.name,
            "organisation_id": str(organisation_id),
            "mcp_server_workspace_id": str(workspace.id),
            "mcp_server_url": mcp_server_url,
        }
"""

from app.db.repositories.agent_access_repository import AgentAccessRepository
from app.db.repositories.audit_log_repository import AuditLogRepository
from app.db.repositories.base import BaseRepository
from app.db.repositories.guardrail_repository import GuardrailRepository
from app.db.repositories.mcp_server_workspace_repository import (
    McpServerWorkspaceRepository,
)
from app.db.repositories.organisation_repository import OrganisationRepository
from app.db.repositories.policy_repository import PolicyRepository
from app.db.repositories.user_repository import UserRepository

__all__ = [
    # Base class
    "BaseRepository",
    # Entity-specific repositories
    "OrganisationRepository",
    "McpServerWorkspaceRepository",
    "UserRepository",
    "AgentAccessRepository",
    "PolicyRepository",
    "GuardrailRepository",
    "AuditLogRepository",
]
