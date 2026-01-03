"""
Organisation API Integration Tests

Comprehensive tests for the organisation management endpoints.
Organisations are the top-level tenant entities in the system.

Endpoints Tested:
    - POST   /api/v1/organisations                  - Create organisation
    - GET    /api/v1/organisations                  - List organisations
    - GET    /api/v1/organisations/{id}             - Get organisation
    - PUT    /api/v1/organisations/{id}             - Update organisation
    - DELETE /api/v1/organisations/{id}             - Delete organisation

Authorization Rules:
    - SuperAdmin: Full access to all operations
    - OrgAdmin: Can read/update their own organisation only
    - OrgViewer: Can read their own organisation only

Test Categories:
    1. Success Cases - Happy path scenarios
    2. Validation Errors - Invalid input handling
    3. Authorization - Role-based access control
    4. Not Found - Non-existent resource handling
    5. Edge Cases - Boundary conditions and special scenarios
"""

from httpx import AsyncClient


# =============================================================================
# CREATE ORGANISATION TESTS
# =============================================================================


class TestCreateOrganisation:
    """
    Tests for POST /api/v1/organisations endpoint.

    This endpoint creates a new organisation (tenant) in the system.
    Only SuperAdmin users can create organisations.

    Request Body:
        - name (str, required): Organisation display name
        - subscription_tier (str, optional): Subscription tier (default: "default")
        - settings (dict, optional): Custom settings (auto-derived from tier if not provided)

    Response: OrganisationResponse with id, name, tier, settings, timestamps
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_create_organisation_success_minimal(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        SuperAdmin can create organisation with only required fields.

        Given: Authenticated as SuperAdmin
        When: POST /organisations with only name
        Then: Returns 201 with organisation details
              Settings are auto-derived from default tier
        """
        response = await client.post(
            "/api/v1/organisations",
            json={"name": "Acme Corporation"},
            headers=super_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()

        # Verify required fields
        assert data["name"] == "Acme Corporation"
        assert "id" in data
        assert data["subscription_tier"] == "default"

        # Verify auto-derived settings from tier
        assert "settings" in data
        assert data["settings"]["max_mcp_server_workspaces"] == 10
        assert data["settings"]["max_users"] == 50

        # Verify timestamps
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_organisation_success_with_custom_settings(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        SuperAdmin can create organisation with custom settings override.

        Given: Authenticated as SuperAdmin
        When: POST /organisations with custom settings
        Then: Returns 201 with custom settings applied
        """
        custom_settings = {
            "max_mcp_server_workspaces": 25,
            "max_users": 100,
            "data_retention_days": 180,
        }

        response = await client.post(
            "/api/v1/organisations",
            json={
                "name": "Enterprise Corp",
                "settings": custom_settings,
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["settings"]["max_mcp_server_workspaces"] == 25
        assert data["settings"]["max_users"] == 100
        assert data["settings"]["data_retention_days"] == 180

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    async def test_create_organisation_missing_name(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Creation fails when name is missing.

        Given: Authenticated as SuperAdmin
        When: POST /organisations without name field
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            "/api/v1/organisations",
            json={},
            headers=super_admin_headers,
        )

        assert response.status_code == 422

    async def test_create_organisation_empty_name(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Creation fails when name is empty string.

        Given: Authenticated as SuperAdmin
        When: POST /organisations with empty name
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            "/api/v1/organisations",
            json={"name": ""},
            headers=super_admin_headers,
        )

        assert response.status_code == 422

    async def test_create_organisation_name_too_long(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Creation fails when name exceeds maximum length.

        Given: Authenticated as SuperAdmin
        When: POST /organisations with name > 255 characters
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            "/api/v1/organisations",
            json={"name": "A" * 300},
            headers=super_admin_headers,
        )

        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_create_organisation_requires_authentication(
        self,
        client: AsyncClient,
    ):
        """
        Creation requires authentication.

        Given: No authentication headers
        When: POST /organisations
        Then: Returns 401 Unauthorized
        """
        response = await client.post(
            "/api/v1/organisations",
            json={"name": "Unauthenticated Org"},
        )

        assert response.status_code == 401

    async def test_create_organisation_org_admin_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        OrgAdmin cannot create organisations.

        Given: Authenticated as OrgAdmin
        When: POST /organisations
        Then: Returns 403 Forbidden
        """
        response = await client.post(
            "/api/v1/organisations",
            json={"name": "Admin Created Org"},
            headers=org_admin_headers,
        )

        assert response.status_code == 403

    async def test_create_organisation_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
    ):
        """
        OrgViewer cannot create organisations.

        Given: Authenticated as OrgViewer
        When: POST /organisations
        Then: Returns 403 Forbidden
        """
        response = await client.post(
            "/api/v1/organisations",
            json={"name": "Viewer Created Org"},
            headers=org_viewer_headers,
        )

        assert response.status_code == 403


# =============================================================================
# LIST ORGANISATIONS TESTS
# =============================================================================


class TestListOrganisations:
    """
    Tests for GET /api/v1/organisations endpoint.

    This endpoint lists all organisations with pagination.
    Only SuperAdmin users can list all organisations.

    Query Parameters:
        - page (int, optional): Page number (default: 1)
        - per_page (int, optional): Items per page (default: 20, max: 100)

    Response: Paginated list of OrganisationResponse objects
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_list_organisations_success(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_organisation,
    ):
        """
        SuperAdmin can list all organisations.

        Given: Authenticated as SuperAdmin, one organisation exists
        When: GET /organisations
        Then: Returns 200 with paginated list containing the organisation
        """
        response = await client.get(
            "/api/v1/organisations",
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify pagination structure
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

        # Verify at least test organisation is present
        assert len(data["data"]) >= 1
        org_ids = [org["id"] for org in data["data"]]
        assert str(test_organisation.id) in org_ids

    async def test_list_organisations_pagination(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Pagination works correctly with page and per_page params.

        Given: Multiple organisations exist
        When: GET /organisations with page=1, per_page=2
        Then: Returns correct number of items and pagination metadata
        """
        # Create multiple organisations
        for i in range(5):
            await client.post(
                "/api/v1/organisations",
                json={"name": f"Pagination Test Org {i}"},
                headers=super_admin_headers,
            )

        # Request first page with 2 items
        response = await client.get(
            "/api/v1/organisations",
            params={"page": 1, "per_page": 2},
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 2
        assert data["pagination"]["total"] >= 5

    async def test_list_organisations_empty(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Returns empty list when no organisations exist.

        Given: No organisations in database (fresh test)
        When: GET /organisations
        Then: Returns 200 with empty data array
        """
        response = await client.get(
            "/api/v1/organisations",
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # May have 0 orgs in fresh DB (super_admin has no org)
        assert isinstance(data["data"], list)

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_list_organisations_requires_authentication(
        self,
        client: AsyncClient,
    ):
        """
        Listing requires authentication.

        Given: No authentication headers
        When: GET /organisations
        Then: Returns 401 Unauthorized
        """
        response = await client.get("/api/v1/organisations")

        assert response.status_code == 401

    async def test_list_organisations_org_admin_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        OrgAdmin cannot list all organisations.

        Given: Authenticated as OrgAdmin
        When: GET /organisations
        Then: Returns 403 Forbidden
        """
        response = await client.get(
            "/api/v1/organisations",
            headers=org_admin_headers,
        )

        assert response.status_code == 403

    async def test_list_organisations_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
    ):
        """
        OrgViewer cannot list all organisations.

        Given: Authenticated as OrgViewer
        When: GET /organisations
        Then: Returns 403 Forbidden
        """
        response = await client.get(
            "/api/v1/organisations",
            headers=org_viewer_headers,
        )

        assert response.status_code == 403


# =============================================================================
# GET ORGANISATION TESTS
# =============================================================================


class TestGetOrganisation:
    """
    Tests for GET /api/v1/organisations/{organisation_id} endpoint.

    This endpoint retrieves a single organisation by ID.
    Access depends on user role and organisation membership.

    Path Parameters:
        - organisation_id (UUID): Organisation identifier

    Response: OrganisationResponse with full details
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_get_organisation_success_super_admin(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_organisation,
    ):
        """
        SuperAdmin can get any organisation.

        Given: Authenticated as SuperAdmin
        When: GET /organisations/{id}
        Then: Returns 200 with organisation details
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}",
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(test_organisation.id)
        assert data["name"] == test_organisation.name
        assert "settings" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_get_organisation_success_org_admin_own_org(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can get their own organisation.

        Given: Authenticated as OrgAdmin of the organisation
        When: GET /organisations/{own_org_id}
        Then: Returns 200 with organisation details
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_organisation.id)

    async def test_get_organisation_success_org_viewer_own_org(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_organisation,
    ):
        """
        OrgViewer can get their own organisation.

        Given: Authenticated as OrgViewer of the organisation
        When: GET /organisations/{own_org_id}
        Then: Returns 200 with organisation details
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_get_organisation_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin cannot access other organisations.

        Given: Authenticated as OrgAdmin of a different organisation
        When: GET /organisations/{other_org_id}
        Then: Returns 403 Forbidden
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    async def test_get_organisation_requires_authentication(
        self,
        client: AsyncClient,
        test_organisation,
    ):
        """
        Get organisation requires authentication.

        Given: No authentication headers
        When: GET /organisations/{id}
        Then: Returns 401 Unauthorized
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}",
        )

        assert response.status_code == 401

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_get_organisation_not_found(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent organisation.

        Given: Authenticated as SuperAdmin
        When: GET /organisations/{non_existent_id}
        Then: Returns 404 Not Found
        """
        response = await client.get(
            f"/api/v1/organisations/{make_uuid()}",
            headers=super_admin_headers,
        )

        assert response.status_code == 404

    async def test_get_organisation_invalid_uuid(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Given: Authenticated as SuperAdmin
        When: GET /organisations/{invalid_uuid}
        Then: Returns 400 Bad Request
        """
        response = await client.get(
            "/api/v1/organisations/not-a-valid-uuid",
            headers=super_admin_headers,
        )

        assert response.status_code == 400


# =============================================================================
# UPDATE ORGANISATION TESTS
# =============================================================================


class TestUpdateOrganisation:
    """
    Tests for PUT /api/v1/organisations/{organisation_id} endpoint.

    This endpoint updates an existing organisation.
    Access depends on user role and organisation membership.

    Path Parameters:
        - organisation_id (UUID): Organisation identifier

    Request Body (all optional):
        - name (str): New organisation name
        - settings (dict): Updated settings

    Response: Updated OrganisationResponse
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_update_organisation_name_success(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_organisation,
    ):
        """
        SuperAdmin can update organisation name.

        Given: Authenticated as SuperAdmin
        When: PUT /organisations/{id} with new name
        Then: Returns 200 with updated name
        """
        response = await client.put(
            f"/api/v1/organisations/{test_organisation.id}",
            json={"name": "Updated Organisation Name"},
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Organisation Name"

    async def test_update_organisation_settings_success(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_organisation,
    ):
        """
        SuperAdmin can update organisation settings.

        Given: Authenticated as SuperAdmin
        When: PUT /organisations/{id} with new settings
        Then: Returns 200 with updated settings
        """
        response = await client.put(
            f"/api/v1/organisations/{test_organisation.id}",
            json={
                "settings": {
                    "max_mcp_server_workspaces": 50,
                    "data_retention_days": 365,
                }
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["max_mcp_server_workspaces"] == 50
        assert data["settings"]["data_retention_days"] == 365

    async def test_update_organisation_org_admin_own_org(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can update their own organisation.

        Given: Authenticated as OrgAdmin
        When: PUT /organisations/{own_org_id}
        Then: Returns 200 with updated data
        """
        response = await client.put(
            f"/api/v1/organisations/{test_organisation.id}",
            json={"name": "Admin Updated Org"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Admin Updated Org"

    async def test_update_organisation_partial_update(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_organisation,
    ):
        """
        Partial update only changes specified fields.

        Given: Organisation with existing name and settings
        When: PUT with only name field
        Then: Name changes but settings remain unchanged
        """
        # Get current settings
        get_response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}",
            headers=super_admin_headers,
        )
        original_settings = get_response.json()["settings"]

        # Update only name
        response = await client.put(
            f"/api/v1/organisations/{test_organisation.id}",
            json={"name": "Partial Update Test"},
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Partial Update Test"
        # Settings should remain unchanged
        assert data["settings"] == original_settings

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    async def test_update_organisation_empty_name(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_organisation,
    ):
        """
        Update fails with empty name.

        Given: Authenticated as SuperAdmin
        When: PUT /organisations/{id} with empty name
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.put(
            f"/api/v1/organisations/{test_organisation.id}",
            json={"name": ""},
            headers=super_admin_headers,
        )

        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_update_organisation_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_organisation,
    ):
        """
        OrgViewer cannot update organisations.

        Given: Authenticated as OrgViewer
        When: PUT /organisations/{id}
        Then: Returns 403 Forbidden
        """
        response = await client.put(
            f"/api/v1/organisations/{test_organisation.id}",
            json={"name": "Viewer Update Attempt"},
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    async def test_update_organisation_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin cannot update other organisations.

        Given: Authenticated as OrgAdmin of different organisation
        When: PUT /organisations/{other_org_id}
        Then: Returns 403 Forbidden
        """
        response = await client.put(
            f"/api/v1/organisations/{test_organisation.id}",
            json={"name": "Cross-org Update Attempt"},
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_update_organisation_not_found(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        make_uuid,
    ):
        """
        Update returns 404 for non-existent organisation.

        Given: Authenticated as SuperAdmin
        When: PUT /organisations/{non_existent_id}
        Then: Returns 404 Not Found
        """
        response = await client.put(
            f"/api/v1/organisations/{make_uuid()}",
            json={"name": "Update Non-existent"},
            headers=super_admin_headers,
        )

        assert response.status_code == 404


# =============================================================================
# DELETE ORGANISATION TESTS
# =============================================================================


class TestDeleteOrganisation:
    """
    Tests for DELETE /api/v1/organisations/{organisation_id} endpoint.

    This endpoint soft-deletes an organisation.
    Only SuperAdmin can delete organisations.

    Path Parameters:
        - organisation_id (UUID): Organisation identifier

    Response: 204 No Content on success
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_delete_organisation_success(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        SuperAdmin can delete an organisation.

        Given: Authenticated as SuperAdmin, organisation exists
        When: DELETE /organisations/{id}
        Then: Returns 204 and organisation is no longer accessible
        """
        # Create an organisation to delete
        create_response = await client.post(
            "/api/v1/organisations",
            json={"name": "Organisation to Delete"},
            headers=super_admin_headers,
        )
        org_id = create_response.json()["id"]

        # Delete it
        response = await client.delete(
            f"/api/v1/organisations/{org_id}",
            headers=super_admin_headers,
        )

        assert response.status_code == 204

        # Verify it's no longer accessible
        get_response = await client.get(
            f"/api/v1/organisations/{org_id}",
            headers=super_admin_headers,
        )
        assert get_response.status_code == 404

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_delete_organisation_org_admin_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin cannot delete organisations.

        Given: Authenticated as OrgAdmin
        When: DELETE /organisations/{id}
        Then: Returns 403 Forbidden
        """
        response = await client.delete(
            f"/api/v1/organisations/{test_organisation.id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 403

    async def test_delete_organisation_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_organisation,
    ):
        """
        OrgViewer cannot delete organisations.

        Given: Authenticated as OrgViewer
        When: DELETE /organisations/{id}
        Then: Returns 403 Forbidden
        """
        response = await client.delete(
            f"/api/v1/organisations/{test_organisation.id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    async def test_delete_organisation_requires_authentication(
        self,
        client: AsyncClient,
        test_organisation,
    ):
        """
        Delete requires authentication.

        Given: No authentication headers
        When: DELETE /organisations/{id}
        Then: Returns 401 Unauthorized
        """
        response = await client.delete(
            f"/api/v1/organisations/{test_organisation.id}",
        )

        assert response.status_code == 401

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_delete_organisation_not_found(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        make_uuid,
    ):
        """
        Delete returns 404 for non-existent organisation.

        Given: Authenticated as SuperAdmin
        When: DELETE /organisations/{non_existent_id}
        Then: Returns 404 Not Found
        """
        response = await client.delete(
            f"/api/v1/organisations/{make_uuid()}",
            headers=super_admin_headers,
        )

        assert response.status_code == 404

    async def test_delete_organisation_idempotent(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Deleting already-deleted organisation returns 404.

        Given: Organisation was already deleted
        When: DELETE /organisations/{id} again
        Then: Returns 404 Not Found
        """
        # Create and delete
        create_response = await client.post(
            "/api/v1/organisations",
            json={"name": "Double Delete Org"},
            headers=super_admin_headers,
        )
        org_id = create_response.json()["id"]

        # First delete
        await client.delete(
            f"/api/v1/organisations/{org_id}",
            headers=super_admin_headers,
        )

        # Second delete should return 404
        response = await client.delete(
            f"/api/v1/organisations/{org_id}",
            headers=super_admin_headers,
        )

        assert response.status_code == 404
