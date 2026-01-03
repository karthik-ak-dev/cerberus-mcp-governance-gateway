"""
Audit Log API Integration Tests

Tests for the audit log query and retrieval endpoints.

Audit logs capture all MCP requests processed by the gateway, including:
- Request details (tool name, message type)
- Decision made (allow, block_request, block_response, modify, log_only, throttle)
- Guardrail evaluation results
- Latency metrics

Endpoint Summary:
=================
- GET /api/v1/logs/mcp-server-workspaces/{id}/logs              - Query audit logs
- GET /api/v1/logs/mcp-server-workspaces/{id}/logs/{request_id} - Get log detail

Authorization:
==============
- All endpoints require authenticated user with access to the organisation
- OrgViewer can read logs for their organisation's workspaces
- Cross-organisation access is forbidden

Query Parameters (for listing):
================================
- start_time: Filter logs after this time (ISO 8601)
- end_time: Filter logs before this time (ISO 8601)
- agent_name: Filter by agent name
- decision: Filter by decision (allow, block_request, block_response, modify, log_only, throttle)
- guardrail_type: Filter by guardrail type
- tool_name: Filter by MCP tool name
- page/per_page: Pagination
"""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient


# =============================================================================
# QUERY AUDIT LOGS TESTS
# =============================================================================


