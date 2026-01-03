"""
MCP Server Workspace API Integration Tests

Comprehensive tests for the MCP server workspace management endpoints.
Workspaces represent MCP server instances that agents connect to.

Endpoints Tested:
    - POST   /api/v1/organisations/{org_id}/mcp-server-workspaces     - Create workspace
    - GET    /api/v1/organisations/{org_id}/mcp-server-workspaces     - List workspaces
    - GET    /api/v1/mcp-server-workspaces/{id}                       - Get workspace
    - PUT    /api/v1/mcp-server-workspaces/{id}                       - Update workspace
    - DELETE /api/v1/mcp-server-workspaces/{id}                       - Delete workspace

Authorization Rules:
    - SuperAdmin: Full access to all workspaces
    - OrgAdmin: Full access to workspaces in their organisation
    - OrgViewer: Read-only access to workspaces in their organisation

Test Categories:
    1. Success Cases - Happy path scenarios
    2. Validation Errors - Invalid input handling
    3. Authorization - Role-based access control
    4. Not Found - Non-existent resource handling
    5. Edge Cases - Boundary conditions and special scenarios
"""

from httpx import AsyncClient

# pylint: disable=unused-argument


# =============================================================================
# CREATE WORKSPACE TESTS
# =============================================================================


class TestCreateWorkspace:
    """
    Tests for POST /api/v1/organisations/{org_id}/mcp-server-workspaces endpoint.

    This endpoint creates a new MCP server workspace within an organisation.
    OrgAdmin or higher can create workspaces.

    Request Body:
        - name (str, required): Workspace display name
        - slug (str, required): URL-friendly identifier (unique within org)
        - environment (str, optional): Environment type (development/staging/production)
        - mcp_endpoint_url (str, required): MCP server endpoint URL
        - description (str, optional): Workspace description
        - settings (dict, optional): Workspace-specific settings

    Response: McpServerWorkspaceResponse with id, name, slug, settings, timestamps
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_create_workspace_success_minimal(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can create workspace with required fields only.

        Given: Authenticated as OrgAdmin
        When: POST /organisations/{org_id}/mcp-server-workspaces with required fields
        Then: Returns 201 with workspace details
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Production Workspace",
                "slug": "production",
                "mcp_endpoint_url": "https://mcp.example.com/production",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "Production Workspace"
        assert data["slug"] == "production"
        assert data["mcp_endpoint_url"] == "https://mcp.example.com/production"
        assert data["organisation_id"] == str(test_organisation.id)
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_workspace_success_full(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can create workspace with all optional fields.

        Given: Authenticated as OrgAdmin
        When: POST with all fields including optional ones
        Then: Returns 201 with all fields populated
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Staging Environment",
                "slug": "staging-env",
                "description": "Pre-production testing environment",
                "environment": "staging",
                "mcp_endpoint_url": "https://mcp.example.com/staging",
                "settings": {
                    "log_level": "verbose",
                    "fail_mode": "open",
                },
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "Staging Environment"
        assert data["slug"] == "staging-env"
        assert data["description"] == "Pre-production testing environment"
        assert data["environment"] == "staging"
        assert data["settings"]["log_level"] == "verbose"

    async def test_create_workspace_super_admin_any_org(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_organisation,
    ):
        """
        SuperAdmin can create workspace in any organisation.

        Given: Authenticated as SuperAdmin
        When: POST to any organisation
        Then: Returns 201 with workspace created
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "SuperAdmin Created Workspace",
                "slug": "super-admin-ws",
                "mcp_endpoint_url": "https://mcp.example.com/super",
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 201

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    async def test_create_workspace_missing_name(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails when name is missing.

        Given: Authenticated as OrgAdmin
        When: POST without name field
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "slug": "missing-name",
                "mcp_endpoint_url": "https://example.com",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    async def test_create_workspace_missing_slug(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails when slug is missing.

        Given: Authenticated as OrgAdmin
        When: POST without slug field
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Missing Slug Workspace",
                "mcp_endpoint_url": "https://example.com",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    async def test_create_workspace_missing_endpoint_url(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails when mcp_endpoint_url is missing.

        Given: Authenticated as OrgAdmin
        When: POST without mcp_endpoint_url field
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Missing URL Workspace",
                "slug": "missing-url",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    async def test_create_workspace_duplicate_slug(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails when slug already exists in organisation.

        Given: Workspace with slug exists
        When: POST with same slug
        Then: Returns 409 Conflict
        """
        # Create first workspace
        await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "First Workspace",
                "slug": "duplicate-slug",
                "mcp_endpoint_url": "https://example.com/first",
            },
            headers=org_admin_headers,
        )

        # Try to create with same slug
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Second Workspace",
                "slug": "duplicate-slug",
                "mcp_endpoint_url": "https://example.com/second",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 409

    async def test_create_workspace_invalid_environment(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails with invalid environment value.

        Given: Authenticated as OrgAdmin
        When: POST with invalid environment type
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Invalid Env Workspace",
                "slug": "invalid-env",
                "mcp_endpoint_url": "https://example.com",
                "environment": "invalid_environment",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_create_workspace_requires_authentication(
        self,
        client: AsyncClient,
        test_organisation,
    ):
        """
        Creation requires authentication.

        Given: No authentication headers
        When: POST to create workspace
        Then: Returns 401 Unauthorized
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Unauthenticated Workspace",
                "slug": "unauth",
                "mcp_endpoint_url": "https://example.com",
            },
        )

        assert response.status_code == 401

    async def test_create_workspace_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_organisation,
    ):
        """
        OrgViewer cannot create workspaces.

        Given: Authenticated as OrgViewer
        When: POST to create workspace
        Then: Returns 403 Forbidden
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Viewer Created Workspace",
                "slug": "viewer-ws",
                "mcp_endpoint_url": "https://example.com",
            },
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    async def test_create_workspace_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin cannot create workspace in other organisations.

        Given: Authenticated as OrgAdmin of different org
        When: POST to other organisation
        Then: Returns 403 Forbidden
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Cross-org Workspace",
                "slug": "cross-org",
                "mcp_endpoint_url": "https://example.com",
            },
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_create_workspace_organisation_not_found(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        make_uuid,
    ):
        """
        Creation fails when organisation doesn't exist.

        Given: Authenticated as SuperAdmin
        When: POST to non-existent organisation
        Then: Returns 404 Not Found
        """
        response = await client.post(
            f"/api/v1/organisations/{make_uuid()}/mcp-server-workspaces",
            json={
                "name": "Orphan Workspace",
                "slug": "orphan",
                "mcp_endpoint_url": "https://example.com",
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 404


# =============================================================================
# LIST WORKSPACES TESTS
# =============================================================================


class TestListWorkspaces:
    """
    Tests for GET /api/v1/organisations/{org_id}/mcp-server-workspaces endpoint.

    This endpoint lists all workspaces in an organisation with pagination.

    Query Parameters:
        - page (int, optional): Page number (default: 1)
        - per_page (int, optional): Items per page (default: 20, max: 100)

    Response: Paginated list of McpServerWorkspaceResponse objects
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_list_workspaces_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        test_workspace,
    ):
        """
        OrgAdmin can list workspaces in their organisation.

        Given: Authenticated as OrgAdmin, workspace exists
        When: GET /organisations/{org_id}/mcp-server-workspaces
        Then: Returns 200 with paginated list
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) >= 1

        # Verify test workspace is in list
        workspace_ids = [ws["id"] for ws in data["data"]]
        assert str(test_workspace.id) in workspace_ids

    async def test_list_workspaces_pagination(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Pagination works correctly for workspace listing.

        Given: Multiple workspaces exist
        When: GET with pagination params
        Then: Returns correct subset and pagination metadata
        """
        # Create multiple workspaces
        for i in range(5):
            await client.post(
                f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
                json={
                    "name": f"Pagination Workspace {i}",
                    "slug": f"pagination-ws-{i}",
                    "mcp_endpoint_url": f"https://example.com/ws{i}",
                },
                headers=org_admin_headers,
            )

        # Request with pagination
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            params={"page": 1, "per_page": 2},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 2
        assert data["pagination"]["total"] >= 5

    async def test_list_workspaces_empty(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Returns empty list when no workspaces exist.

        Given: Organisation with no workspaces
        When: GET /organisations/{org_id}/mcp-server-workspaces
        Then: Returns 200 with empty data array
        """
        # Create a new org without workspaces
        org_response = await client.post(
            "/api/v1/organisations",
            json={"name": "Empty Org"},
            headers=super_admin_headers,
        )
        org_id = org_response.json()["id"]

        response = await client.get(
            f"/api/v1/organisations/{org_id}/mcp-server-workspaces",
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["pagination"]["total"] == 0

    async def test_list_workspaces_org_viewer_can_read(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_organisation,
        test_workspace,
    ):
        """
        OrgViewer can list workspaces (read-only).

        Given: Authenticated as OrgViewer
        When: GET /organisations/{org_id}/mcp-server-workspaces
        Then: Returns 200 with workspace list
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_list_workspaces_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_organisation,
    ):
        """
        Cannot list workspaces of other organisations.

        Given: Authenticated as admin of different org
        When: GET workspaces of another org
        Then: Returns 403 Forbidden
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403


# =============================================================================
# GET WORKSPACE TESTS
# =============================================================================


class TestGetWorkspace:
    """
    Tests for GET /api/v1/mcp-server-workspaces/{workspace_id} endpoint.

    This endpoint retrieves a single workspace by ID.

    Path Parameters:
        - mcp_server_workspace_id (UUID): Workspace identifier

    Response: McpServerWorkspaceResponse with full details
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_get_workspace_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        OrgAdmin can get workspace details.

        Given: Authenticated as OrgAdmin
        When: GET /mcp-server-workspaces/{id}
        Then: Returns 200 with workspace details
        """
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(test_workspace.id)
        assert data["name"] == test_workspace.name
        assert data["slug"] == test_workspace.slug
        assert "mcp_endpoint_url" in data
        assert "settings" in data
        assert "created_at" in data

    async def test_get_workspace_org_viewer_can_read(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_workspace,
    ):
        """
        OrgViewer can get workspace details.

        Given: Authenticated as OrgViewer
        When: GET /mcp-server-workspaces/{id}
        Then: Returns 200 with workspace details
        """
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_get_workspace_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot get workspace from other organisation.

        Given: Authenticated as admin of different org
        When: GET workspace from another org
        Then: Returns 403 Forbidden
        """
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_get_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent workspace.

        Given: Authenticated as OrgAdmin
        When: GET /mcp-server-workspaces/{non_existent_id}
        Then: Returns 404 Not Found
        """
        response = await client.get(
            f"/api/v1/mcp-server-workspaces/{make_uuid()}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    async def test_get_workspace_invalid_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Given: Authenticated as OrgAdmin
        When: GET /mcp-server-workspaces/{invalid_uuid}
        Then: Returns 400 Bad Request
        """
        response = await client.get(
            "/api/v1/mcp-server-workspaces/not-a-valid-uuid",
            headers=org_admin_headers,
        )

        assert response.status_code == 400


