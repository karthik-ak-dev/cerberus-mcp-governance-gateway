"""
Analytics API Integration Tests

Tests for the analytics endpoints.

Analytics provide dashboard and reporting data for MCP server workspaces,
including request counts, block rates, latency metrics, and guardrail triggers.

Endpoint Summary:
=================
- GET /api/v1/analytics/mcp-server-workspaces/{id}/analytics           - Get workspace analytics
- GET /api/v1/analytics/mcp-server-workspaces/{id}/analytics/guardrails - Get guardrail analytics

Authorization:
==============
- All endpoints require authenticated user with access to the organisation
- OrgViewer can read analytics for their organisation's workspaces
- Cross-organisation access is forbidden

Query Parameters:
=================
- period: Time period for analytics (hour, day, week, month)
- start_time: Custom start time (ISO 8601 format)
- end_time: Custom end time (ISO 8601 format)
"""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient


# =============================================================================
# WORKSPACE ANALYTICS TESTS
# =============================================================================


class TestGetWorkspaceAnalytics:
    """
    Tests for GET /api/v1/analytics/mcp-server-workspaces/{id}/analytics endpoint.

    Returns analytics summary for a workspace including:
    - Total requests
    - Allowed/blocked requests
    - Block rate percentage
    - Average latency
    """

    async def test_get_analytics_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can get analytics for a workspace.

        Scenario: Request analytics for an existing workspace.
        Expected: 200 OK with analytics summary.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mcp_server_workspace_id"] == str(test_workspace.id)
        assert "period" in data
        assert "start_time" in data
        assert "end_time" in data
        assert "summary" in data
        assert "total_requests" in data["summary"]
        assert "allowed_requests" in data["summary"]
        assert "blocked_requests" in data["summary"]
        assert "block_rate_percent" in data["summary"]
        assert "avg_latency_ms" in data["summary"]

    async def test_get_analytics_with_period_hour(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can get analytics for the last hour.

        Scenario: Request analytics with period=hour.
        Expected: 200 OK with period set to hour.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
            params={"period": "hour"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "hour"

    async def test_get_analytics_with_period_day(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can get analytics for the last day (default).

        Scenario: Request analytics with period=day.
        Expected: 200 OK with period set to day.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
            params={"period": "day"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "day"

    async def test_get_analytics_with_period_week(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can get analytics for the last week.

        Scenario: Request analytics with period=week.
        Expected: 200 OK with period set to week.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
            params={"period": "week"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "week"

    async def test_get_analytics_with_period_month(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can get analytics for the last month.

        Scenario: Request analytics with period=month.
        Expected: 200 OK with period set to month.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
            params={"period": "month"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "month"

    async def test_get_analytics_with_custom_time_range(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can get analytics with custom start_time and end_time.

        Scenario: Request analytics with specific time range.
        Expected: 200 OK with custom time range in response.
        """
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(hours=2)).isoformat()
        end_time = now.isoformat()

        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
            params={
                "start_time": start_time,
                "end_time": end_time,
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 200

    async def test_get_analytics_invalid_time_range(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Returns 400 when start_time is after end_time.

        Scenario: Request analytics with start_time > end_time.
        Expected: 400 Bad Request.
        """
        now = datetime.now(timezone.utc)
        start_time = now.isoformat()
        end_time = (now - timedelta(hours=2)).isoformat()  # Before start

        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
            params={
                "start_time": start_time,
                "end_time": end_time,
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    async def test_get_analytics_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent workspace.

        Scenario: Request analytics for non-existent workspace.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{make_uuid()}/analytics",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    async def test_get_analytics_invalid_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Scenario: Request analytics with malformed UUID.
        Expected: 400 Bad Request.
        """
        response = await client.get(
            "/api/v1/analytics/mcp-server-workspaces/not-a-uuid/analytics",
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    async def test_get_analytics_org_viewer_allowed(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_workspace,
    ):
        """
        OrgViewer can get analytics for their org's workspace.

        Scenario: Viewer requests analytics.
        Expected: 200 OK.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    async def test_get_analytics_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot get analytics for workspace in another organisation.

        Scenario: OrgAdmin of Org B tries to get Org A's workspace analytics.
        Expected: 403 Forbidden.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    async def test_get_analytics_unauthenticated(
        self,
        client: AsyncClient,
        test_workspace,
    ):
        """
        Unauthenticated requests cannot get analytics.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics",
        )

        assert response.status_code == 401


# =============================================================================
# GUARDRAIL ANALYTICS TESTS
# =============================================================================


class TestGetGuardrailAnalytics:
    """
    Tests for GET /api/v1/analytics/mcp-server-workspaces/{id}/analytics/guardrails endpoint.

    Returns guardrail-specific analytics showing which guardrails
    were triggered most frequently during the specified period.
    """

    async def test_get_guardrail_analytics_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can get guardrail analytics for a workspace.

        Scenario: Request guardrail analytics for an existing workspace.
        Expected: 200 OK with guardrail trigger data.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics/guardrails",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mcp_server_workspace_id"] == str(test_workspace.id)
        assert "period" in data
        assert "start_time" in data
        assert "end_time" in data
        assert "guardrail_triggers" in data
        assert isinstance(data["guardrail_triggers"], list)
        assert "total_triggers" in data

    async def test_get_guardrail_analytics_with_period(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can get guardrail analytics with specific period.

        Scenario: Request guardrail analytics with period=week.
        Expected: 200 OK with period set to week.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics/guardrails",
            params={"period": "week"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "week"

    async def test_get_guardrail_analytics_trigger_format(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Guardrail triggers have correct format.

        Scenario: Check the structure of guardrail_triggers array.
        Expected: Each trigger has guardrail and count fields.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics/guardrails",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # If there are triggers, verify format
        for trigger in data["guardrail_triggers"]:
            assert "guardrail" in trigger
            assert "count" in trigger
            assert isinstance(trigger["count"], int)

    async def test_get_guardrail_analytics_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent workspace.

        Scenario: Request guardrail analytics for non-existent workspace.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{make_uuid()}/analytics/guardrails",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    async def test_get_guardrail_analytics_invalid_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Scenario: Request guardrail analytics with malformed UUID.
        Expected: 400 Bad Request.
        """
        response = await client.get(
            "/api/v1/analytics/mcp-server-workspaces/invalid-uuid/analytics/guardrails",
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    async def test_get_guardrail_analytics_org_viewer_allowed(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_workspace,
    ):
        """
        OrgViewer can get guardrail analytics.

        Scenario: Viewer requests guardrail analytics.
        Expected: 200 OK.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics/guardrails",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    async def test_get_guardrail_analytics_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot get guardrail analytics for workspace in another organisation.

        Scenario: OrgAdmin of Org B tries to get Org A's guardrail analytics.
        Expected: 403 Forbidden.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics/guardrails",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    async def test_get_guardrail_analytics_unauthenticated(
        self,
        client: AsyncClient,
        test_workspace,
    ):
        """
        Unauthenticated requests cannot get guardrail analytics.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics/guardrails",
        )

        assert response.status_code == 401

    async def test_get_guardrail_analytics_invalid_period(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Returns 422 for invalid period value.

        Scenario: Request guardrail analytics with invalid period.
        Expected: 422 Unprocessable Entity.
        """
        response = await client.get(
            f"/api/v1/analytics/mcp-server-workspaces/{test_workspace.id}/analytics/guardrails",
            params={"period": "invalid_period"},
            headers=org_admin_headers,
        )

        assert response.status_code == 422
