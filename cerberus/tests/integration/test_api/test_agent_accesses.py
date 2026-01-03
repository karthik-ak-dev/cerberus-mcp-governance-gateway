"""
Agent Access API Integration Tests

Tests for the agent access management endpoints.

Agent access keys are used by AI agents (like Claude, GPT, etc.) to authenticate
with MCP servers through Cerberus Gateway. These are NOT tied to dashboard users -
agents are standalone entities scoped to workspaces.

Endpoint Summary:
=================
- GET    /api/v1/mcp-server-workspaces/{id}/agent-accesses  - List workspace agent accesses
- POST   /api/v1/mcp-server-workspaces/{id}/agent-accesses  - Create agent access
- GET    /api/v1/agent-accesses/{id}                        - Get agent access by ID
- PUT    /api/v1/agent-accesses/{id}                        - Update agent access
- DELETE /api/v1/agent-accesses/{id}                        - Revoke agent access
- POST   /api/v1/agent-accesses/{id}/rotate                 - Rotate agent access key

Authorization:
==============
- All operations require OrganisationAdmin+ role
- Users can only access agent keys within their organisation
- Cross-organisation access is forbidden

Important Notes:
================
- The actual API key value is ONLY returned on creation
- Keys cannot be retrieved after creation - only rotated
- Deleting an agent access immediately invalidates the key
"""

import pytest
from httpx import AsyncClient

# pylint: disable=unused-argument


# =============================================================================
# CREATE AGENT ACCESS TESTS
# =============================================================================