# =============================================================================
# UPDATE WORKSPACE TESTS
# =============================================================================


class TestUpdateWorkspace:
    """
    Tests for PUT /api/v1/mcp-server-workspaces/{workspace_id} endpoint.

    This endpoint updates an existing workspace.

    Path Parameters:
        - mcp_server_workspace_id (UUID): Workspace identifier

    Request Body (all optional):
        - name (str): New workspace name
        - description (str): Updated description
        - mcp_endpoint_url (str): New MCP endpoint URL
        - settings (dict): Updated settings

    Response: Updated McpServerWorkspaceResponse
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_update_workspace_name_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        OrgAdmin can update workspace name.

        Given: Authenticated as OrgAdmin
        When: PUT /mcp-server-workspaces/{id} with new name
        Then: Returns 200 with updated name
        """
        response = await client.put(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            json={"name": "Updated Workspace Name"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Workspace Name"

    async def test_update_workspace_endpoint_url_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        OrgAdmin can update MCP endpoint URL.

        Given: Authenticated as OrgAdmin
        When: PUT with new mcp_endpoint_url
        Then: Returns 200 with updated URL
        """
        response = await client.put(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            json={"mcp_endpoint_url": "https://new-mcp.example.com/endpoint"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mcp_endpoint_url"] == "https://new-mcp.example.com/endpoint"

    async def test_update_workspace_settings_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        OrgAdmin can update workspace settings.

        Given: Authenticated as OrgAdmin
        When: PUT with new settings
        Then: Returns 200 with updated settings
        """
        response = await client.put(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            json={
                "settings": {
                    "log_level": "verbose",
                    "fail_mode": "closed",
                }
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["log_level"] == "verbose"
        assert data["settings"]["fail_mode"] == "closed"

    async def test_update_workspace_multiple_fields(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Can update multiple fields in single request.

        Given: Authenticated as OrgAdmin
        When: PUT with multiple fields
        Then: Returns 200 with all fields updated
        """
        response = await client.put(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            json={
                "name": "Multi-update Workspace",
                "description": "Updated description",
                "mcp_endpoint_url": "https://multi.example.com",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Multi-update Workspace"
        assert data["description"] == "Updated description"
        assert data["mcp_endpoint_url"] == "https://multi.example.com"

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    async def test_update_workspace_empty_name(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_workspace,
    ):
        """
        Update fails with empty name.

        Given: Authenticated as OrgAdmin
        When: PUT with empty name
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.put(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            json={"name": ""},
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_update_workspace_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_workspace,
    ):
        """
        OrgViewer cannot update workspaces.

        Given: Authenticated as OrgViewer
        When: PUT /mcp-server-workspaces/{id}
        Then: Returns 403 Forbidden
        """
        response = await client.put(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            json={"name": "Viewer Update Attempt"},
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    async def test_update_workspace_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot update workspace of other organisation.

        Given: Authenticated as admin of different org
        When: PUT workspace of another org
        Then: Returns 403 Forbidden
        """
        response = await client.put(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            json={"name": "Cross-org Update"},
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_update_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Update returns 404 for non-existent workspace.

        Given: Authenticated as OrgAdmin
        When: PUT /mcp-server-workspaces/{non_existent_id}
        Then: Returns 404 Not Found
        """
        response = await client.put(
            f"/api/v1/mcp-server-workspaces/{make_uuid()}",
            json={"name": "Update Non-existent"},
            headers=org_admin_headers,
        )

        assert response.status_code == 404


# =============================================================================
# DELETE WORKSPACE TESTS
# =============================================================================


class TestDeleteWorkspace:
    """
    Tests for DELETE /api/v1/mcp-server-workspaces/{workspace_id} endpoint.

    This endpoint soft-deletes a workspace.
    OrgAdmin or higher can delete workspaces.

    Path Parameters:
        - mcp_server_workspace_id (UUID): Workspace identifier

    Response: 204 No Content on success
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_delete_workspace_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can delete a workspace.

        Given: Authenticated as OrgAdmin, workspace exists
        When: DELETE /mcp-server-workspaces/{id}
        Then: Returns 204 and workspace is no longer accessible
        """
        # Create workspace to delete
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Workspace to Delete",
                "slug": "delete-me",
                "mcp_endpoint_url": "https://example.com/delete",
            },
            headers=org_admin_headers,
        )
        workspace_id = create_response.json()["id"]

        # Delete it
        response = await client.delete(
            f"/api/v1/mcp-server-workspaces/{workspace_id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 204

        # Verify it's no longer accessible
        get_response = await client.get(
            f"/api/v1/mcp-server-workspaces/{workspace_id}",
            headers=org_admin_headers,
        )
        assert get_response.status_code == 404

    async def test_delete_workspace_super_admin(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        SuperAdmin can delete any workspace.

        Given: Authenticated as SuperAdmin
        When: DELETE workspace in any org
        Then: Returns 204
        """
        # Create workspace as org admin
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "SuperAdmin Delete Target",
                "slug": "super-delete",
                "mcp_endpoint_url": "https://example.com/super",
            },
            headers=org_admin_headers,
        )
        workspace_id = create_response.json()["id"]

        # Delete as super admin
        response = await client.delete(
            f"/api/v1/mcp-server-workspaces/{workspace_id}",
            headers=super_admin_headers,
        )

        assert response.status_code == 204

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_delete_workspace_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_workspace,
    ):
        """
        OrgViewer cannot delete workspaces.

        Given: Authenticated as OrgViewer
        When: DELETE /mcp-server-workspaces/{id}
        Then: Returns 403 Forbidden
        """
        response = await client.delete(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    async def test_delete_workspace_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot delete workspace of other organisation.

        Given: Authenticated as admin of different org
        When: DELETE workspace of another org
        Then: Returns 403 Forbidden
        """
        response = await client.delete(
            f"/api/v1/mcp-server-workspaces/{test_workspace.id}",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_delete_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Delete returns 404 for non-existent workspace.

        Given: Authenticated as OrgAdmin
        When: DELETE /mcp-server-workspaces/{non_existent_id}
        Then: Returns 404 Not Found
        """
        response = await client.delete(
            f"/api/v1/mcp-server-workspaces/{make_uuid()}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    async def test_delete_workspace_idempotent(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Deleting already-deleted workspace returns 404.

        Given: Workspace was already deleted
        When: DELETE again
        Then: Returns 404 Not Found
        """
        # Create and delete
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/mcp-server-workspaces",
            json={
                "name": "Double Delete WS",
                "slug": "double-delete",
                "mcp_endpoint_url": "https://example.com/double",
            },
            headers=org_admin_headers,
        )
        workspace_id = create_response.json()["id"]

        # First delete
        await client.delete(
            f"/api/v1/mcp-server-workspaces/{workspace_id}",
            headers=org_admin_headers,
        )

        # Second delete should return 404
        response = await client.delete(
            f"/api/v1/mcp-server-workspaces/{workspace_id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404
