"""
Guardrail Definition API Integration Tests

Tests for the guardrail definition management endpoints.

Guardrails are atomic security checks that can be attached to entities via policies.
These endpoints manage the guardrail DEFINITIONS themselves (admin only).

Endpoint Summary:
=================
- GET    /api/v1/guardrails              - List guardrail definitions
- GET    /api/v1/guardrails/{id}         - Get guardrail definition by ID
- POST   /api/v1/guardrails              - Create guardrail definition (SuperAdmin only)
- PUT    /api/v1/guardrails/{id}         - Update guardrail definition (SuperAdmin only)
- DELETE /api/v1/guardrails/{id}         - Delete guardrail definition (SuperAdmin only)

Authorization:
==============
- List/Get: Any authenticated user
- Create/Update/Delete: SuperAdmin only (platform-level, not org-level)
"""

import pytest
from httpx import AsyncClient

from app.config.constants import GuardrailCategory, GuardrailType

# pylint: disable=unused-argument


# =============================================================================
# CREATE GUARDRAIL TESTS
# =============================================================================


class TestCreateGuardrail:
    """
    Tests for POST /api/v1/guardrails endpoint.

    This endpoint creates new guardrail definitions. Only SuperAdmin users
    can create guardrails since they are platform-wide resources.
    """

    @pytest.mark.asyncio
    async def test_create_guardrail_success_super_admin(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        SuperAdmin can create a new guardrail definition.

        Scenario: SuperAdmin creates a custom guardrail for specific use case.
        Expected: 201 Created with guardrail details.
        """
        response = await client.post(
            "/api/v1/guardrails",
            json={
                "guardrail_type": "custom_content_filter",
                "display_name": "Custom Content Filter",
                "description": "Filters custom content patterns",
                "category": GuardrailCategory.CONTENT.value,
                "default_config": {"patterns": []},
                "is_active": True,
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["guardrail_type"] == "custom_content_filter"
        assert data["display_name"] == "Custom Content Filter"
        assert data["category"] == GuardrailCategory.CONTENT.value
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_guardrail_with_all_fields(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Can create guardrail with all optional fields specified.

        Scenario: SuperAdmin creates a fully configured guardrail.
        Expected: 201 Created with all fields properly saved.
        """
        response = await client.post(
            "/api/v1/guardrails",
            json={
                "guardrail_type": "full_config_guardrail",
                "display_name": "Full Config Guardrail",
                "description": "A guardrail with all configuration options",
                "category": GuardrailCategory.RBAC.value,
                "default_config": {
                    "allowed_tools": ["*"],
                    "default_action": "allow",
                },
                "is_active": True,
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "A guardrail with all configuration options"
        assert data["default_config"]["allowed_tools"] == ["*"]
        assert data["default_config"]["default_action"] == "allow"

    @pytest.mark.asyncio
    async def test_create_guardrail_duplicate_type_conflict(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Creating guardrail with duplicate type fails.

        Scenario: Try to create a guardrail with a type that already exists.
        Expected: 409 Conflict with error message.
        """
        guardrail_data = {
            "guardrail_type": "unique_guardrail_type",
            "display_name": "Unique Guardrail",
            "category": GuardrailCategory.PII.value,
            "default_config": {},
            "is_active": True,
        }

        # Create first guardrail
        response1 = await client.post(
            "/api/v1/guardrails",
            json=guardrail_data,
            headers=super_admin_headers,
        )
        assert response1.status_code == 201

        # Try to create duplicate
        guardrail_data["display_name"] = "Different Name"
        response2 = await client.post(
            "/api/v1/guardrails",
            json=guardrail_data,
            headers=super_admin_headers,
        )

        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_guardrail_missing_required_fields(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Creating guardrail without required fields fails.

        Scenario: Try to create a guardrail missing guardrail_type.
        Expected: 422 Unprocessable Entity with validation error.
        """
        response = await client.post(
            "/api/v1/guardrails",
            json={
                "display_name": "Missing Type Guardrail",
                "category": GuardrailCategory.CONTENT.value,
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_create_guardrail_invalid_category(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Creating guardrail with invalid category fails.

        Scenario: Try to create a guardrail with non-existent category.
        Expected: 422 Unprocessable Entity with validation error.
        """
        response = await client.post(
            "/api/v1/guardrails",
            json={
                "guardrail_type": "invalid_category_guardrail",
                "display_name": "Invalid Category",
                "category": "invalid_category",
                "default_config": {},
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_guardrail_org_admin_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Org admins cannot create guardrail definitions.

        Scenario: OrgAdmin tries to create a guardrail.
        Expected: 403 Forbidden - only SuperAdmin can create guardrails.
        """
        response = await client.post(
            "/api/v1/guardrails",
            json={
                "guardrail_type": "org_admin_guardrail",
                "display_name": "Org Admin Guardrail",
                "category": GuardrailCategory.CONTENT.value,
                "default_config": {},
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_guardrail_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
    ):
        """
        Org viewers cannot create guardrail definitions.

        Scenario: OrgViewer tries to create a guardrail.
        Expected: 403 Forbidden.
        """
        response = await client.post(
            "/api/v1/guardrails",
            json={
                "guardrail_type": "viewer_guardrail",
                "display_name": "Viewer Guardrail",
                "category": GuardrailCategory.CONTENT.value,
                "default_config": {},
            },
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_guardrail_unauthenticated(
        self,
        client: AsyncClient,
    ):
        """
        Unauthenticated requests cannot create guardrails.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.post(
            "/api/v1/guardrails",
            json={
                "guardrail_type": "unauth_guardrail",
                "display_name": "Unauth Guardrail",
                "category": GuardrailCategory.CONTENT.value,
                "default_config": {},
            },
        )

        assert response.status_code == 401


# =============================================================================
# LIST GUARDRAILS TESTS
# =============================================================================


class TestListGuardrails:
    """
    Tests for GET /api/v1/guardrails endpoint.

    Lists all available guardrail definitions with optional filtering.
    Any authenticated user can list guardrails.
    """

    @pytest.mark.asyncio
    async def test_list_guardrails_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Can list all guardrail definitions.

        Scenario: User requests list of all guardrails.
        Expected: 200 OK with paginated list of guardrails.
        """
        response = await client.get(
            "/api/v1/guardrails",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) > 0
        assert data["pagination"]["total"] >= len(seeded_guardrails)

    @pytest.mark.asyncio
    async def test_list_guardrails_with_pagination(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Can paginate guardrail list.

        Scenario: Request guardrails with page and per_page params.
        Expected: Returns correct subset of guardrails.
        """
        response = await client.get(
            "/api/v1/guardrails",
            params={"page": 1, "per_page": 2},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) <= 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 2

    @pytest.mark.asyncio
    async def test_list_guardrails_filter_by_category(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Can filter guardrails by category.

        Scenario: Request only PII category guardrails.
        Expected: Returns only guardrails in the PII category.
        """
        response = await client.get(
            "/api/v1/guardrails",
            params={"category": GuardrailCategory.PII.value},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for guardrail in data["data"]:
            assert guardrail["category"] == GuardrailCategory.PII.value

    @pytest.mark.asyncio
    async def test_list_guardrails_filter_active_only(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Can filter to show only active guardrails.

        Scenario: Request only active guardrails (default behavior).
        Expected: Returns only guardrails where is_active=True.
        """
        response = await client.get(
            "/api/v1/guardrails",
            params={"active_only": True},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for guardrail in data["data"]:
            assert guardrail["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_guardrails_org_viewer_allowed(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        seeded_guardrails,
    ):
        """
        Org viewers can list guardrails.

        Scenario: OrgViewer requests guardrail list.
        Expected: 200 OK - list is accessible to all authenticated users.
        """
        response = await client.get(
            "/api/v1/guardrails",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) > 0

    @pytest.mark.asyncio
    async def test_list_guardrails_unauthenticated(
        self,
        client: AsyncClient,
        seeded_guardrails,
    ):
        """
        Unauthenticated requests cannot list guardrails.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        response = await client.get("/api/v1/guardrails")

        assert response.status_code == 401


# =============================================================================
# GET GUARDRAIL TESTS
# =============================================================================


class TestGetGuardrail:
    """
    Tests for GET /api/v1/guardrails/{guardrail_id} endpoint.

    Retrieves a specific guardrail definition by ID.
    Any authenticated user can view guardrail details.
    """

    @pytest.mark.asyncio
    async def test_get_guardrail_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Can retrieve a guardrail by ID.

        Scenario: Request a specific guardrail by its UUID.
        Expected: 200 OK with guardrail details.
        """
        guardrail = seeded_guardrails[0]

        response = await client.get(
            f"/api/v1/guardrails/{guardrail.id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(guardrail.id)
        assert data["guardrail_type"] == guardrail.guardrail_type
        assert "display_name" in data
        assert "category" in data
        assert "default_config" in data

    @pytest.mark.asyncio
    async def test_get_guardrail_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent guardrail.

        Scenario: Request a guardrail with random UUID.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/guardrails/{make_uuid()}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_guardrail_invalid_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Scenario: Request with malformed UUID.
        Expected: 400 Bad Request.
        """
        response = await client.get(
            "/api/v1/guardrails/not-a-valid-uuid",
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_guardrail_org_viewer_allowed(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        seeded_guardrails,
    ):
        """
        Org viewers can view guardrail details.

        Scenario: OrgViewer requests guardrail details.
        Expected: 200 OK.
        """
        guardrail = seeded_guardrails[0]

        response = await client.get(
            f"/api/v1/guardrails/{guardrail.id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_guardrail_unauthenticated(
        self,
        client: AsyncClient,
        seeded_guardrails,
    ):
        """
        Unauthenticated requests cannot get guardrail details.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        guardrail = seeded_guardrails[0]

        response = await client.get(f"/api/v1/guardrails/{guardrail.id}")

        assert response.status_code == 401


# =============================================================================
# UPDATE GUARDRAIL TESTS
# =============================================================================


class TestUpdateGuardrail:
    """
    Tests for PUT /api/v1/guardrails/{guardrail_id} endpoint.

    Updates guardrail definition details. Only SuperAdmin can update.
    """

    @pytest.mark.asyncio
    async def test_update_guardrail_success(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        SuperAdmin can update guardrail details.

        Scenario: Update display_name and description of a guardrail.
        Expected: 200 OK with updated guardrail.
        """
        guardrail = seeded_guardrails[0]

        response = await client.put(
            f"/api/v1/guardrails/{guardrail.id}",
            json={
                "display_name": "Updated Display Name",
                "description": "Updated description for the guardrail",
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Display Name"
        assert data["description"] == "Updated description for the guardrail"

    @pytest.mark.asyncio
    async def test_update_guardrail_default_config(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Can update guardrail default_config.

        Scenario: Update the default configuration for a guardrail.
        Expected: 200 OK with new default_config.
        """
        # Find a rate limit guardrail to update
        rate_limit_guardrail = next(
            (g for g in seeded_guardrails
             if g.guardrail_type == GuardrailType.RATE_LIMIT_PER_MINUTE.value),
            seeded_guardrails[0]
        )

        response = await client.put(
            f"/api/v1/guardrails/{rate_limit_guardrail.id}",
            json={
                "default_config": {"limit": 120},
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["default_config"]["limit"] == 120

    @pytest.mark.asyncio
    async def test_update_guardrail_toggle_active_status(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Can toggle guardrail active status.

        Scenario: Deactivate an active guardrail.
        Expected: 200 OK with is_active=False.
        """
        guardrail = seeded_guardrails[0]

        response = await client.put(
            f"/api/v1/guardrails/{guardrail.id}",
            json={"is_active": False},
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_guardrail_partial_update(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Can partially update guardrail (only specified fields change).

        Scenario: Update only description, other fields remain unchanged.
        Expected: 200 OK with only description changed.
        """
        guardrail = seeded_guardrails[0]
        original_display_name = guardrail.display_name

        response = await client.put(
            f"/api/v1/guardrails/{guardrail.id}",
            json={"description": "Only description changed"},
            headers=super_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Only description changed"
        assert data["display_name"] == original_display_name

    @pytest.mark.asyncio
    async def test_update_guardrail_not_found(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent guardrail.

        Scenario: Try to update a guardrail that doesn't exist.
        Expected: 404 Not Found.
        """
        response = await client.put(
            f"/api/v1/guardrails/{make_uuid()}",
            json={"display_name": "Ghost Guardrail"},
            headers=super_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_guardrail_invalid_uuid(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Scenario: Try to update with malformed UUID.
        Expected: 400 Bad Request.
        """
        response = await client.put(
            "/api/v1/guardrails/invalid-uuid-format",
            json={"display_name": "Invalid UUID"},
            headers=super_admin_headers,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_guardrail_org_admin_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Org admins cannot update guardrail definitions.

        Scenario: OrgAdmin tries to update a guardrail.
        Expected: 403 Forbidden - only SuperAdmin can update.
        """
        guardrail = seeded_guardrails[0]

        response = await client.put(
            f"/api/v1/guardrails/{guardrail.id}",
            json={"display_name": "Org Admin Update"},
            headers=org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_guardrail_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        seeded_guardrails,
    ):
        """
        Org viewers cannot update guardrail definitions.

        Scenario: OrgViewer tries to update a guardrail.
        Expected: 403 Forbidden.
        """
        guardrail = seeded_guardrails[0]

        response = await client.put(
            f"/api/v1/guardrails/{guardrail.id}",
            json={"display_name": "Viewer Update"},
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_guardrail_unauthenticated(
        self,
        client: AsyncClient,
        seeded_guardrails,
    ):
        """
        Unauthenticated requests cannot update guardrails.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        guardrail = seeded_guardrails[0]

        response = await client.put(
            f"/api/v1/guardrails/{guardrail.id}",
            json={"display_name": "Unauth Update"},
        )

        assert response.status_code == 401


# =============================================================================
# DELETE GUARDRAIL TESTS
# =============================================================================


class TestDeleteGuardrail:
    """
    Tests for DELETE /api/v1/guardrails/{guardrail_id} endpoint.

    Deletes a guardrail definition. Only SuperAdmin can delete.
    WARNING: Deleting a guardrail also deletes all policies using it.
    """

    @pytest.mark.asyncio
    async def test_delete_guardrail_success(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        SuperAdmin can delete a guardrail.

        Scenario: Create and then delete a guardrail.
        Expected: 204 No Content, guardrail no longer retrievable.
        """
        # First create a guardrail to delete
        create_response = await client.post(
            "/api/v1/guardrails",
            json={
                "guardrail_type": "deletable_guardrail",
                "display_name": "Deletable Guardrail",
                "category": GuardrailCategory.CONTENT.value,
                "default_config": {},
                "is_active": True,
            },
            headers=super_admin_headers,
        )
        guardrail_id = create_response.json()["id"]

        # Delete it
        delete_response = await client.delete(
            f"/api/v1/guardrails/{guardrail_id}",
            headers=super_admin_headers,
        )

        assert delete_response.status_code == 204

        # Verify it's gone
        get_response = await client.get(
            f"/api/v1/guardrails/{guardrail_id}",
            headers=super_admin_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_guardrail_not_found(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent guardrail.

        Scenario: Try to delete a guardrail that doesn't exist.
        Expected: 404 Not Found.
        """
        response = await client.delete(
            f"/api/v1/guardrails/{make_uuid()}",
            headers=super_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_guardrail_invalid_uuid(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Scenario: Try to delete with malformed UUID.
        Expected: 400 Bad Request.
        """
        response = await client.delete(
            "/api/v1/guardrails/not-a-uuid",
            headers=super_admin_headers,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_guardrail_idempotent(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
    ):
        """
        Deleting same guardrail twice returns 404 on second attempt.

        Scenario: Delete a guardrail, then try to delete again.
        Expected: First delete returns 204, second returns 404.
        """
        # Create guardrail
        create_response = await client.post(
            "/api/v1/guardrails",
            json={
                "guardrail_type": "double_delete_guardrail",
                "display_name": "Double Delete Guardrail",
                "category": GuardrailCategory.CONTENT.value,
                "default_config": {},
            },
            headers=super_admin_headers,
        )
        guardrail_id = create_response.json()["id"]

        # First delete - success
        response1 = await client.delete(
            f"/api/v1/guardrails/{guardrail_id}",
            headers=super_admin_headers,
        )
        assert response1.status_code == 204

        # Second delete - not found
        response2 = await client.delete(
            f"/api/v1/guardrails/{guardrail_id}",
            headers=super_admin_headers,
        )
        assert response2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_guardrail_org_admin_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        seeded_guardrails,
    ):
        """
        Org admins cannot delete guardrail definitions.

        Scenario: OrgAdmin tries to delete a guardrail.
        Expected: 403 Forbidden - only SuperAdmin can delete.
        """
        guardrail = seeded_guardrails[0]

        response = await client.delete(
            f"/api/v1/guardrails/{guardrail.id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_guardrail_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        seeded_guardrails,
    ):
        """
        Org viewers cannot delete guardrail definitions.

        Scenario: OrgViewer tries to delete a guardrail.
        Expected: 403 Forbidden.
        """
        guardrail = seeded_guardrails[0]

        response = await client.delete(
            f"/api/v1/guardrails/{guardrail.id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_guardrail_unauthenticated(
        self,
        client: AsyncClient,
        seeded_guardrails,
    ):
        """
        Unauthenticated requests cannot delete guardrails.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        guardrail = seeded_guardrails[0]

        response = await client.delete(f"/api/v1/guardrails/{guardrail.id}")

        assert response.status_code == 401