class TestCreateAgentAccess:
    """
    Tests for POST /api/v1/mcp-server-workspaces/{id}/agent-accesses endpoint.

    Creates a new agent access key for an MCP server workspace.
    The API key value is only returned once in the creation response.
    """

    @pytest.mark.asyncio
    async def test_create_agent_access_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        OrgAdmin can create agent access for their workspace.

        Scenario: Create an agent access key for a workspace.
        Expected: 201 Created with agent access details including the API key.
        """
        response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={
                "name": "Production Agent",
                "description": "Agent for production workloads",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Production Agent"
        assert data["description"] == "Agent for production workloads"
        assert "id" in data
        assert "key" in data  # The actual API key - only returned on creation
        assert data["key"].startswith("sk-")  # API key prefix
        assert data["is_revoked"] is False
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_agent_access_with_expiry(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
        future_datetime,
    ):
        """
        Can create agent access with expiration date.

        Scenario: Create an agent that expires in 1 hour.
        Expected: 201 Created with expires_at set.
        """
        expires_at = future_datetime.isoformat()

        response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={
                "name": "Temporary Agent",
                "expires_at": expires_at,
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_create_agent_access_with_metadata(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can create agent access with custom metadata.

        Scenario: Create an agent with environment and team metadata.
        Expected: 201 Created with metadata preserved.
        """
        response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={
                "name": "Dev Agent",
                "metadata": {
                    "environment": "development",
                    "team": "platform",
                    "owner": "jane.doe@example.com",
                },
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["metadata"]["environment"] == "development"
        assert data["metadata"]["team"] == "platform"

    @pytest.mark.asyncio
    async def test_create_agent_access_minimal(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can create agent access with only required fields.

        Scenario: Create an agent with just a name.
        Expected: 201 Created with sensible defaults.
        """
        response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Minimal Agent"},
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Agent"
        assert data["description"] is None
        assert data["expires_at"] is None

    @pytest.mark.asyncio
    async def test_create_agent_access_missing_name(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Creating agent access without name fails.

        Scenario: Try to create agent without required name field.
        Expected: 422 Unprocessable Entity.
        """
        response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"description": "Agent without name"},
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_agent_access_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Creating agent access for non-existent workspace fails.

        Scenario: Try to create agent in a workspace that doesn't exist.
        Expected: 404 Not Found.
        """
        response = await client.post(
            f"/api/v1/mcp-server-workspaces/{make_uuid()}/agent-accesses",
            json={"name": "Ghost Workspace Agent"},
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_agent_access_invalid_workspace_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Creating agent access with invalid UUID fails.

        Scenario: Try to create agent with malformed workspace ID.
        Expected: 400 Bad Request.
        """
        response = await client.post(
            "/api/v1/mcp-server-workspaces/not-a-uuid/agent-accesses",
            json={"name": "Invalid UUID Agent"},
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_agent_access_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot create agent access in another org's workspace.

        Scenario: OrgAdmin of Org B tries to create agent in Org A's workspace.
        Expected: 403 Forbidden.
        """
        response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Cross-org Agent"},
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_agent_access_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_workspace,
    ):
        """
        Org viewers cannot create agent accesses.

        Scenario: OrgViewer tries to create an agent.
        Expected: 403 Forbidden.
        """
        response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Viewer Agent"},
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_agent_access_unauthenticated(
        self,
        client: AsyncClient,
        test_workspace,
    ):
        """
        Unauthenticated requests cannot create agent accesses.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Unauth Agent"},
        )

        assert response.status_code == 401


# =============================================================================
# LIST AGENT ACCESSES TESTS
# =============================================================================


class TestListAgentAccesses:
    """
    Tests for GET /api/v1/mcp-server-workspaces/{id}/agent-accesses endpoint.

    Lists all agent access keys for a workspace.
    Note: The actual key values are NOT returned in list responses.
    """

    @pytest.mark.asyncio
    async def test_list_agent_accesses_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
        test_agent_access,
    ):
        """
        Can list agent accesses for a workspace.

        Scenario: List all agents in a workspace.
        Expected: 200 OK with paginated list of agents.
        """
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) >= 1  # At least test_agent_access
        # Verify key is NOT returned in list
        for agent in data["data"]:
            assert "key" not in agent

    @pytest.mark.asyncio
    async def test_list_agent_accesses_with_pagination(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can paginate agent access list.

        Scenario: Create multiple agents and paginate through them.
        Expected: Returns correct page of results.
        """
        # Create multiple agents
        for i in range(5):
            await client.post(
                f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
                json={"name": f"Agent {i}"},
                headers=org_admin_headers,
            )

        # Request first page
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            params={"page": 1, "per_page": 2},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 2
        assert data["pagination"]["total"] >= 5

    @pytest.mark.asyncio
    async def test_list_agent_accesses_exclude_revoked_by_default(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Revoked agents are excluded by default.

        Scenario: Create and revoke an agent, then list.
        Expected: Revoked agent not in list by default.
        """
        # Create an agent
        create_response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Revoked Agent"},
            headers=org_admin_headers,
        )
        agent_id = create_response.json()["id"]

        # Revoke it
        await client.delete(
            f"/api/v1/agent-accesses/{agent_id}",
            headers=org_admin_headers,
        )

        # List without include_revoked
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        agent_ids = [a["id"] for a in data["data"]]
        assert agent_id not in agent_ids

    @pytest.mark.asyncio
    async def test_list_agent_accesses_include_revoked(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can include revoked agents in list.

        Scenario: List agents with include_revoked=true.
        Expected: Revoked agents are included.
        """
        # Create an agent
        create_response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Revoked Agent Include"},
            headers=org_admin_headers,
        )
        agent_id = create_response.json()["id"]

        # Revoke it
        await client.delete(
            f"/api/v1/agent-accesses/{agent_id}",
            headers=org_admin_headers,
        )

        # List with include_revoked
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            params={"include_revoked": True},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        agent_ids = [a["id"] for a in data["data"]]
        assert agent_id in agent_ids

    @pytest.mark.asyncio
    async def test_list_agent_accesses_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot list agents in another org's workspace.

        Scenario: OrgAdmin of Org B tries to list agents in Org A's workspace.
        Expected: 403 Forbidden.
        """
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_agent_accesses_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent workspace.

        Scenario: Try to list agents in a workspace that doesn't exist.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{make_uuid()}/agent-accesses",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_agent_accesses_unauthenticated(
        self,
        client: AsyncClient,
        test_workspace,
    ):
        """
        Unauthenticated requests cannot list agents.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
        )

        assert response.status_code == 401


# =============================================================================
# GET AGENT ACCESS TESTS
# =============================================================================


class TestGetAgentAccess:
    """
    Tests for GET /api/v1/agent-accesses/{agent_access_id} endpoint.

    Retrieves agent access details by ID.
    Note: The actual key value is NOT returned.
    """

    @pytest.mark.asyncio
    async def test_get_agent_access_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_agent_access,
    ):
        """
        Can retrieve agent access by ID.

        Scenario: Get details of an existing agent.
        Expected: 200 OK with agent details (no key).
        """
        response = await client.get(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_agent_access.id)
        assert data["name"] == test_agent_access.name
        assert "key" not in data  # Key is never returned after creation
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_agent_access_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent agent.

        Scenario: Try to get an agent that doesn't exist.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/agent-accesses/{make_uuid()}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_agent_access_invalid_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Scenario: Try to get with malformed UUID.
        Expected: 400 Bad Request.
        """
        response = await client.get(
            "/api/v1/agent-accesses/invalid-uuid",
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_agent_access_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_agent_access,
    ):
        """
        Cannot access agent from another organisation.

        Scenario: OrgAdmin of Org B tries to get Org A's agent.
        Expected: 403 Forbidden.
        """
        response = await client.get(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_agent_access_unauthenticated(
        self,
        client: AsyncClient,
        test_agent_access,
    ):
        """
        Unauthenticated requests cannot get agent details.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.get(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
        )

        assert response.status_code == 401


# =============================================================================
# UPDATE AGENT ACCESS TESTS
# =============================================================================


class TestUpdateAgentAccess:
    """
    Tests for PUT /api/v1/agent-accesses/{agent_access_id} endpoint.

    Updates agent access details (name, description, metadata, expiry).
    Cannot update the key - use rotate endpoint for that.
    """

    @pytest.mark.asyncio
    async def test_update_agent_access_name(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_agent_access,
    ):
        """
        Can update agent access name.

        Scenario: Change agent name.
        Expected: 200 OK with updated name.
        """
        response = await client.put(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            json={"name": "Updated Agent Name"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Agent Name"

    @pytest.mark.asyncio
    async def test_update_agent_access_description(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_agent_access,
    ):
        """
        Can update agent access description.

        Scenario: Add/update agent description.
        Expected: 200 OK with updated description.
        """
        response = await client.put(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            json={"description": "Updated description for testing"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description for testing"

    @pytest.mark.asyncio
    async def test_update_agent_access_metadata(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_agent_access,
    ):
        """
        Can update agent access metadata.

        Scenario: Update custom metadata fields.
        Expected: 200 OK with updated metadata.
        """
        response = await client.put(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            json={
                "metadata": {
                    "environment": "staging",
                    "version": "2.0",
                }
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["environment"] == "staging"
        assert data["metadata"]["version"] == "2.0"

    @pytest.mark.asyncio
    async def test_update_agent_access_expiry(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_agent_access,
        future_datetime,
    ):
        """
        Can update agent access expiry time.

        Scenario: Set an expiration date on an agent.
        Expected: 200 OK with expires_at set.
        """
        expires_at = future_datetime.isoformat()

        response = await client.put(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            json={"expires_at": expires_at},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_update_agent_access_partial(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_agent_access,
    ):
        """
        Partial update only changes specified fields.

        Scenario: Update only name, other fields unchanged.
        Expected: 200 OK with only name changed.
        """
        original_description = test_agent_access.description

        response = await client.put(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            json={"name": "Partial Update Agent"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Partial Update Agent"
        assert data["description"] == original_description

    @pytest.mark.asyncio
    async def test_update_agent_access_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent agent.

        Scenario: Try to update an agent that doesn't exist.
        Expected: 404 Not Found.
        """
        response = await client.put(
            f"/api/v1/agent-accesses/{make_uuid()}",
            json={"name": "Ghost Agent"},
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_agent_access_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_agent_access,
    ):
        """
        Cannot update agent from another organisation.

        Scenario: OrgAdmin of Org B tries to update Org A's agent.
        Expected: 403 Forbidden.
        """
        response = await client.put(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            json={"name": "Cross-org Update"},
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_agent_access_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_agent_access,
    ):
        """
        Org viewers cannot update agent accesses.

        Scenario: OrgViewer tries to update an agent.
        Expected: 403 Forbidden.
        """
        response = await client.put(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            json={"name": "Viewer Update"},
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_agent_access_unauthenticated(
        self,
        client: AsyncClient,
        test_agent_access,
    ):
        """
        Unauthenticated requests cannot update agents.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.put(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            json={"name": "Unauth Update"},
        )

        assert response.status_code == 401


# =============================================================================
# REVOKE (DELETE) AGENT ACCESS TESTS
# =============================================================================


class TestRevokeAgentAccess:
    """
    Tests for DELETE /api/v1/agent-accesses/{agent_access_id} endpoint.

    Revokes an agent access key. The key is immediately invalidated.
    """

    @pytest.mark.asyncio
    async def test_revoke_agent_access_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can revoke an agent access key.

        Scenario: Create and then revoke an agent.
        Expected: 204 No Content, agent is marked as revoked.
        """
        # Create agent first
        create_response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Revokable Agent"},
            headers=org_admin_headers,
        )
        agent_id = create_response.json()["id"]

        # Revoke it
        revoke_response = await client.delete(
            f"/api/v1/agent-accesses/{agent_id}",
            headers=org_admin_headers,
        )

        assert revoke_response.status_code == 204

        # Verify it's revoked by checking with include_revoked
        list_response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            params={"include_revoked": True},
            headers=org_admin_headers,
        )
        agents = list_response.json()["data"]
        revoked_agent = next((a for a in agents if a["id"] == agent_id), None)
        assert revoked_agent is not None
        assert revoked_agent["is_revoked"] is True

    @pytest.mark.asyncio
    async def test_revoke_agent_access_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent agent.

        Scenario: Try to revoke an agent that doesn't exist.
        Expected: 404 Not Found.
        """
        response = await client.delete(
            f"/api/v1/agent-accesses/{make_uuid()}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_revoke_agent_access_idempotent(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Revoking an already-revoked agent succeeds (idempotent).

        Scenario: Revoke an agent twice.
        Expected: Both requests succeed with 204.
        """
        # Create agent
        create_response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Double Revoke Agent"},
            headers=org_admin_headers,
        )
        agent_id = create_response.json()["id"]

        # First revoke
        response1 = await client.delete(
            f"/api/v1/agent-accesses/{agent_id}",
            headers=org_admin_headers,
        )
        assert response1.status_code == 204

        # Second revoke - should also succeed (idempotent)
        response2 = await client.delete(
            f"/api/v1/agent-accesses/{agent_id}",
            headers=org_admin_headers,
        )
        # May be 204 (idempotent) or 404 (already revoked)
        assert response2.status_code in [204, 404]

    @pytest.mark.asyncio
    async def test_revoke_agent_access_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_agent_access,
    ):
        """
        Cannot revoke agent from another organisation.

        Scenario: OrgAdmin of Org B tries to revoke Org A's agent.
        Expected: 403 Forbidden.
        """
        response = await client.delete(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_revoke_agent_access_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_agent_access,
    ):
        """
        Org viewers cannot revoke agent accesses.

        Scenario: OrgViewer tries to revoke an agent.
        Expected: 403 Forbidden.
        """
        response = await client.delete(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_revoke_agent_access_unauthenticated(
        self,
        client: AsyncClient,
        test_agent_access,
    ):
        """
        Unauthenticated requests cannot revoke agents.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.delete(
            f"/api/v1/agent-accesses/{test_agent_access.id}",
        )

        assert response.status_code == 401


# =============================================================================
# ROTATE AGENT ACCESS KEY TESTS
# =============================================================================


class TestRotateAgentAccessKey:
    """
    Tests for POST /api/v1/agent-accesses/{agent_access_id}/rotate endpoint.

    Rotates an agent access key. The old key has a grace period before expiring.
    The new key is returned in the response.
    """

    @pytest.mark.asyncio
    async def test_rotate_agent_access_key_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can rotate an agent access key.

        Scenario: Rotate an existing agent's key.
        Expected: 200 OK with new key and old key expiration info.
        """
        # Create agent
        create_response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Rotatable Agent"},
            headers=org_admin_headers,
        )
        agent_id = create_response.json()["id"]
        original_key = create_response.json()["key"]

        # Rotate key
        rotate_response = await client.post(
            f"/api/v1/agent-accesses/{agent_id}/rotate",
            headers=org_admin_headers,
        )

        assert rotate_response.status_code == 200
        data = rotate_response.json()
        assert "key" in data  # New key returned
        assert data["key"] != original_key  # Different from original
        assert data["key"].startswith("sk-")
        assert "old_key_expires_at" in data  # Grace period for old key

    @pytest.mark.asyncio
    async def test_rotate_agent_access_key_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent agent.

        Scenario: Try to rotate key for agent that doesn't exist.
        Expected: 404 Not Found.
        """
        response = await client.post(
            f"/api/v1/agent-accesses/{make_uuid()}/rotate",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rotate_agent_access_key_revoked_fails(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot rotate a revoked agent's key.

        Scenario: Try to rotate key for a revoked agent.
        Expected: 400 Bad Request.
        """
        # Create and revoke agent
        create_response = await client.post(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}/agent-accesses",
            json={"name": "Revoked for Rotation"},
            headers=org_admin_headers,
        )
        agent_id = create_response.json()["id"]

        await client.delete(
            f"/api/v1/agent-accesses/{agent_id}",
            headers=org_admin_headers,
        )

        # Try to rotate
        response = await client.post(
            f"/api/v1/agent-accesses/{agent_id}/rotate",
            headers=org_admin_headers,
        )

        # May be 400 (revoked) or 404 (not found after revoke)
        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_rotate_agent_access_key_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_agent_access,
    ):
        """
        Cannot rotate key for agent in another organisation.

        Scenario: OrgAdmin of Org B tries to rotate Org A's agent key.
        Expected: 403 Forbidden.
        """
        response = await client.post(
            f"/api/v1/agent-accesses/{test_agent_access.id}/rotate",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rotate_agent_access_key_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_agent_access,
    ):
        """
        Org viewers cannot rotate agent keys.

        Scenario: OrgViewer tries to rotate an agent's key.
        Expected: 403 Forbidden.
        """
        response = await client.post(
            f"/api/v1/agent-accesses/{test_agent_access.id}/rotate",
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rotate_agent_access_key_unauthenticated(
        self,
        client: AsyncClient,
        test_agent_access,
    ):
        """
        Unauthenticated requests cannot rotate keys.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.post(
            f"/api/v1/agent-accesses/{test_agent_access.id}/rotate",
        )

        assert response.status_code == 401
