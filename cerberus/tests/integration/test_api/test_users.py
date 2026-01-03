"""
User API Integration Tests

Comprehensive tests for the dashboard user management endpoints.
Users are dashboard users (NOT MCP agents) who access the control plane.

Endpoints Tested:
    - POST   /api/v1/organisations/{org_id}/users     - Create user
    - GET    /api/v1/organisations/{org_id}/users     - List users
    - GET    /api/v1/users/{id}                       - Get user
    - PUT    /api/v1/users/{id}                       - Update user
    - DELETE /api/v1/users/{id}                       - Delete user

Authorization Rules:
    - SuperAdmin: Full access to all users
    - OrgAdmin: Can manage users in their organisation
    - OrgViewer: Can only view users in their organisation

User Roles:
    - super_admin: Platform admin (system administrators)
    - org_admin: Full admin for their organisation
    - org_viewer: Read-only access to dashboards and logs

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
# CREATE USER TESTS
# =============================================================================


class TestCreateUser:
    """
    Tests for POST /api/v1/organisations/{org_id}/users endpoint.

    This endpoint creates a new dashboard user within an organisation.
    OrgAdmin or higher can create users.

    Request Body:
        - email (str, required): User email address (unique)
        - password (str, required): User password (min 8 chars)
        - display_name (str, required): User display name
        - role (str, required): User role (org_admin, org_viewer)

    Response: UserResponse with id, email, display_name, role, timestamps
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_create_user_org_admin_role_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can create a new org_admin user.

        Given: Authenticated as OrgAdmin
        When: POST /organisations/{org_id}/users with org_admin role
        Then: Returns 201 with user details
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "newadmin@test.com",
                "password": "securepassword123",
                "display_name": "New Admin User",
                "role": "org_admin",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()

        assert data["email"] == "newadmin@test.com"
        assert data["display_name"] == "New Admin User"
        assert data["role"] == "org_admin"
        assert data["organisation_id"] == str(test_organisation.id)
        assert "id" in data
        assert "created_at" in data
        # Password should not be returned
        assert "password" not in data
        assert "password_hash" not in data

    async def test_create_user_org_viewer_role_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can create a new org_viewer user.

        Given: Authenticated as OrgAdmin
        When: POST with org_viewer role
        Then: Returns 201 with viewer role
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "newviewer@test.com",
                "password": "viewerpassword123",
                "display_name": "New Viewer User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "org_viewer"

    async def test_create_user_super_admin_any_org(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_organisation,
    ):
        """
        SuperAdmin can create users in any organisation.

        Given: Authenticated as SuperAdmin
        When: POST to any organisation
        Then: Returns 201 with user created
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "superadmin.created@test.com",
                "password": "password12345",
                "display_name": "SuperAdmin Created User",
                "role": "org_admin",
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 201

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    async def test_create_user_missing_email(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails when email is missing.

        Given: Authenticated as OrgAdmin
        When: POST without email field
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "password": "password123",
                "display_name": "No Email User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    async def test_create_user_invalid_email(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails with invalid email format.

        Given: Authenticated as OrgAdmin
        When: POST with malformed email
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "not-an-email",
                "password": "password123",
                "display_name": "Invalid Email User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    async def test_create_user_password_too_short(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails when password is too short.

        Given: Authenticated as OrgAdmin
        When: POST with password < 8 characters
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "shortpass@test.com",
                "password": "short",
                "display_name": "Short Password User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    async def test_create_user_invalid_role(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails with invalid role.

        Given: Authenticated as OrgAdmin
        When: POST with non-existent role
        Then: Returns 422 Unprocessable Entity
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "invalidrole@test.com",
                "password": "password123",
                "display_name": "Invalid Role User",
                "role": "super_mega_admin",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    async def test_create_user_duplicate_email(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Creation fails when email already exists.

        Given: User with email exists
        When: POST with same email
        Then: Returns 409 Conflict
        """
        email = "duplicate@test.com"

        # Create first user
        await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": email,
                "password": "password123",
                "display_name": "First User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )

        # Try to create with same email
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": email,
                "password": "password456",
                "display_name": "Duplicate User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 409

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_create_user_requires_authentication(
        self,
        client: AsyncClient,
        test_organisation,
    ):
        """
        Creation requires authentication.

        Given: No authentication headers
        When: POST to create user
        Then: Returns 401 Unauthorized
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "unauth@test.com",
                "password": "password123",
                "display_name": "Unauthenticated User",
                "role": "org_viewer",
            },
        )

        assert response.status_code == 401

    async def test_create_user_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_organisation,
    ):
        """
        OrgViewer cannot create users.

        Given: Authenticated as OrgViewer
        When: POST to create user
        Then: Returns 403 Forbidden
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "viewer.created@test.com",
                "password": "password123",
                "display_name": "Viewer Created User",
                "role": "org_viewer",
            },
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    async def test_create_user_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin cannot create users in other organisations.

        Given: Authenticated as OrgAdmin of different org
        When: POST to other organisation
        Then: Returns 403 Forbidden
        """
        response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "crossorg@test.com",
                "password": "password123",
                "display_name": "Cross-org User",
                "role": "org_viewer",
            },
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403


# =============================================================================
# LIST USERS TESTS
# =============================================================================


class TestListUsers:
    """
    Tests for GET /api/v1/organisations/{org_id}/users endpoint.

    This endpoint lists all users in an organisation with pagination.

    Query Parameters:
        - page (int, optional): Page number (default: 1)
        - per_page (int, optional): Items per page (default: 20, max: 100)

    Response: Paginated list of UserResponse objects
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_list_users_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        org_admin_user,
    ):
        """
        OrgAdmin can list users in their organisation.

        Given: Authenticated as OrgAdmin, users exist
        When: GET /organisations/{org_id}/users
        Then: Returns 200 with paginated list
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}/users",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) >= 1

    async def test_list_users_pagination(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Pagination works correctly for user listing.

        Given: Multiple users exist
        When: GET with pagination params
        Then: Returns correct subset and pagination metadata
        """
        # Create multiple users
        for i in range(5):
            await client.post(
                f"/api/v1/organisations/{test_organisation.id}/users",
                json={
                    "email": f"pagination.user{i}@test.com",
                    "password": "password123",
                    "display_name": f"Pagination User {i}",
                    "role": "org_viewer",
                },
                headers=org_admin_headers,
            )

        # Request with pagination
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}/users",
            params={"page": 1, "per_page": 2},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 2

    async def test_list_users_org_viewer_can_read(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_organisation,
    ):
        """
        OrgViewer can list users (read-only access).

        Given: Authenticated as OrgViewer
        When: GET /organisations/{org_id}/users
        Then: Returns 200 with user list
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}/users",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_list_users_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_organisation,
    ):
        """
        Cannot list users of other organisations.

        Given: Authenticated as admin of different org
        When: GET users of another org
        Then: Returns 403 Forbidden
        """
        response = await client.get(
            f"/api/v1/organisations/{test_organisation.id}/users",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403


# =============================================================================
# GET USER TESTS
# =============================================================================


class TestGetUser:
    """
    Tests for GET /api/v1/users/{user_id} endpoint.

    This endpoint retrieves a single user by ID.

    Path Parameters:
        - user_id (UUID): User identifier

    Response: UserResponse with full details
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_get_user_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        org_admin_user,
    ):
        """
        OrgAdmin can get user details.

        Given: Authenticated as OrgAdmin
        When: GET /users/{id}
        Then: Returns 200 with user details
        """
        response = await client.get(
            f"/api/v1/users/{org_admin_user.id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(org_admin_user.id)
        assert data["email"] == org_admin_user.email
        assert "display_name" in data
        assert "role" in data
        assert "created_at" in data
        # Sensitive fields should not be exposed
        assert "password" not in data
        assert "password_hash" not in data

    async def test_get_user_org_viewer_can_read(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        org_admin_user,
    ):
        """
        OrgViewer can get user details (same org).

        Given: Authenticated as OrgViewer
        When: GET /users/{id} for user in same org
        Then: Returns 200 with user details
        """
        response = await client.get(
            f"/api/v1/users/{org_admin_user.id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_get_user_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        org_admin_user,
    ):
        """
        Cannot get user from other organisation.

        Given: Authenticated as admin of different org
        When: GET user from another org
        Then: Returns 403 Forbidden
        """
        response = await client.get(
            f"/api/v1/users/{org_admin_user.id}",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_get_user_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent user.

        Given: Authenticated as OrgAdmin
        When: GET /users/{non_existent_id}
        Then: Returns 404 Not Found
        """
        response = await client.get(
            f"/api/v1/users/{make_uuid()}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    async def test_get_user_invalid_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Given: Authenticated as OrgAdmin
        When: GET /users/{invalid_uuid}
        Then: Returns 400 Bad Request
        """
        response = await client.get(
            "/api/v1/users/not-a-valid-uuid",
            headers=org_admin_headers,
        )

        assert response.status_code == 400


# =============================================================================
# UPDATE USER TESTS
# =============================================================================


class TestUpdateUser:
    """
    Tests for PUT /api/v1/users/{user_id} endpoint.

    This endpoint updates an existing user.

    Path Parameters:
        - user_id (UUID): User identifier

    Request Body (all optional):
        - display_name (str): New display name
        - role (str): New role (org_admin, org_viewer)
        - is_active (bool): Active status

    Response: Updated UserResponse
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_update_user_display_name_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can update user display name.

        Given: Authenticated as OrgAdmin
        When: PUT /users/{id} with new display_name
        Then: Returns 200 with updated name
        """
        # Create user to update
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "update.name@test.com",
                "password": "password123",
                "display_name": "Original Name",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )
        user_id = create_response.json()["id"]

        # Update display name
        response = await client.put(
            f"/api/v1/users/{user_id}",
            json={"display_name": "Updated Display Name"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Display Name"

    async def test_update_user_role_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can update user role.

        Given: Authenticated as OrgAdmin
        When: PUT /users/{id} with new role
        Then: Returns 200 with updated role
        """
        # Create user to update
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "update.role@test.com",
                "password": "password123",
                "display_name": "Role Change User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )
        user_id = create_response.json()["id"]

        # Update role
        response = await client.put(
            f"/api/v1/users/{user_id}",
            json={"role": "org_admin"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "org_admin"

    async def test_update_user_deactivate(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can deactivate a user.

        Given: Authenticated as OrgAdmin
        When: PUT /users/{id} with is_active=false
        Then: Returns 200 with user deactivated
        """
        # Create user to deactivate
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "deactivate@test.com",
                "password": "password123",
                "display_name": "Deactivate User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )
        user_id = create_response.json()["id"]

        # Deactivate
        response = await client.put(
            f"/api/v1/users/{user_id}",
            json={"is_active": False},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    async def test_update_user_invalid_role(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Update fails with invalid role.

        Given: Authenticated as OrgAdmin
        When: PUT with invalid role value
        Then: Returns 422 Unprocessable Entity
        """
        # Create user
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "invalid.role.update@test.com",
                "password": "password123",
                "display_name": "Invalid Role User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )
        user_id = create_response.json()["id"]

        # Try to update with invalid role
        response = await client.put(
            f"/api/v1/users/{user_id}",
            json={"role": "invalid_role"},
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_update_user_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        org_admin_user,
    ):
        """
        OrgViewer cannot update users.

        Given: Authenticated as OrgViewer
        When: PUT /users/{id}
        Then: Returns 403 Forbidden
        """
        response = await client.put(
            f"/api/v1/users/{org_admin_user.id}",
            json={"display_name": "Viewer Update Attempt"},
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    async def test_update_user_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        org_admin_user,
    ):
        """
        Cannot update user of other organisation.

        Given: Authenticated as admin of different org
        When: PUT user of another org
        Then: Returns 403 Forbidden
        """
        response = await client.put(
            f"/api/v1/users/{org_admin_user.id}",
            json={"display_name": "Cross-org Update"},
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_update_user_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Update returns 404 for non-existent user.

        Given: Authenticated as OrgAdmin
        When: PUT /users/{non_existent_id}
        Then: Returns 404 Not Found
        """
        response = await client.put(
            f"/api/v1/users/{make_uuid()}",
            json={"display_name": "Update Non-existent"},
            headers=org_admin_headers,
        )

        assert response.status_code == 404


# =============================================================================
# DELETE USER TESTS
# =============================================================================


class TestDeleteUser:
    """
    Tests for DELETE /api/v1/users/{user_id} endpoint.

    This endpoint soft-deletes a user.
    OrgAdmin or higher can delete users.

    Path Parameters:
        - user_id (UUID): User identifier

    Response: 204 No Content on success
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    async def test_delete_user_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        OrgAdmin can delete a user.

        Given: Authenticated as OrgAdmin, user exists
        When: DELETE /users/{id}
        Then: Returns 204 and user is no longer accessible
        """
        # Create user to delete
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "delete.user@test.com",
                "password": "password123",
                "display_name": "User to Delete",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )
        user_id = create_response.json()["id"]

        # Delete user
        response = await client.delete(
            f"/api/v1/users/{user_id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 204

        # Verify user is no longer accessible
        get_response = await client.get(
            f"/api/v1/users/{user_id}",
            headers=org_admin_headers,
        )
        assert get_response.status_code == 404

    async def test_delete_user_super_admin(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        SuperAdmin can delete any user.

        Given: Authenticated as SuperAdmin
        When: DELETE user in any org
        Then: Returns 204
        """
        # Create user as org admin
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "super.delete@test.com",
                "password": "password123",
                "display_name": "SuperAdmin Delete Target",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )
        user_id = create_response.json()["id"]

        # Delete as super admin
        response = await client.delete(
            f"/api/v1/users/{user_id}",
            headers=super_admin_headers,
        )

        assert response.status_code == 204

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    async def test_delete_user_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        org_admin_user,
    ):
        """
        OrgViewer cannot delete users.

        Given: Authenticated as OrgViewer
        When: DELETE /users/{id}
        Then: Returns 403 Forbidden
        """
        response = await client.delete(
            f"/api/v1/users/{org_admin_user.id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    async def test_delete_user_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        org_admin_user,
    ):
        """
        Cannot delete user of other organisation.

        Given: Authenticated as admin of different org
        When: DELETE user of another org
        Then: Returns 403 Forbidden
        """
        response = await client.delete(
            f"/api/v1/users/{org_admin_user.id}",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    # -------------------------------------------------------------------------
    # Not Found
    # -------------------------------------------------------------------------

    async def test_delete_user_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Delete returns 404 for non-existent user.

        Given: Authenticated as OrgAdmin
        When: DELETE /users/{non_existent_id}
        Then: Returns 404 Not Found
        """
        response = await client.delete(
            f"/api/v1/users/{make_uuid()}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    async def test_delete_user_idempotent(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Deleting already-deleted user returns 404.

        Given: User was already deleted
        When: DELETE again
        Then: Returns 404 Not Found
        """
        # Create and delete
        create_response = await client.post(
            f"/api/v1/organisations/{test_organisation.id}/users",
            json={
                "email": "double.delete@test.com",
                "password": "password123",
                "display_name": "Double Delete User",
                "role": "org_viewer",
            },
            headers=org_admin_headers,
        )
        user_id = create_response.json()["id"]

        # First delete
        await client.delete(
            f"/api/v1/users/{user_id}",
            headers=org_admin_headers,
        )

        # Second delete should return 404
        response = await client.delete(
            f"/api/v1/users/{user_id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404
