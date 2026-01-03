"""
Proxy Schemas

Models for the MCP proxy functionality.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.config.constants import DecisionAction


class MCPError(BaseModel):
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: Optional[Any] = None


class MCPErrorCodes:
    """JSON-RPC and MCP-specific error codes."""

    # Standard JSON-RPC errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # Cerberus-specific errors
    GOVERNANCE_BLOCKED = -32001
    UPSTREAM_TIMEOUT = -32002
    UPSTREAM_ERROR = -32003


class ProxyContext(BaseModel):
    """Context for a proxy request, derived from agent access key."""

    request_id: str
    organisation_id: str
    mcp_server_workspace_id: str
    agent_access_id: str
    agent_name: str
    mcp_server_url: str
    request_path: str = "/"
    http_method: str = "POST"
    client_ip: Optional[str] = None
    client_agent: Optional[str] = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Original request body - can be None for GET/DELETE/HEAD requests
    mcp_message: Optional[dict[str, Any]] = None
    # Original client headers (for forwarding to upstream)
    client_headers: dict[str, str] = Field(default_factory=dict)
    # Query parameters (for GET requests)
    query_params: Optional[str] = None

    @property
    def mcp_method(self) -> Optional[str]:
        """MCP method name from message."""
        if self.mcp_message:
            return self.mcp_message.get("method")
        return None

    @property
    def mcp_id(self) -> Optional[int | str]:
        """MCP request ID from message."""
        if self.mcp_message:
            return self.mcp_message.get("id")
        return None

    @property
    def has_body(self) -> bool:
        """Check if request has a body."""
        return self.http_method.upper() in ("POST", "PUT", "PATCH")


@dataclass
class ProxyResult:
    """Result from upstream MCP server."""

    success: bool
    status_code: int
    response_body: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    response_time_ms: float = 0.0
    upstream_url: str = ""
    # Upstream response headers (for forwarding back to client)
    upstream_headers: Optional[dict[str, str]] = None

    @classmethod
    def from_success(
        cls,
        response_body: dict[str, Any],
        status_code: int = 200,
        response_time_ms: float = 0.0,
        upstream_url: str = "",
        upstream_headers: Optional[dict[str, str]] = None,
    ) -> "ProxyResult":
        """Create a successful proxy result."""
        return cls(
            success=True,
            status_code=status_code,
            response_body=response_body,
            response_time_ms=response_time_ms,
            upstream_url=upstream_url,
            upstream_headers=upstream_headers,
        )

    @classmethod
    def from_error(
        cls,
        error_message: str,
        status_code: int = 502,
        response_time_ms: float = 0.0,
        upstream_url: str = "",
    ) -> "ProxyResult":
        """Create an error proxy result."""
        return cls(
            success=False,
            status_code=status_code,
            error_message=error_message,
            response_time_ms=response_time_ms,
            upstream_url=upstream_url,
        )


class ProxyResponse(BaseModel):
    """MCP JSON-RPC response."""

    jsonrpc: str = "2.0"
    id: Optional[int | str] = None
    result: Optional[Any] = None
    error: Optional[MCPError] = None

    class Config:
        """Pydantic config."""

        extra = "allow"

    @classmethod
    def from_upstream(cls, response_body: dict[str, Any]) -> "ProxyResponse":
        """Create response from upstream body."""
        return cls(**response_body)

    @classmethod
    def from_error(
        cls,
        request_id: Optional[int | str],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> "ProxyResponse":
        """Create error response."""
        return cls(
            id=request_id,
            error=MCPError(code=code, message=message, data=data),
        )


class ProxyDecisionInfo(BaseModel):
    """Governance decision info for a proxy request."""

    request_decision_id: str
    request_action: DecisionAction
    request_allowed: bool
    response_decision_id: Optional[str] = None
    response_action: Optional[DecisionAction] = None
    response_allowed: Optional[bool] = None
    total_governance_time_ms: int = 0