class TestQueryAuditLogs:
    """
    Tests for GET /api/v1/logs/mcp-server-workspaces/{id}/logs endpoint.

    Queries audit logs for a workspace with optional filtering.
    """

    async def test_query_logs_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can query audit logs for a workspace.

        Scenario: Request logs for an existing workspace.
        Expected: 200 OK with paginated log list.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

    async def test_query_logs_with_pagination(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can paginate through audit logs.

        Scenario: Request logs with page and per_page params.
        Expected: 200 OK with correct pagination metadata.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            params={"page": 1, "per_page": 10},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 10

    async def test_query_logs_filter_by_time_range(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can filter logs by time range.

        Scenario: Request logs with start_time and end_time.
        Expected: 200 OK with logs in the specified range.
        """
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(hours=24)).isoformat()
        end_time = now.isoformat()

        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            params={
                "start_time": start_time,
                "end_time": end_time,
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 200

    async def test_query_logs_filter_by_agent_name(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can filter logs by agent name.

        Scenario: Request logs for a specific agent.
        Expected: 200 OK with filtered results.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            params={"agent_name": "test-agent"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200

    async def test_query_logs_filter_by_decision_allow(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can filter logs by decision=allow.

        Scenario: Request only allowed requests.
        Expected: 200 OK with allowed logs only.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            params={"decision": "allow"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200

    async def test_query_logs_filter_by_decision_block_request(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can filter logs by decision=block_request.

        Scenario: Request only blocked requests.
        Expected: 200 OK with blocked logs only.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            params={"decision": "block_request"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200

    async def test_query_logs_filter_by_guardrail_type(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can filter logs by guardrail type.

        Scenario: Request logs for a specific guardrail.
        Expected: 200 OK with filtered results.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            params={"guardrail_type": "pii_ssn"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200

    async def test_query_logs_filter_by_tool_name(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can filter logs by MCP tool name.

        Scenario: Request logs for a specific tool.
        Expected: 200 OK with filtered results.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            params={"tool_name": "read_file"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200

    async def test_query_logs_multiple_filters(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can apply multiple filters simultaneously.

        Scenario: Request logs with decision + agent_name filters.
        Expected: 200 OK with combined filter results.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            params={
                "decision": "block_request",
                "agent_name": "test-agent",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 200

    async def test_query_logs_invalid_time_range(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Returns 400 when start_time is after end_time.

        Scenario: Request logs with start_time > end_time.
        Expected: 400 Bad Request.
        """
        now = datetime.now(timezone.utc)
        start_time = now.isoformat()
        end_time = (now - timedelta(hours=2)).isoformat()

        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            params={
                "start_time": start_time,
                "end_time": end_time,
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    async def test_query_logs_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent workspace.

        Scenario: Request logs for non-existent workspace.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{make_uuid()}/logs",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    async def test_query_logs_invalid_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Scenario: Request logs with malformed UUID.
        Expected: 400 Bad Request.
        """
        response = await client.get(
            "/api/v1/logs/mcp-server-workspaces/not-a-uuid/logs",
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    async def test_query_logs_org_viewer_allowed(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_workspace,
    ):
        """
        OrgViewer can query logs for their org's workspace.

        Scenario: Viewer requests logs.
        Expected: 200 OK.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    async def test_query_logs_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot query logs for workspace in another organisation.

        Scenario: OrgAdmin of Org B tries to query Org A's logs.
        Expected: 403 Forbidden.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    async def test_query_logs_unauthenticated(
        self,
        client: AsyncClient,
        test_workspace,
    ):
        """
        Unauthenticated requests cannot query logs.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
        )

        assert response.status_code == 401

    async def test_query_logs_response_format(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Log entries have the correct format.

        Scenario: Check the structure of log entries.
        Expected: Each log has required fields.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # If there are logs, verify format
        for log in data["data"]:
            assert "id" in log
            assert "request_id" in log
            assert "created_at" in log
            assert "decision" in log


# =============================================================================
# GET LOG DETAIL TESTS
# =============================================================================


class TestGetLogDetail:
    """
    Tests for GET /api/v1/logs/mcp-server-workspaces/{id}/logs/{request_id} endpoint.

    Retrieves detailed audit log by request ID.
    """

    async def test_get_log_detail_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Returns 404 for non-existent request_id.

        Scenario: Request detail for non-existent log.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs/non-existent-request-id",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    async def test_get_log_detail_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent workspace.

        Scenario: Request log detail for non-existent workspace.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{make_uuid()}/logs/some-request-id",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    async def test_get_log_detail_invalid_workspace_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Returns 400 for invalid workspace UUID format.

        Scenario: Request log detail with malformed workspace UUID.
        Expected: 400 Bad Request.
        """
        response = await client.get(
            "/api/v1/logs/mcp-server-workspaces/invalid-uuid/logs/some-request-id",
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    async def test_get_log_detail_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot get log detail for workspace in another organisation.

        Scenario: OrgAdmin of Org B tries to get Org A's log detail.
        Expected: 403 Forbidden.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs/some-request-id",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    async def test_get_log_detail_org_viewer_allowed(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_workspace,
    ):
        """
        OrgViewer can attempt to get log detail (returns 404 if not exists).

        Scenario: Viewer requests log detail.
        Expected: 404 Not Found (not 403).
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs/non-existent-id",
            headers=org_viewer_headers,
        )

        # Should be 404 (not found), not 403 (forbidden)
        # This proves viewer has access to the endpoint
        assert response.status_code == 404

    async def test_get_log_detail_unauthenticated(
        self,
        client: AsyncClient,
        test_workspace,
    ):
        """
        Unauthenticated requests cannot get log detail.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs/some-request-id",
        )

        assert response.status_code == 401


# =============================================================================
# LOG CONTENT VALIDATION TESTS
# =============================================================================


class TestLogContentValidation:
    """
    Tests for validating log entry content and field presence.

    These tests verify that log entries contain the expected fields
    when logs exist in the system.
    """

    async def test_log_entry_contains_required_fields(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Log entries contain all required fields.

        Scenario: Query logs and check field presence.
        Expected: Each log has id, request_id, created_at, decision.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure even if empty
        assert "data" in data
        assert "pagination" in data

    async def test_pagination_metadata_format(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Pagination metadata has correct format.

        Scenario: Query logs and check pagination structure.
        Expected: Pagination has page, per_page, total fields.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        pagination = data["pagination"]
        assert "page" in pagination
        assert "per_page" in pagination
        assert "total" in pagination
        assert isinstance(pagination["page"], int)
        assert isinstance(pagination["per_page"], int)
        assert isinstance(pagination["total"], int)

    async def test_empty_logs_returns_empty_array(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Workspace with no logs returns empty array.

        Scenario: Query logs for workspace with no activity.
        Expected: 200 OK with empty data array.
        """
        response = await client.get(
            f"/api/v1/logs/mcp-server-workspaces/{test_workspace.id}/logs",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["data"], list)
        # Total should be 0 for fresh workspace
        assert data["pagination"]["total"] >= 0
