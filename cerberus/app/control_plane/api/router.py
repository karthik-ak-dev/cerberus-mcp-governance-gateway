"""
Control Plane API Router

Aggregates all admin API routes.
"""

from fastapi import APIRouter

from app.control_plane.api import auth
from app.control_plane.api.v1 import (
    agent_accesses,
    analytics,
    guardrails,
    logs,
    mcp_server_workspaces,
    organisations,
    policies,
    users,
)

router = APIRouter()

# Authentication
router.include_router(
    auth.router, prefix="/auth", tags=["Control Plane: Authentication"]
)

# V1 Admin APIs
router.include_router(
    organisations.router,
    prefix="/organisations",
    tags=["Control Plane: Organisations"],
)
router.include_router(
    mcp_server_workspaces.router,
    tags=["Control Plane: MCP Server Workspaces"],
)
router.include_router(
    users.router,
    tags=["Control Plane: Users"],
)
router.include_router(
    agent_accesses.router,
    tags=["Control Plane: Agent Accesses"],
)
router.include_router(
    guardrails.router,
    prefix="/guardrails",
    tags=["Control Plane: Guardrails"],
)
router.include_router(
    policies.router,
    prefix="/policies",
    tags=["Control Plane: Policies"],
)
router.include_router(
    logs.router,
    tags=["Control Plane: Logs"],
)
router.include_router(
    analytics.router,
    tags=["Control Plane: Analytics"],
)
