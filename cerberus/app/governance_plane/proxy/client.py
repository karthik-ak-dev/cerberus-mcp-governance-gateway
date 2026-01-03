"""
MCP HTTP Client

Handles HTTP communication with upstream MCP servers.

Features:
- Connection pooling for efficiency
- Configurable timeouts
- Retry logic for transient failures
- Response time tracking
- Proper error handling
- Full HTTP method support (GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD)
- Configurable header forwarding (including client Authorization)
"""

import json
import time
from typing import Any

import httpx

from app.config.settings import settings
from app.core.logging import logger
from app.schemas.proxy import ProxyContext, ProxyResult

# Headers that should never be forwarded for security reasons
DEFAULT_BLOCKED_HEADERS = frozenset({
    "host",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "proxy-authorization",
    "proxy-connection",
})

# Headers that Cerberus adds (will override client headers)
CERBERUS_HEADERS = frozenset({
    "x-gateway-request-id",
    "x-forwarded-for",
    "x-organisation-id",
    "x-mcp-server-workspace-id",
    "x-agent-access-id",
    "x-original-user-agent",
})


class MCPClient:
    """
    HTTP client for communicating with upstream MCP servers.

    Uses httpx for async HTTP requests with:
    - Connection pooling
    - Configurable timeouts
    - Automatic retry for transient failures
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        max_keepalive_connections: int = 20,
        max_connections: int = 100,
    ):
        """Initialize the MCP client.

        Args:
            timeout_seconds: Request timeout in seconds
            max_retries: Maximum retry attempts for transient failures
            max_keepalive_connections: Max keepalive connections in pool
            max_connections: Max total connections in pool
        """
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_keepalive_connections = max_keepalive_connections
        self.max_connections = max_connections
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize the HTTP client.

        Creates an async client with connection pooling.
        Call this during application startup.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                limits=httpx.Limits(
                    max_keepalive_connections=self.max_keepalive_connections,
                    max_connections=self.max_connections,
                ),
                follow_redirects=False,
            )
            logger.info(
                "MCP client initialized",
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
            )

    async def close(self) -> None:
        """Close the HTTP client.

        Call this during application shutdown.
        """
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("MCP client closed")

    async def forward(
        self,
        context: ProxyContext,
        message: dict[str, Any] | None = None,
    ) -> ProxyResult:
        """Forward an MCP message to the upstream server.

        The upstream URL comes from context.mcp_server_url which is
        resolved from the workspace configuration via access key.

        Supports all HTTP methods:
        - GET, HEAD, OPTIONS: No body, query params preserved
        - POST, PUT, PATCH: Body forwarded as JSON
        - DELETE: Optional body support

        Args:
            context: Proxy context with request information
            message: Optional modified message to send (defaults to original)

        Returns:
            ProxyResult with success/failure and response
        """
        if self._client is None:
            logger.info("MCPClient: Initializing HTTP client")
            await self.initialize()

        # mcp_server_url is mandatory
        if not context.mcp_server_url:
            logger.error(
                "MCPClient: No MCP server URL configured",
                request_id=context.request_id,
                mcp_server_workspace_id=context.mcp_server_workspace_id,
            )
            return ProxyResult.from_error(
                error_message="No MCP server URL configured for this workspace",
                status_code=500,
                response_time_ms=0,
                upstream_url="",
            )

        # Use modified message if provided, otherwise original
        # For methods without body (GET, HEAD, OPTIONS), this will be None
        body = message if message is not None else context.mcp_message

        # Build the upstream URL
        base_url = context.mcp_server_url.rstrip("/")
        request_path = context.request_path
        if not request_path.startswith("/"):
            request_path = "/" + request_path

        upstream_url = f"{base_url}{request_path}"

        # Append query parameters if present
        if context.query_params:
            upstream_url = f"{upstream_url}?{context.query_params}"

        logger.info(
            "MCPClient: Preparing upstream request",
            request_id=context.request_id,
            http_method=context.http_method,
            upstream_url=upstream_url,
            request_path=request_path,
            mcp_method=context.mcp_method,
            has_body=body is not None,
            has_query_params=context.query_params is not None,
        )

        start_time = time.perf_counter()

        try:
            headers = self._prepare_headers(context)

            logger.info(
                "MCPClient: Sending request to upstream",
                request_id=context.request_id,
                http_method=context.http_method,
                upstream_url=upstream_url,
                headers_count=len(headers),
            )

            response = await self._make_request(
                method=context.http_method,
                url=upstream_url,
                body=body,
                headers=headers,
                request_id=context.request_id,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "MCPClient: Upstream response received",
                request_id=context.request_id,
                status_code=response.status_code,
                response_time_ms=round(elapsed_ms, 2),
                upstream_url=upstream_url,
                content_length=response.headers.get("content-length"),
            )

            return await self._handle_response(
                response=response,
                request_id=context.request_id,
                elapsed_ms=elapsed_ms,
                upstream_url=upstream_url,
            )

        except httpx.TimeoutException as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "MCPClient: Upstream TIMEOUT",
                request_id=context.request_id,
                elapsed_ms=round(elapsed_ms, 2),
                timeout_seconds=self.timeout_seconds,
                upstream_url=upstream_url,
                error=str(e),
            )
            return ProxyResult.from_error(
                error_message=f"Upstream server timeout: {e}",
                status_code=504,
                response_time_ms=elapsed_ms,
                upstream_url=upstream_url,
            )

        except httpx.ConnectError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "MCPClient: Upstream CONNECTION ERROR",
                request_id=context.request_id,
                upstream_url=upstream_url,
                elapsed_ms=round(elapsed_ms, 2),
                error=str(e),
            )
            return ProxyResult.from_error(
                error_message=f"Cannot connect to upstream server: {e}",
                status_code=502,
                response_time_ms=elapsed_ms,
                upstream_url=upstream_url,
            )

        except (httpx.HTTPError, json.JSONDecodeError, ValueError, KeyError) as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "MCPClient: Unexpected error during upstream request",
                request_id=context.request_id,
                upstream_url=upstream_url,
                error_type=type(e).__name__,
            )
            return ProxyResult.from_error(
                error_message=f"Unexpected error: {e}",
                status_code=502,
                response_time_ms=elapsed_ms,
                upstream_url=upstream_url,
            )

    async def _make_request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None,
        headers: dict[str, str],
        request_id: str,
    ) -> httpx.Response:
        """Make the HTTP request to upstream with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD)
            url: Full upstream URL
            body: Request body (can be None for GET/DELETE/HEAD/OPTIONS)
            headers: Headers to send
            request_id: Request ID for logging

        Returns:
            httpx.Response from upstream
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                method_upper = method.upper()

                # Methods that typically don't have a body
                if method_upper == "GET":
                    response = await self._client.get(url, headers=headers)
                elif method_upper == "HEAD":
                    response = await self._client.head(url, headers=headers)
                elif method_upper == "OPTIONS":
                    response = await self._client.options(url, headers=headers)
                elif method_upper == "DELETE":
                    # DELETE can optionally have a body
                    if body:
                        response = await self._client.request(
                            "DELETE", url, json=body, headers=headers
                        )
                    else:
                        response = await self._client.delete(url, headers=headers)
                # Methods that typically have a body
                elif method_upper == "POST":
                    response = await self._client.post(url, json=body, headers=headers)
                elif method_upper == "PUT":
                    response = await self._client.put(url, json=body, headers=headers)
                elif method_upper == "PATCH":
                    response = await self._client.patch(url, json=body, headers=headers)
                else:
                    # Unknown method - use generic request
                    logger.warning(
                        "Unknown HTTP method, using generic request",
                        request_id=request_id,
                        method=method_upper,
                    )
                    if body:
                        response = await self._client.request(
                            method_upper, url, json=body, headers=headers
                        )
                    else:
                        response = await self._client.request(
                            method_upper, url, headers=headers
                        )
                return response

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(
                        "Upstream request failed, retrying",
                        request_id=request_id,
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        error=str(e),
                    )
                    continue
                raise

        raise last_exception or Exception("Request failed after retries")

    def _prepare_headers(self, context: ProxyContext) -> dict[str, str]:
        """Prepare headers for the upstream request.

        Header forwarding strategy:
        1. Start with forwarded client headers (if configured)
        2. Add Cerberus-specific headers (always override client headers)
        3. Optionally forward Authorization header (if configured)

        Args:
            context: Proxy context with client headers

        Returns:
            Headers dict to send to upstream
        """
        headers: dict[str, str] = {}

        # Step 1: Forward client headers based on configuration
        if context.client_headers:
            blocked = self._get_blocked_headers()

            for header_name, header_value in context.client_headers.items():
                header_lower = header_name.lower()

                # Skip blocked headers
                if header_lower in blocked:
                    continue

                # Skip Cerberus headers (will be set below)
                if header_lower in CERBERUS_HEADERS:
                    continue

                # Skip Authorization if not configured to forward
                if header_lower == "authorization":
                    if settings.PROXY_FORWARD_AUTHORIZATION:
                        headers[header_name] = header_value
                    continue

                # Check if we should forward this header
                if self._should_forward_header(header_lower):
                    headers[header_name] = header_value

        # Step 2: Add Cerberus headers (always present, override any client headers)
        headers["Content-Type"] = "application/json"
        headers[settings.PROXY_REQUEST_ID_HEADER] = context.request_id
        headers[settings.PROXY_FORWARDED_FOR_HEADER] = context.client_ip or "unknown"
        headers["X-Organisation-ID"] = context.organisation_id
        headers["X-MCP-Server-Workspace-ID"] = context.mcp_server_workspace_id
        headers["X-Agent-Access-ID"] = context.agent_access_id

        if context.client_agent:
            headers["X-Original-User-Agent"] = context.client_agent

        return headers

    def _get_blocked_headers(self) -> frozenset[str]:
        """Get the complete set of blocked headers."""
        blocked = set(DEFAULT_BLOCKED_HEADERS)
        blocked.update(settings.proxy_blocked_headers_list)
        return frozenset(blocked)

    def _should_forward_header(self, header_lower: str) -> bool:
        """Determine if a header should be forwarded to upstream.

        Args:
            header_lower: Lowercase header name

        Returns:
            True if header should be forwarded
        """
        # If forward all is enabled, forward everything not blocked
        if settings.PROXY_FORWARD_ALL_HEADERS:
            return True

        # Otherwise, only forward explicitly listed headers
        return header_lower in settings.proxy_forward_headers_list

    async def _handle_response(
        self,
        response: httpx.Response,
        request_id: str,
        elapsed_ms: float,
        upstream_url: str,
    ) -> ProxyResult:
        """Handle the upstream response.

        Captures both the response body and headers for forwarding.
        """
        # Extract upstream headers (filter out hop-by-hop headers)
        upstream_headers = self._extract_response_headers(response)

        logger.info(
            "MCPClient: Processing upstream response",
            request_id=request_id,
            status_code=response.status_code,
            headers_forwarded=len(upstream_headers),
        )

        try:
            response_body = response.json()

            logger.info(
                "MCPClient: Parsed JSON response successfully",
                request_id=request_id,
            )

            return ProxyResult.from_success(
                response_body=response_body,
                status_code=response.status_code,
                response_time_ms=elapsed_ms,
                upstream_url=upstream_url,
                upstream_headers=upstream_headers,
            )

        except json.JSONDecodeError:
            logger.error(
                "MCPClient: Upstream returned non-JSON response",
                request_id=request_id,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                response_preview=response.text[:200] if response.text else "(empty)",
            )
            return ProxyResult.from_error(
                error_message="Upstream returned invalid JSON",
                status_code=502,
                response_time_ms=elapsed_ms,
                upstream_url=upstream_url,
            )

    def _extract_response_headers(self, response: httpx.Response) -> dict[str, str]:
        """Extract headers from upstream response for forwarding.

        Filters out hop-by-hop headers and internal headers.
        """
        # Headers to exclude from response forwarding
        excluded = {
            "connection",
            "keep-alive",
            "transfer-encoding",
            "te",
            "trailer",
            "upgrade",
            "content-encoding",  # httpx handles decompression
            "content-length",  # Will be recalculated
        }

        headers = {}
        for name, value in response.headers.items():
            if name.lower() not in excluded:
                headers[name] = value

        return headers

    async def health_check(self, mcp_server_url: str) -> bool:
        """Check if an MCP server is healthy.

        Args:
            mcp_server_url: URL of the MCP server to check

        Returns:
            True if reachable, False otherwise
        """
        if self._client is None:
            await self.initialize()

        try:
            response = await self._client.get(mcp_server_url, timeout=5.0)
            return response.status_code < 500
        except httpx.HTTPError as e:
            logger.warning(
                "MCP server health check failed",
                mcp_server_url=mcp_server_url,
                error=str(e),
            )
            return False


class _MCPClientHolder:
    """Holder for global MCP client instance."""

    instance: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """Get the global MCP client instance."""
    if _MCPClientHolder.instance is None:
        _MCPClientHolder.instance = MCPClient(
            timeout_seconds=settings.MCP_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.MCP_MAX_RETRIES,
        )
    return _MCPClientHolder.instance


async def init_mcp_client() -> None:
    """Initialize the global MCP client."""
    client = get_mcp_client()
    await client.initialize()


async def close_mcp_client() -> None:
    """Close the global MCP client."""
    if _MCPClientHolder.instance:
        await _MCPClientHolder.instance.close()
        _MCPClientHolder.instance = None
