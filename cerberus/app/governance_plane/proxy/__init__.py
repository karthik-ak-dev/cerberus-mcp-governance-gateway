"""
Proxy Module

MCP proxy functionality with inline governance.
"""

from app.governance_plane.proxy.client import MCPClient
from app.governance_plane.proxy.service import ProxyService

__all__ = ["MCPClient", "ProxyService"]
