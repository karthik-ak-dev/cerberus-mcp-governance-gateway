"""
MCP Proxy Endpoint

Direct MCP proxy with inline governance. This is the main entry point
for MCP clients connecting to Cerberus.

Flow:
1. Validate access key (derives organisation, workspace, agent_access, mcp_server_url)
2. Evaluate request against governance policies
3. Forward to upstream MCP server
4. Evaluate response against governance policies
5. Return final response to client

Supports all HTTP methods:
- GET, HEAD, OPTIONS: No body required
- POST, PUT, PATCH: JSON body forwarded
- DELETE: Optional body support

Original client headers (including Authorization) can be forwarded
to upstream based on configuration (see settings.py).
"""

import json
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from httpx import HTTPError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import GuardrailExecutionError
from app.core.logging import logger
from app.core.utils import generate_short_id
from app.governance_plane.api.dependencies import DbSession, ValidatedAccessKey
from app.governance_plane.proxy.service import ProxyService, create_proxy_context
from app.schemas.proxy import MCPErrorCodes, ProxyResponse

# HTTP methods that typically have a request body
METHODS_WITH_BODY = frozenset({"POST", "PUT", "PATCH"})

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP, considering X-Forwarded-For from proxies."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _extract_client_headers(request: Request) -> dict[str, str]:
    """Extract all client headers for potential forwarding.

    The MCPClient will decide which headers to actually forward
    based on configuration.
    """
    return dict(request.headers)


async def _handle_proxy_request(
    request: Request,
    path: str,
    key_context: ValidatedAccessKey,
    db: DbSession,
) -> JSONResponse:
    """
    Core proxy handler for MCP requests.

    Supports all HTTP methods:
    - GET, HEAD, OPTIONS: No body required, query params preserved
    - POST, PUT, PATCH: JSON body forwarded
    - DELETE: Optional body support

    Args:
        request: Incoming FastAPI request
        path: Request path to forward to upstream
        key_context: Validated access key context
        db: Database session

    Returns:
        JSONResponse with MCP response or error
    """
    request_id = generate_short_id("req")
    http_method = request.method.upper()

    logger.info(
        "Received proxy request",
        request_id=request_id,
        http_method=http_method,
        path=path,
        client_ip=_get_client_ip(request),
        agent_name=key_context.agent_name,
        mcp_server_url=key_context.mcp_server_url,
    )

    try:
        # Parse request body for methods that support it
        body: dict | None = None
        mcp_id: int | str | None = None

        if http_method in METHODS_WITH_BODY:
            try:
                body = await request.json()
                mcp_id = body.get("id") if body else None
                logger.info(
                    "Parsed request body",
                    request_id=request_id,
                    mcp_id=mcp_id,
                    mcp_method=body.get("method") if body else None,
                )
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    "Invalid request body",
                    request_id=request_id,
                    http_method=http_method,
                    error=str(e),
                )
                return JSONResponse(
                    content=ProxyResponse.from_error(
                        request_id=None,
                        code=MCPErrorCodes.PARSE_ERROR,
                        message=f"Invalid JSON: {e}",
                    ).model_dump(exclude_none=True),
                    status_code=200,
                )
        elif http_method == "DELETE":
            # DELETE can optionally have a body
            try:
                content_length = request.headers.get("content-length", "0")
                if int(content_length) > 0:
                    body = await request.json()
                    mcp_id = body.get("id") if body else None
                    logger.info(
                        "Parsed DELETE request body",
                        request_id=request_id,
                        mcp_id=mcp_id,
                    )
            except (json.JSONDecodeError, ValueError):
                # Body is optional for DELETE, ignore parse errors
                logger.info(
                    "DELETE request has no valid body (optional)",
                    request_id=request_id,
                )

        # Validate MCP server is configured
        if not key_context.mcp_server_url:
            logger.error(
                "No MCP server URL configured",
                request_id=request_id,
                mcp_server_workspace_id=key_context.mcp_server_workspace_id,
                organisation_id=key_context.organisation_id,
            )
            return JSONResponse(
                content=ProxyResponse.from_error(
                    request_id=mcp_id,
                    code=MCPErrorCodes.INTERNAL_ERROR,
                    message="No MCP server URL configured for this workspace",
                ).model_dump(exclude_none=True),
                status_code=200,
            )

        # Extract query parameters
        query_params = str(request.query_params) if request.query_params else None

        # Build context and proxy
        context = create_proxy_context(
            key_context=key_context,
            mcp_message=body,
            request_path=f"/{path}" if path else "/",
            http_method=http_method,
            client_ip=_get_client_ip(request),
            client_agent=request.headers.get("user-agent"),
            request_id=request_id,
            client_headers=_extract_client_headers(request),
            query_params=query_params,
        )

        logger.info(
            "Proxying MCP request",
            request_id=request_id,
            http_method=http_method,
            organisation_id=context.organisation_id,
            mcp_server_workspace_id=context.mcp_server_workspace_id,
            agent_access_id=context.agent_access_id,
            agent_name=context.agent_name,
            mcp_method=context.mcp_method,
            upstream_url=context.mcp_server_url,
            request_path=context.request_path,
            has_body=body is not None,
            has_query_params=query_params is not None,
        )

        # Execute proxy with inline governance
        proxy_service = ProxyService(db=db)
        response, decision_info = await proxy_service.proxy_request(context)

        # Build response headers
        response_headers = {
            "X-Request-ID": request_id,
            "X-Request-Decision-ID": decision_info.request_decision_id,
        }
        if decision_info.response_decision_id:
            response_headers["X-Response-Decision-ID"] = decision_info.response_decision_id

        logger.info(
            "Proxy request completed successfully",
            request_id=request_id,
            request_decision_id=decision_info.request_decision_id,
            response_decision_id=decision_info.response_decision_id,
            request_allowed=decision_info.request_allowed,
            response_allowed=decision_info.response_allowed,
            governance_time_ms=decision_info.total_governance_time_ms,
        )

        return JSONResponse(
            content=response.model_dump(exclude_none=True),
            status_code=200,
            headers=response_headers,
        )

    except (
        SQLAlchemyError,
        HTTPError,
        ValidationError,
        GuardrailExecutionError,
        RuntimeError,
        TypeError,
        AttributeError,
        KeyError,
        ValueError,
        OSError,
    ) as e:
        tb_str = traceback.format_exc()
        logger.error(
            "Proxy error",
            request_id=request_id,
            error_type=type(e).__name__,
            error_message=str(e),
            traceback=tb_str,
        )
        return JSONResponse(
            content=ProxyResponse.from_error(
                request_id=None,
                code=MCPErrorCodes.INTERNAL_ERROR,
                message=f"Internal error: {type(e).__name__}: {e}",
            ).model_dump(exclude_none=True),
            status_code=200,
        )


