"""
Cerberus Platform SQLAlchemy Models

This package contains all database models for the Central Governance Service.

Model Hierarchy:
================
    Organisation
       ├── MCP Server Workspaces (Environments: prod, staging, dev)
       │      └── Agent Accesses (AI agents connecting to MCP servers)
       │      └── Policies (Workspace-level guardrail configurations)
       │      └── Audit Logs (Decision history)
       ├── Users (Dashboard access for admins/viewers)
       └── Policies (Organisation-level defaults)

    Guardrails (System-wide guardrail definitions)
       └── Policies (Link guardrails to entities)

Models Overview:
================
- Base: Base class and mixins (timestamps, soft delete)
- Organisation: Customer organization, top-level entity
- McpServerWorkspace: Environment within an organisation (prod/staging/dev)
- User: Individual with dashboard access (NOT for MCP auth)
- AgentAccess: AI agent authentication for MCP tools
- Guardrail: Guardrail definition (RBAC, PII, Rate Limit, etc.)
- Policy: Links a guardrail to an entity with configuration
- AuditLog: Record of every governance decision

Usage:
======
    from app.models import (
        Organisation, McpServerWorkspace, User, AgentAccess,
        Guardrail, Policy, AuditLog
    )

    # Create a new organisation
    org = Organisation(
        name="Acme Corporation",
        slug="acme-corp",
        subscription_tier="default"
    )

    # Query with relationships
    org.mcp_server_workspaces  # All workspaces in this organisation
    org.users                   # All dashboard users in this organisation
"""

from app.models.agent_access import AgentAccess
from app.models.audit_log import AuditLog
from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.guardrail import Guardrail
from app.models.mcp_server_workspace import McpServerWorkspace
from app.models.organisation import Organisation
from app.models.policy import Policy
from app.models.user import User

__all__ = [
    # Base classes and mixins
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    # Core models
    "Organisation",
    "McpServerWorkspace",
    "User",
    "AgentAccess",
    "Guardrail",
    "Policy",
    "AuditLog",
]
