"""
Analytics Endpoints

Dashboard and reporting analytics.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query

from app.config.constants import AnalyticsPeriod
from app.control_plane.api.dependencies import CurrentUser, DbSession
from app.control_plane.api.utils import (
    check_organisation_access,
    raise_bad_request,
    raise_not_found,
    validate_uuid,
)
from app.db.repositories import AuditLogRepository, McpServerWorkspaceRepository


router = APIRouter()


# Period to timedelta mapping
PERIOD_DELTAS = {
    AnalyticsPeriod.HOUR: timedelta(hours=1),
    AnalyticsPeriod.DAY: timedelta(days=1),
    AnalyticsPeriod.WEEK: timedelta(weeks=1),
    AnalyticsPeriod.MONTH: timedelta(days=30),
}


# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================


@router.get(
    "/mcp-server-workspaces/{mcp_server_workspace_id}/analytics",
    summary="Get workspace analytics",
    description="""
Get analytics summary for an MCP Server Workspace.

**Period Options:**
- `hour`: Last hour
- `day`: Last 24 hours (default)
- `week`: Last 7 days
- `month`: Last 30 days

Custom time ranges can be specified using `start_time` and `end_time` parameters.
""",
)
async def get_analytics(
    mcp_server_workspace_id: str,
    current_user: CurrentUser,
    db: DbSession,
    period: AnalyticsPeriod = Query(
        AnalyticsPeriod.DAY,
        description="Time period for analytics",
    ),
    start_time: Optional[datetime] = Query(
        None,
        description="Custom start time (ISO 8601 format)",
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="Custom end time (ISO 8601 format)",
    ),
) -> dict[str, Any]:
    """Get analytics summary for an MCP Server Workspace.

    Args:
        mcp_server_workspace_id: MCP Server Workspace UUID
        current_user: Current authenticated user
        db: Database session
        period: Time period (hour, day, week, month)
        start_time: Custom start time
        end_time: Custom end time

    Returns:
        Analytics summary

    Raises:
        400: Invalid UUID format or invalid time range
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
        current_user, str(workspace.organisation_id), "access analytics for"
    )

    # Calculate time range
    now = datetime.now(timezone.utc)
    effective_end_time = end_time or now
    effective_start_time = start_time or (effective_end_time - PERIOD_DELTAS[period])

    # Validate time range
    if effective_start_time > effective_end_time:
        raise_bad_request("start_time must be before end_time")

    # Get analytics
    log_repo = AuditLogRepository(db)
    analytics = await log_repo.get_analytics(
        mcp_server_workspace_id=workspace_uuid,
        start_time=effective_start_time,
        end_time=effective_end_time,
    )

    return {
        "mcp_server_workspace_id": mcp_server_workspace_id,
        "period": period.value,
        "start_time": effective_start_time.isoformat(),
        "end_time": effective_end_time.isoformat(),
        "summary": {
            "total_requests": analytics["total_requests"],
            "allowed_requests": analytics["allowed_requests"],
            "blocked_requests": analytics["blocked_requests"],
            "block_rate_percent": round(analytics["block_rate"], 2),
            "avg_latency_ms": analytics["avg_latency_ms"],
        },
    }


@router.get(
    "/mcp-server-workspaces/{mcp_server_workspace_id}/analytics/guardrails",
    summary="Get guardrail analytics",
    description="""
Get guardrail-specific analytics for an MCP Server Workspace.

Shows which guardrails were triggered most frequently during the specified period.
""",
)
async def get_guardrail_analytics(
    mcp_server_workspace_id: str,
    current_user: CurrentUser,
    db: DbSession,
    period: AnalyticsPeriod = Query(
        AnalyticsPeriod.DAY,
        description="Time period for analytics",
    ),
) -> dict[str, Any]:
    """Get guardrail-specific analytics.

    Args:
        mcp_server_workspace_id: MCP Server Workspace UUID
        current_user: Current authenticated user
        db: Database session
        period: Time period

    Returns:
        Guardrail analytics

    Raises:
        400: Invalid UUID format
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
        current_user, str(workspace.organisation_id), "access analytics for"
    )

    # Calculate time range
    now = datetime.now(timezone.utc)
    start_time = now - PERIOD_DELTAS[period]

    # Query logs with guardrail triggers
    log_repo = AuditLogRepository(db)
    logs = await log_repo.query(
        mcp_server_workspace_id=workspace_uuid,
        start_time=start_time,
        end_time=now,
        offset=0,
        limit=10000,  # Get all for analytics
    )

    # Aggregate guardrail triggers from guardrail_results
    guardrail_counts: dict[str, int] = {}
    for log in logs:
        if log.guardrail_results:
            for guardrail_type, result in log.guardrail_results.items():
                if isinstance(result, dict) and result.get("triggered"):
                    guardrail_counts[guardrail_type] = (
                        guardrail_counts.get(guardrail_type, 0) + 1
                    )

    # Sort by count
    sorted_guardrails = sorted(
        guardrail_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    return {
        "mcp_server_workspace_id": mcp_server_workspace_id,
        "period": period.value,
        "start_time": start_time.isoformat(),
        "end_time": now.isoformat(),
        "guardrail_triggers": [
            {"guardrail": g, "count": c} for g, c in sorted_guardrails
        ],
        "total_triggers": sum(guardrail_counts.values()),
    }