# =============================================================================
# Route handlers for all HTTP methods
# =============================================================================

# POST routes (most common for MCP JSON-RPC)
@router.post("/{path:path}")
async def proxy_post(
    request: Request,
    key_context: ValidatedAccessKey,
    db: DbSession,
    path: str = "",
) -> JSONResponse:
    """
    Proxy POST requests to upstream MCP server.

    Path is preserved: POST /proxy/v1/tools/call -> mcp_server_url/v1/tools/call

    Requires: Authorization: Bearer <access_key>
    """
    return await _handle_proxy_request(request, path, key_context, db)


# GET routes
@router.get("/{path:path}")
async def proxy_get(
    request: Request,
    key_context: ValidatedAccessKey,
    db: DbSession,
    path: str = "",
) -> JSONResponse:
    """
    Proxy GET requests to upstream MCP server.

    Query parameters are preserved.
    """
    return await _handle_proxy_request(request, path, key_context, db)


# PUT routes
@router.put("/{path:path}")
async def proxy_put(
    request: Request,
    key_context: ValidatedAccessKey,
    db: DbSession,
    path: str = "",
) -> JSONResponse:
    """Proxy PUT requests to upstream MCP server."""
    return await _handle_proxy_request(request, path, key_context, db)


# PATCH routes
@router.patch("/{path:path}")
async def proxy_patch(
    request: Request,
    key_context: ValidatedAccessKey,
    db: DbSession,
    path: str = "",
) -> JSONResponse:
    """Proxy PATCH requests to upstream MCP server."""
    return await _handle_proxy_request(request, path, key_context, db)


# DELETE routes
@router.delete("/{path:path}")
async def proxy_delete(
    request: Request,
    key_context: ValidatedAccessKey,
    db: DbSession,
    path: str = "",
) -> JSONResponse:
    """Proxy DELETE requests to upstream MCP server."""
    return await _handle_proxy_request(request, path, key_context, db)


# OPTIONS routes (for CORS preflight)
@router.options("/{path:path}")
async def proxy_options(
    request: Request,
    key_context: ValidatedAccessKey,
    db: DbSession,
    path: str = "",
) -> JSONResponse:
    """Proxy OPTIONS requests to upstream MCP server."""
    return await _handle_proxy_request(request, path, key_context, db)


# HEAD routes
@router.head("/{path:path}")
async def proxy_head(
    request: Request,
    key_context: ValidatedAccessKey,
    db: DbSession,
    path: str = "",
) -> JSONResponse:
    """Proxy HEAD requests to upstream MCP server."""
    return await _handle_proxy_request(request, path, key_context, db)
