"""
Audit Log Repository

Database operations specific to the AuditLog model.
Extends BaseRepository with audit log-specific query methods.

Common Operations:
==================
- create_decision_log() → Create audit log for a governance decision
- query()               → Search logs with multiple filters
- count_query()         → Count logs matching filters
- get_analytics()       → Get aggregated analytics for a period
- get_by_request_id()   → Get log by unique request ID

Key Concept - Audit Trail:
==========================
Every governance decision is logged for:
- Compliance: Prove what decisions were made and why
- Debugging: Understand why a request was blocked
- Analytics: Track patterns, identify issues
- Security: Detect anomalies and threats

What Gets Logged:
=================
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AUDIT LOG ENTRY                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CONTEXT:                                                                   │
│  - organisation_id, mcp_server_workspace_id: Where did this happen?        │
│  - agent_access_id, agent_name: Which agent made the request?              │
│  - request_id: Unique ID for correlation                                   │
│                                                                             │
│  REQUEST:                                                                   │
│  - message_type: "request" or "response"                                   │
│  - tool_name: Tool being invoked                                           │
│                                                                             │
│  DECISION:                                                                  │
│  - decision: What decision was made (DecisionAction enum values)           │
│  - decision_reason: Why this decision was made                             │
│                                                                             │
│  GUARDRAILS:                                                                │
│  - guardrail_results: Detailed results from each guardrail                 │
│                                                                             │
│  PERFORMANCE:                                                               │
│  - latency_ms: How long the decision took                                  │
│  - created_at: When it happened                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Usage in Decision Flow:
=======================
    async def log_decision(
        db: AsyncSession,
        context: AgentAccessContext,
        result: DecisionResult
    ):
        repo = AuditLogRepository(db)

        await repo.create_decision_log(
            organisation_id=context.organisation_id,
            mcp_server_workspace_id=context.mcp_server_workspace_id,
            agent_access_id=context.agent_access_id,
            agent_name=context.agent_name,
            request_id=context.request_id,
            message_type="request",
            decision=result.decision,
            decision_reason=result.reason,
            latency_ms=result.latency_ms,
            tool_name=context.tool_name,
            guardrail_results=result.guardrail_results
        )

Analytics Usage:
================
    async def get_dashboard_stats(
        db: AsyncSession,
        mcp_server_workspace_id: UUID,
        start: datetime,
        end: datetime
    ):
        repo = AuditLogRepository(db)

        stats = await repo.get_analytics(mcp_server_workspace_id, start, end)
        # Returns:
        # {
        #     "total_requests": 10000,
        #     "blocked_requests": 150,
        #     "allowed_requests": 9850,
        #     "block_rate": 1.5,
        #     "avg_latency_ms": 12.5
        # }
        return stats
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count

from app.config.constants import DecisionAction
from app.db.repositories.base import BaseRepository
from app.models.audit_log import AuditLog


class AuditLogRepository(BaseRepository[AuditLog]):
    """
    Repository for AuditLog database operations.

    Provides methods for:
    - Creating audit log entries
    - Querying logs with filters
    - Generating analytics and reports

    Note: Audit logs are typically insert-only (immutable).
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize AuditLogRepository.

        Args:
            session: Async database session
        """
        super().__init__(AuditLog, session)

    # ═══════════════════════════════════════════════════════════════════════════
    # CREATE METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def create_decision_log(
        self,
        organisation_id: UUID,
        mcp_server_workspace_id: UUID,
        request_id: str,
        agent_name: str,
        message_type: str,
        decision: str,
        decision_reason: str,
        latency_ms: int,
        tool_name: str,
        agent_access_id: UUID | None = None,
        session_id: str | None = None,
        guardrail_results: dict[str, Any] | None = None,
        request_summary: dict[str, Any] | None = None,
        response_summary: dict[str, Any] | None = None,
        modifications: list[dict[str, Any]] | None = None,
        ip_address: str | None = None,
        **kwargs: Any,
    ) -> AuditLog:
        """
        Create an audit log entry for a governance decision.

        This is a specialized create method with all the fields
        needed for a complete audit trail.

        Args:
            organisation_id: UUID of the organisation
            mcp_server_workspace_id: UUID of the workspace
            request_id: Unique identifier for this request
                        (for correlating request/response logs)
            agent_name: Name of the agent making the request
            message_type: "request" (outgoing) or "response" (incoming)
            decision: Decision outcome (DecisionAction enum value)
            decision_reason: Human-readable explanation of the decision
            latency_ms: Time taken to make decision
            tool_name: MCP tool being invoked
            agent_access_id: UUID of the agent access key used
            session_id: Session identifier for grouping related requests
            guardrail_results: Detailed results from each guardrail
            request_summary: Summary of the request (may be redacted)
            response_summary: Summary of the response (may be redacted)
            modifications: List of modifications made
            ip_address: Gateway IP address
            **kwargs: Any additional fields

        Returns:
            Created AuditLog entry

        Example:
            log = await repo.create_decision_log(
                organisation_id=org.id,
                mcp_server_workspace_id=workspace.id,
                request_id="req-abc123",
                agent_name="Production AI Agent",
                message_type="request",
                decision="block_request",
                decision_reason="Tool not allowed by RBAC policy",
                latency_ms=15,
                tool_name="filesystem/delete",
                guardrail_results={
                    "rbac": {
                        "status": "fail",
                        "reason": "Tool not allowed by RBAC policy"
                    }
                }
            )
        """
        return await self.create(
            organisation_id=organisation_id,
            mcp_server_workspace_id=mcp_server_workspace_id,
            request_id=request_id,
            agent_name=agent_name,
            agent_access_id=agent_access_id,
            message_type=message_type,
            decision=decision,
            decision_reason=decision_reason,
            latency_ms=latency_ms,
            tool_name=tool_name,
            session_id=session_id,
            guardrail_results=guardrail_results or {},
            request_summary=request_summary,
            response_summary=response_summary,
            modifications=modifications,
            ip_address=ip_address,
            **kwargs,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # QUERY METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def query(
        self,
        mcp_server_workspace_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        agent_name: str | None = None,
        decision: str | None = None,
        guardrail_type: str | None = None,
        tool_name: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """
        Query audit logs with multiple filters.

        Flexible query method for log exploration and debugging.
        All filters are optional and combined with AND logic.

        Args:
            mcp_server_workspace_id: UUID of the workspace (required)
            start_time: Only logs after this time
            end_time: Only logs before this time
            agent_name: Filter by agent name
            decision: Filter by decision (DecisionAction enum value)
            guardrail_type: Filter by guardrail type in results
            tool_name: Filter by MCP tool name
            offset: Pagination offset
            limit: Max records (default 100)

        Returns:
            List of matching audit logs (newest first)

        Example:
            # Find all blocked requests for Production Agent in the last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            blocked_logs = await repo.query(
                mcp_server_workspace_id=workspace.id,
                start_time=one_hour_ago,
                agent_name="Production AI Agent",
                decision="block_request"
            )

            for log in blocked_logs:
                print(f"{log.created_at}: {log.decision_reason}")

        SQL Generated:
            SELECT * FROM audit_logs
            WHERE mcp_server_workspace_id = '...'
              AND created_at >= '...'
              AND agent_name = 'Production AI Agent'
              AND decision = 'block_request'
            ORDER BY created_at DESC
            OFFSET 0 LIMIT 100
        """
        conditions = [AuditLog.mcp_server_workspace_id == mcp_server_workspace_id]

        # Add optional filters
        if start_time:
            conditions.append(AuditLog.created_at >= start_time)
        if end_time:
            conditions.append(AuditLog.created_at <= end_time)
        if agent_name:
            conditions.append(AuditLog.agent_name == agent_name)
        if decision:
            conditions.append(AuditLog.decision == decision)
        if tool_name:
            conditions.append(AuditLog.tool_name == tool_name)
        if guardrail_type:
            # Check if guardrail type exists in the guardrail_results JSONB
            conditions.append(AuditLog.guardrail_results.has_key(guardrail_type))

        result = await self.session.execute(
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(AuditLog.created_at.desc())  # Newest first
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_query(
        self,
        mcp_server_workspace_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        agent_name: str | None = None,
        decision: str | None = None,
    ) -> int:
        """
        Count audit logs matching filters.

        Same filters as query() but returns count only.
        Useful for pagination and summary statistics.

        Args:
            mcp_server_workspace_id: UUID of the workspace
            start_time: Only logs after this time
            end_time: Only logs before this time
            agent_name: Filter by agent name
            decision: Filter by decision

        Returns:
            Number of matching logs

        Example:
            # How many requests did the Production Agent make today?
            today_start = datetime.utcnow().replace(hour=0, minute=0)

            count = await repo.count_query(
                mcp_server_workspace_id=workspace.id,
                start_time=today_start,
                agent_name="Production AI Agent"
            )
            print(f"Agent made {count} requests today")

        SQL Generated:
            SELECT COUNT(*) FROM audit_logs
            WHERE mcp_server_workspace_id = '...'
              AND created_at >= '...'
              AND agent_name = '...'
        """
        conditions = [AuditLog.mcp_server_workspace_id == mcp_server_workspace_id]

        if start_time:
            conditions.append(AuditLog.created_at >= start_time)
        if end_time:
            conditions.append(AuditLog.created_at <= end_time)
        if agent_name:
            conditions.append(AuditLog.agent_name == agent_name)
        if decision:
            conditions.append(AuditLog.decision == decision)

        result = await self.session.execute(
            select(count(AuditLog.id)).select_from(AuditLog).where(and_(*conditions))
        )
        return result.scalar() or 0

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYTICS METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_analytics(
        self,
        mcp_server_workspace_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """
        Get analytics summary for a time period.

        Computes aggregated statistics for dashboards and reports.
        Uses a single aggregation query for efficiency.

        Args:
            mcp_server_workspace_id: UUID of the workspace
            start_time: Period start (inclusive)
            end_time: Period end (inclusive)

        Returns:
            Analytics dictionary:
            {
                "total_requests": 10000,
                "blocked_requests": 150,
                "allowed_requests": 9850,
                "block_rate": 1.5,  # percentage
                "avg_latency_ms": 12.5
            }

        Example:
            # Get last 24 hours analytics
            now = datetime.utcnow()
            yesterday = now - timedelta(days=1)

            stats = await repo.get_analytics(
                mcp_server_workspace_id=workspace.id,
                start_time=yesterday,
                end_time=now
            )

            print(f"Block rate: {stats['block_rate']:.1f}%")
            print(f"Avg latency: {stats['avg_latency_ms']:.1f}ms")

        SQL Generated:
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE decision IN ('block_request', 'block_response', 'throttle')) as blocked,
                AVG(latency_ms) as avg_latency
            FROM audit_logs
            WHERE mcp_server_workspace_id = '...'
              AND created_at >= '...'
              AND created_at <= '...'
        """
        # Single aggregation query for all metrics
        # Uses ix_audit_logs_workspace_created index
        # Block-type decisions include block_request, block_response, and throttle
        blocked_decisions = (
            DecisionAction.BLOCK_REQUEST.value,
            DecisionAction.BLOCK_RESPONSE.value,
            DecisionAction.THROTTLE.value,
        )
        result = await self.session.execute(
            select(
                count(AuditLog.id).label("total"),
                func.sum(
                    case((AuditLog.decision.in_(blocked_decisions), 1), else_=0)
                ).label("blocked"),
                func.avg(AuditLog.latency_ms).label("avg_latency"),
            )
            .select_from(AuditLog)
            .where(
                AuditLog.mcp_server_workspace_id == mcp_server_workspace_id,
                AuditLog.created_at >= start_time,
                AuditLog.created_at <= end_time,
            )
        )
        row = result.one()

        total = row.total or 0
        blocked = row.blocked or 0
        avg_latency = row.avg_latency or 0

        return {
            "total_requests": total,
            "blocked_requests": blocked,
            "allowed_requests": total - blocked,
            "block_rate": (blocked / total * 100) if total > 0 else 0,
            "avg_latency_ms": round(float(avg_latency), 2),
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # LOOKUP METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_by_request_id(self, request_id: str) -> AuditLog | None:
        """
        Get audit log by request ID.

        Each governance request has a unique ID for correlation.
        This allows looking up the full audit trail for a specific request.

        Args:
            request_id: Unique request identifier

        Returns:
            AuditLog if found, None otherwise

        Example:
            # From an error response, look up what happened
            log = await repo.get_by_request_id("req-abc123")
            if log:
                print(f"Decision: {log.decision}")
                print(f"Reason: {log.decision_reason}")
                print(f"Guardrails: {log.guardrail_results}")

        SQL Generated:
            SELECT * FROM audit_logs WHERE request_id = 'req-abc123'
        """
        result = await self.session.execute(
            select(AuditLog).where(AuditLog.request_id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_by_organisation(
        self,
        organisation_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """
        Get all audit logs for an organisation.

        Useful for organisation-level reporting and compliance.

        Args:
            organisation_id: UUID of the organisation
            start_time: Only logs after this time
            end_time: Only logs before this time
            offset: Pagination offset
            limit: Max records

        Returns:
            List of audit logs for the organisation
        """
        conditions = [AuditLog.organisation_id == organisation_id]

        if start_time:
            conditions.append(AuditLog.created_at >= start_time)
        if end_time:
            conditions.append(AuditLog.created_at <= end_time)

        result = await self.session.execute(
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
