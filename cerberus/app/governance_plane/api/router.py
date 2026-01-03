"""
Governance Plane API Router

MCP proxy with inline governance - the main entry point for MCP clients.
"""

from fastapi import APIRouter

from app.governance_plane.api.v1 import proxy

router = APIRouter()

# Proxy API - Direct MCP proxy with inline governance
router.include_router(proxy.router, prefix="/proxy", tags=["Governance Plane: Proxy"])
