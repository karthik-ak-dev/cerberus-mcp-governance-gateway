"""
Audit Log Endpoints

Query and export audit logs.
"""

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query

from app.config.constants import DecisionAction, GuardrailType
from app.control_plane.api.dependencies import CurrentUser, DbSession
from app.control_plane.api.utils import (
    check_organisation_access,
    raise_bad_request,
    raise_not_found,
    validate_uuid,
)
from app.db.repositories import AuditLogRepository, McpServerWorkspaceRepository
from app.schemas.common import PaginatedResponse, PaginationMeta, PaginationParams


router = APIRouter()


# =============================================================================
# LOG ENDPOINTS
# =============================================================================


@router.get(
    "/mcp-server-workspaces/{mcp_server_workspace_id}/logs",
    summary="Query audit logs",
    description="""
Query audit logs for an MCP Server Workspace with optional filters.

**Filters:**
- `start_time`: Filter logs after this time (ISO 8601 format)
- `end_time`: Filter logs before this time (ISO 8601 format)
- `agent_name`: Filter by agent name
- `decision`: Filter by decision (allow, block_request, block_response, modify, log_only, throttle)
- `guardrail_type`: Filter by guardrail type
- `tool_name`: Filter by MCP tool name
""",
)
async def query_logs(
    mcp_server_workspace_id: str,
    current_user: CurrentUser,
    db: DbSession,
    pagination: Annotated[PaginationParams, Depends()],
    start_time: Annotated[
        Optional[datetime], Query(description="Filter logs after this time")
    ] = None,
    end_time: Annotated[
        Optional[datetime], Query(description="Filter logs before this time")
    ] = None,
    agent_name: Annotated[
        Optional[str], Query(description="Filter by agent name")
    ] = None,
    decision: Annotated[
        Optional[DecisionAction], Query(description="Filter by decision")
    ] = None,
    guardrail_type: Annotated[
        Optional[GuardrailType], Query(description="Filter by guardrail type")
    ] = None,
    tool_name: Annotated[
        Optional[str], Query(description="Filter by MCP tool name")
    ] = None,
) -> PaginatedResponse[dict[str, Any]]:
    """Query audit logs for an MCP Server Workspace.

    Args:
        mcp_server_workspace_id: MCP Server Workspace UUID
        current_user: Current authenticated user
        db: Database session
        pagination: Pagination parameters
        start_time: Filter logs after this time
        end_time: Filter logs before this time
        agent_name: Filter by agent name
        decision: Filter by decision (allow, block_request, block_response, modify, log_only, throttle)
        guardrail_type: Filter by guardrail type
        tool_name: Filter by MCP tool name

    Returns:
        Paginated list of audit logs

    Raises:
        400: Invalid UUID format or invalid enum value
        403: Access denied
        404: Workspace not found or deleted
    """
    workspace_uuid = validate_uuid(mcp_server_workspace_id, "mcp_server_workspace_id")

    # Verify workspace exists and is not deleted
    workspace_repo = McpServerWorkspaceRepository(db)
    workspace = await workspace_repo.get(workspace_uuid)

    if not workspace or workspace.deleted_at:
        raise_not_found("MCP Server Workspace")

    # Check organisation access
    check_organisation_access(
        current_user, str(workspace.organisation_id), "query logs for"
    )

    # Validate time range
    if start_time and end_time and start_time > end_time:
        raise_bad_request("start_time must be before end_time")

    # Query logs
    log_repo = AuditLogRepository(db)
    logs = await log_repo.query(
        mcp_server_workspace_id=workspace_uuid,
        start_time=start_time,
        end_time=end_time,
        agent_name=agent_name,
        decision=decision.value if decision else None,
        guardrail_type=guardrail_type.value if guardrail_type else None,
        tool_name=tool_name,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    # Get total count
    total = await log_repo.count_query(
        mcp_server_workspace_id=workspace_uuid,
        start_time=start_time,
        end_time=end_time,
        agent_name=agent_name,
        decision=decision.value if decision else None,
    )

    # Convert to response format
    log_data = [
        {
            "id": str(log.id),
            "request_id": log.request_id,
            "created_at": log.created_at.isoformat(),
            "agent_name": log.agent_name,
            "agent_access_id": str(log.agent_access_id) if log.agent_access_id else None,
            "message_type": log.message_type,
            "tool_name": log.tool_name,
            "decision": log.decision,
            "decision_reason": log.decision_reason,
            "guardrail_results": log.guardrail_results,
            "latency_ms": log.latency_ms,
        }
        for log in logs
    ]

    return PaginatedResponse[dict[str, Any]](
        data=log_data,
        pagination=PaginationMeta.create(
            page=pagination.page, per_page=pagination.per_page, total=total
        ),
    )


@router.get(
    "/mcp-server-workspaces/{mcp_server_workspace_id}/logs/{request_id}",
    summary="Get log detail",
    description="Get detailed audit log by request ID.",
)
async def get_log_detail(
    mcp_server_workspace_id: str,
    request_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, Any]:
    """Get detailed audit log by request ID.

    Args:
        mcp_server_workspace_id: MCP Server Workspace UUID
        request_id: Request ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Detailed audit log

    Raises:
        400: Invalid UUID format
        403: Access denied
        404: Workspace or log not found
    """
    workspace_uuid = validate_uuid(mcp_server_workspace_id, "mcp_server_workspace_id")

    # Verify workspace exists and is not deleted
    workspace_repo = McpServerWorkspaceRepository(db)
    workspace = await workspace_repo.get(workspace_uuid)

    if not workspace or workspace.deleted_at:
        raise_not_found("MCP Server Workspace")

    # Check organisation access
    check_organisation_access(
        current_user, str(workspace.organisation_id), "access logs for"
    )

    # Get log
    log_repo = AuditLogRepository(db)
    log = await log_repo.get_by_request_id(request_id)

    if not log or str(log.mcp_server_workspace_id) != mcp_server_workspace_id:
        raise_not_found("Log")

    return {
        "id": str(log.id),
        "request_id": log.request_id,
        "created_at": log.created_at.isoformat(),
        "agent_name": log.agent_name,
        "agent_access_id": str(log.agent_access_id) if log.agent_access_id else None,
        "session_id": log.session_id,
        "message_type": log.message_type,
        "tool_name": log.tool_name,
        "decision": log.decision,
        "decision_reason": log.decision_reason,
        "guardrail_results": log.guardrail_results,
        "request_summary": log.request_summary,
        "response_summary": log.response_summary,
        "modifications": log.modifications,
        "latency_ms": log.latency_ms,
        "ip_address": log.ip_address,
    }
