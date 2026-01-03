"""
Policy API Integration Tests

Comprehensive tests for the policy management endpoints.

Policies link guardrails to entities (organisations, workspaces, or agents).
Each policy configures ONE guardrail for ONE entity - no complex merging.

Policy Levels (determined by which IDs are provided):
- Organisation-level: Only organisation_id - applies to all workspaces/agents
- Workspace-level: organisation_id + mcp_server_workspace_id - applies to workspace
- Agent-level: All three IDs - applies to specific agent only

Endpoint Summary:
=================
- POST   /api/v1/policies                                              - Create policy
- GET    /api/v1/policies/{id}                                         - Get policy by ID
- PUT    /api/v1/policies/{id}                                         - Update policy
- DELETE /api/v1/policies/{id}                                         - Delete policy
- GET    /api/v1/policies/organisations/{id}/policies                  - List org policies
- GET    /api/v1/policies/mcp-server-workspaces/{id}/policies          - List workspace policies
- GET    /api/v1/policies/agent-accesses/{id}/policies                 - List agent policies
- GET    /api/v1/policies/mcp-server-workspaces/{id}/effective-policies - Get effective policies

Authorization:
==============
- Create/Update/Delete: OrganisationAdmin+ only
- List/Get: Any authenticated user in the organisation
"""

import pytest
from httpx import AsyncClient

from app.config.constants import GuardrailType

# pylint: disable=too-many-arguments,too-many-positional-arguments


# =============================================================================
# CREATE POLICY TESTS
# =============================================================================


class TestCreatePolicy:
    """
    Tests for POST /api/v1/policies endpoint.

    Creates a policy that links a guardrail to an entity.
    The policy level is determined by which IDs are provided.
    """

    # -------------------------------------------------------------------------
    # Success Cases
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_org_level_policy_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        OrgAdmin can create an organisation-level policy.

        Scenario: Create policy with only organisation_id.
        Expected: 201 Created with level="organisation".
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Block SSN Org-wide",
                "action": "block",
                "config": {"direction": "both"},
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Block SSN Org-wide"
        assert data["level"] == "organisation"
        assert data["guardrail_type"] == "pii_ssn"
        assert data["action"] == "block"
        assert data["config"]["direction"] == "both"
        assert data["is_enabled"] is True

    @pytest.mark.asyncio
    async def test_create_workspace_level_policy_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        test_workspace,
        seeded_guardrails,
    ):
        """
        OrgAdmin can create a workspace-level policy.

        Scenario: Create policy with organisation_id + workspace_id.
        Expected: 201 Created with level="workspace".
        """
        rate_limit_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.RATE_LIMIT_PER_MINUTE.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "mcp_server_workspace_id": str(test_workspace.id),
                "guardrail_id": str(rate_limit_guardrail.id),
                "name": "Workspace Rate Limit",
                "action": "block",
                "config": {"limit": 100},
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["level"] == "workspace"
        assert data["mcp_server_workspace_id"] == str(test_workspace.id)
        assert data["config"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_create_agent_level_policy_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        test_workspace,
        test_agent_access,
        seeded_guardrails,
    ):
        """
        OrgAdmin can create an agent-level policy.

        Scenario: Create policy with all three IDs.
        Expected: 201 Created with level="agent".
        """
        rbac_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.RBAC.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "mcp_server_workspace_id": str(test_workspace.id),
                "agent_access_id": str(test_agent_access.id),
                "guardrail_id": str(rbac_guardrail.id),
                "name": "Agent RBAC Policy",
                "action": "block",
                "config": {"allowed_tools": ["filesystem/*"], "default_action": "deny"},
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["level"] == "agent"
        assert data["agent_access_id"] == str(test_agent_access.id)

    @pytest.mark.asyncio
    async def test_create_policy_with_redact_action(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Can create policy with redact action.

        Scenario: Create PII policy with redact action.
        Expected: 201 Created with action="redact".
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Redact SSN Policy",
                "action": "redact",
                "config": {
                    "direction": "both",
                    "redaction_pattern": "[SSN REDACTED]",
                },
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["action"] == "redact"
        assert data["config"]["redaction_pattern"] == "[SSN REDACTED]"

    @pytest.mark.asyncio
    async def test_create_policy_super_admin_any_org(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        SuperAdmin can create policy in any organisation.

        Scenario: SuperAdmin creates policy in an organisation.
        Expected: 201 Created.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "SuperAdmin Created Policy",
                "action": "block",
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 201

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_policy_invalid_config_rejected(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Policy creation fails with invalid config keys for guardrail type.

        Scenario: Use PII config keys for rate_limit guardrail.
        Expected: 400 Bad Request with error about unknown config keys.
        """
        rate_limit_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.RATE_LIMIT_PER_MINUTE.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(rate_limit_guardrail.id),
                "name": "Invalid Config Policy",
                "action": "block",
                "config": {"direction": "both"},  # Invalid for rate_limit!
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 400
        assert "Unknown config keys" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_duplicate_policy_conflict(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Creating duplicate policy for same guardrail at same level fails.

        Scenario: Create two policies for same guardrail at org level.
        Expected: Second creation returns 409 Conflict.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create first policy
        response1 = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "First SSN Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Duplicate SSN Policy",
                "action": "redact",
            },
            headers=org_admin_headers,
        )

        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_policy_guardrail_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        make_uuid,
    ):
        """
        Policy creation fails when guardrail doesn't exist.

        Scenario: Create policy referencing non-existent guardrail.
        Expected: 404 Not Found.
        """
        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": make_uuid(),
                "name": "Policy for Missing Guardrail",
                "action": "block",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_policy_missing_required_fields(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
    ):
        """
        Policy creation fails when required fields missing.

        Scenario: Create policy without guardrail_id.
        Expected: 422 Unprocessable Entity.
        """
        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "name": "Missing Guardrail ID",
                "action": "block",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_policy_invalid_action(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Policy creation fails with invalid action value.

        Scenario: Create policy with non-existent action.
        Expected: 422 Unprocessable Entity.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Invalid Action Policy",
                "action": "invalid_action",
            },
            headers=org_admin_headers,
        )

        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # Authorization Errors
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_policy_requires_auth(
        self,
        client: AsyncClient,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Policy creation requires authentication.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Unauthenticated Policy",
                "action": "block",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_policy_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Org viewers cannot create policies.

        Scenario: OrgViewer tries to create policy.
        Expected: 403 Forbidden.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Viewer Created Policy",
                "action": "block",
            },
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_policy_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Cannot create policy in another organisation.

        Scenario: OrgAdmin of Org B creates policy in Org A.
        Expected: 403 Forbidden.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Cross-org Policy",
                "action": "block",
            },
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403


# =============================================================================
# GET POLICY TESTS
# =============================================================================


class TestGetPolicy:
    """
    Tests for GET /api/v1/policies/{policy_id} endpoint.

    Retrieves a single policy by ID.
    """

    @pytest.mark.asyncio
    async def test_get_policy_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Can retrieve a policy by ID.

        Scenario: Get existing policy.
        Expected: 200 OK with policy details.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy first
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Get Test Policy",
                "action": "redact",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Get the policy
        response = await client.get(
            f"/api/v1/policies/{policy_id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == policy_id
        assert data["name"] == "Get Test Policy"

    @pytest.mark.asyncio
    async def test_get_policy_viewer_can_read(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        org_viewer_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        OrgViewer can read policies in their org.

        Scenario: Viewer gets policy created by admin.
        Expected: 200 OK.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create as admin
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Viewer Readable Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Read as viewer
        response = await client.get(
            f"/api/v1/policies/{policy_id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_policy_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent policy.

        Scenario: Get policy with random UUID.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/policies/{make_uuid()}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_policy_invalid_uuid(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
    ):
        """
        Returns 400 for invalid UUID format.

        Scenario: Get policy with malformed UUID.
        Expected: 400 Bad Request.
        """
        response = await client.get(
            "/api/v1/policies/not-a-uuid",
            headers=org_admin_headers,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_policy_other_org_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        other_org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Cannot access policy from another organisation.

        Scenario: OrgAdmin of Org B tries to read Org A's policy.
        Expected: 403 Forbidden.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create in Org A
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Org A Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Try to read from Org B
        response = await client.get(
            f"/api/v1/policies/{policy_id}",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_policy_unauthenticated(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Unauthenticated requests cannot get policies.

        Scenario: No auth token provided.
        Expected: 401 Unauthorized.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Unauth Test Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Try to get without auth
        response = await client.get(f"/api/v1/policies/{policy_id}")

        assert response.status_code == 401


# =============================================================================
# UPDATE POLICY TESTS
# =============================================================================


class TestUpdatePolicy:
    """
    Tests for PUT /api/v1/policies/{policy_id} endpoint.

    Updates policy name, config, action, or enabled status.
    """

    @pytest.mark.asyncio
    async def test_update_policy_name_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Can update policy name.

        Scenario: Update name of existing policy.
        Expected: 200 OK with updated name.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Original Name",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Update name
        response = await client.put(
            f"/api/v1/policies/{policy_id}",
            json={"name": "Updated Name"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_policy_config_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Can update policy config.

        Scenario: Update config of existing policy.
        Expected: 200 OK with updated config.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Config Update Test",
                "action": "block",
                "config": {"direction": "request"},
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Update config
        response = await client.put(
            f"/api/v1/policies/{policy_id}",
            json={"config": {"direction": "both", "redaction_pattern": "[HIDDEN]"}},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["config"]["direction"] == "both"
        assert data["config"]["redaction_pattern"] == "[HIDDEN]"

    @pytest.mark.asyncio
    async def test_update_policy_action_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Can update policy action.

        Scenario: Change action from block to redact.
        Expected: 200 OK with updated action.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Action Update Test",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Update action
        response = await client.put(
            f"/api/v1/policies/{policy_id}",
            json={"action": "redact"},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "redact"

    @pytest.mark.asyncio
    async def test_update_policy_disable(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Can disable a policy.

        Scenario: Set is_enabled to False.
        Expected: 200 OK with is_enabled=False.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Disable Test",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Disable policy
        response = await client.put(
            f"/api/v1/policies/{policy_id}",
            json={"is_enabled": False},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_enabled"] is False

    @pytest.mark.asyncio
    async def test_update_policy_invalid_config_rejected(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Update fails with invalid config for guardrail type.

        Scenario: Use PII config for rate_limit guardrail.
        Expected: 400 Bad Request.
        """
        rate_limit_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.RATE_LIMIT_PER_MINUTE.value
        )

        # Create policy
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(rate_limit_guardrail.id),
                "name": "Rate Limit Policy",
                "action": "block",
                "config": {"limit": 60},
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Try to update with invalid config
        response = await client.put(
            f"/api/v1/policies/{policy_id}",
            json={"config": {"direction": "both"}},  # Invalid for rate_limit
            headers=org_admin_headers,
        )

        assert response.status_code == 400
        assert "Unknown config keys" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_policy_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent policy.

        Scenario: Try to update non-existent policy.
        Expected: 404 Not Found.
        """
        response = await client.put(
            f"/api/v1/policies/{make_uuid()}",
            json={"name": "Ghost Policy"},
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_policy_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        org_viewer_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Org viewers cannot update policies.

        Scenario: Viewer tries to update policy.
        Expected: 403 Forbidden.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy as admin
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Admin Created Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Try to update as viewer
        response = await client.put(
            f"/api/v1/policies/{policy_id}",
            json={"name": "Viewer Updated"},
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_policy_other_org_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        other_org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Cannot update policy in another organisation.

        Scenario: OrgAdmin of Org B tries to update Org A's policy.
        Expected: 403 Forbidden.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create in Org A
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Org A Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Try to update from Org B
        response = await client.put(
            f"/api/v1/policies/{policy_id}",
            json={"name": "Cross-org Update"},
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403


# =============================================================================
# DELETE POLICY TESTS
# =============================================================================


class TestDeletePolicy:
    """
    Tests for DELETE /api/v1/policies/{policy_id} endpoint.

    Soft deletes a policy.
    """

    @pytest.mark.asyncio
    async def test_delete_policy_success(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        OrgAdmin can delete a policy.

        Scenario: Delete existing policy.
        Expected: 204 No Content, policy no longer retrievable.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Delete Test Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Delete policy
        response = await client.delete(
            f"/api/v1/policies/{policy_id}",
            headers=org_admin_headers,
        )

        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(
            f"/api/v1/policies/{policy_id}",
            headers=org_admin_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_policy_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent policy.

        Scenario: Try to delete non-existent policy.
        Expected: 404 Not Found.
        """
        response = await client.delete(
            f"/api/v1/policies/{make_uuid()}",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_policy_idempotent(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Deleting same policy twice returns 404 on second attempt.

        Scenario: Delete policy, then try again.
        Expected: First returns 204, second returns 404.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Double Delete Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # First delete - success
        response1 = await client.delete(
            f"/api/v1/policies/{policy_id}",
            headers=org_admin_headers,
        )
        assert response1.status_code == 204

        # Second delete - not found
        response2 = await client.delete(
            f"/api/v1/policies/{policy_id}",
            headers=org_admin_headers,
        )
        assert response2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_policy_org_viewer_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        org_viewer_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Org viewers cannot delete policies.

        Scenario: Viewer tries to delete policy.
        Expected: 403 Forbidden.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create policy as admin
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Viewer Delete Test",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Try to delete as viewer
        response = await client.delete(
            f"/api/v1/policies/{policy_id}",
            headers=org_viewer_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_policy_other_org_forbidden(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        other_org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Cannot delete policy in another organisation.

        Scenario: OrgAdmin of Org B tries to delete Org A's policy.
        Expected: 403 Forbidden.
        """
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )

        # Create in Org A
        create_response = await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Org A Delete Test",
                "action": "block",
            },
            headers=org_admin_headers,
        )
        policy_id = create_response.json()["id"]

        # Try to delete from Org B
        response = await client.delete(
            f"/api/v1/policies/{policy_id}",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403


# =============================================================================
# LIST POLICIES TESTS
# =============================================================================


class TestListPolicies:
    """
    Tests for policy listing endpoints.

    - GET /api/v1/policies/organisations/{id}/policies
    - GET /api/v1/policies/mcp-server-workspaces/{id}/policies
    - GET /api/v1/policies/agent-accesses/{id}/policies
    """

    @pytest.mark.asyncio
    async def test_list_organisation_policies(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Can list organisation-level policies.

        Scenario: Create multiple org policies and list them.
        Expected: 200 OK with paginated list.
        """
        # Create multiple policies
        for i, guardrail in enumerate(seeded_guardrails[:3]):
            await client.post(
                "/api/v1/policies",
                json={
                    "organisation_id": str(test_organisation.id),
                    "guardrail_id": str(guardrail.id),
                    "name": f"Org Policy {i}",
                    "action": "block",
                },
                headers=org_admin_headers,
            )

        # List policies
        response = await client.get(
            f"/api/v1/policies/organisations/{test_organisation.id}/policies",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 3
        assert data["pagination"]["total"] == 3

    @pytest.mark.asyncio
    async def test_list_organisation_policies_with_pagination(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        seeded_guardrails,
    ):
        """
        Pagination works for organisation policies.

        Scenario: Create multiple policies, request with pagination.
        Expected: Returns correct page subset.
        """
        # Create policies
        for i, guardrail in enumerate(seeded_guardrails[:5]):
            await client.post(
                "/api/v1/policies",
                json={
                    "organisation_id": str(test_organisation.id),
                    "guardrail_id": str(guardrail.id),
                    "name": f"Paginated Org Policy {i}",
                    "action": "block",
                },
                headers=org_admin_headers,
            )

        # Request with pagination
        response = await client.get(
            f"/api/v1/policies/organisations/{test_organisation.id}/policies",
            params={"page": 1, "per_page": 2},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 2

    @pytest.mark.asyncio
    async def test_list_workspace_policies(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        test_workspace,
        seeded_guardrails,
    ):
        """
        Can list workspace-level policies.

        Scenario: Create workspace policies and list them.
        Expected: 200 OK with workspace policies only.
        """
        # Create workspace policy
        await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "mcp_server_workspace_id": str(test_workspace.id),
                "guardrail_id": str(seeded_guardrails[0].id),
                "name": "Workspace Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )

        # List workspace policies
        response = await client.get(
            f"/api/v1/policies/mcp-server-workspaces/{test_workspace.id}/policies",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) >= 1
        for policy in data["data"]:
            assert policy["mcp_server_workspace_id"] == str(test_workspace.id)

    @pytest.mark.asyncio
    async def test_list_agent_policies(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        test_workspace,
        test_agent_access,
        seeded_guardrails,
    ):
        """
        Can list agent-level policies.

        Scenario: Create agent policies and list them.
        Expected: 200 OK with agent policies only.
        """
        # Create agent policy
        await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "mcp_server_workspace_id": str(test_workspace.id),
                "agent_access_id": str(test_agent_access.id),
                "guardrail_id": str(seeded_guardrails[0].id),
                "name": "Agent Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )

        # List agent policies
        response = await client.get(
            f"/api/v1/policies/agent-accesses/{test_agent_access.id}/policies",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) >= 1
        for policy in data["data"]:
            assert policy["agent_access_id"] == str(test_agent_access.id)

    @pytest.mark.asyncio
    async def test_list_policies_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_organisation,
    ):
        """
        Cannot list policies in another organisation.

        Scenario: OrgAdmin of Org B tries to list Org A's policies.
        Expected: 403 Forbidden.
        """
        response = await client.get(
            f"/api/v1/policies/organisations/{test_organisation.id}/policies",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403


# =============================================================================
# EFFECTIVE POLICIES TESTS
# =============================================================================


class TestEffectivePolicies:
    """
    Tests for GET /api/v1/policies/mcp-server-workspaces/{id}/effective-policies.

    Returns all policies that apply to a workspace/agent, from all levels.
    """

    @pytest.mark.asyncio
    async def test_get_effective_policies_all_levels(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        test_workspace,
        test_agent_access,
        seeded_guardrails,
    ):
        """
        Effective policies include all applicable levels.

        Scenario: Create org, workspace, and agent policies.
        Expected: Effective policies include all three.
        """
        # Create org-level policy
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )
        await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Org SSN Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )

        # Create workspace-level policy
        rate_limit_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.RATE_LIMIT_PER_MINUTE.value
        )
        await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "mcp_server_workspace_id": str(test_workspace.id),
                "guardrail_id": str(rate_limit_guardrail.id),
                "name": "Workspace Rate Limit",
                "action": "block",
                "config": {"limit": 60},
            },
            headers=org_admin_headers,
        )

        # Create agent-level policy
        rbac_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.RBAC.value
        )
        await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "mcp_server_workspace_id": str(test_workspace.id),
                "agent_access_id": str(test_agent_access.id),
                "guardrail_id": str(rbac_guardrail.id),
                "name": "Agent RBAC",
                "action": "block",
            },
            headers=org_admin_headers,
        )

        # Get effective policies with agent
        response = await client.get(
            f"/api/v1/policies/mcp-server-workspaces/{test_workspace.id}/effective-policies",
            params={"agent_access_id": str(test_agent_access.id)},
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["policies"]) == 3
        assert data["organisation_id"] == str(test_organisation.id)
        assert data["mcp_server_workspace_id"] == str(test_workspace.id)

    @pytest.mark.asyncio
    async def test_get_effective_policies_workspace_only(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        test_organisation,
        test_workspace,
        seeded_guardrails,
    ):
        """
        Effective policies without agent_access_id excludes agent policies.

        Scenario: Create org and workspace policies.
        Expected: Returns only org and workspace policies.
        """
        # Create org-level policy
        ssn_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.PII_SSN.value
        )
        await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "guardrail_id": str(ssn_guardrail.id),
                "name": "Org SSN Policy",
                "action": "block",
            },
            headers=org_admin_headers,
        )

        # Create workspace-level policy
        rate_limit_guardrail = next(
            g for g in seeded_guardrails
            if g.guardrail_type == GuardrailType.RATE_LIMIT_PER_MINUTE.value
        )
        await client.post(
            "/api/v1/policies",
            json={
                "organisation_id": str(test_organisation.id),
                "mcp_server_workspace_id": str(test_workspace.id),
                "guardrail_id": str(rate_limit_guardrail.id),
                "name": "Workspace Rate Limit",
                "action": "block",
                "config": {"limit": 60},
            },
            headers=org_admin_headers,
        )

        # Get effective policies (no agent)
        response = await client.get(
            f"/api/v1/policies/mcp-server-workspaces/{test_workspace.id}/effective-policies",
            headers=org_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["policies"]) == 2  # Org + workspace only

    @pytest.mark.asyncio
    async def test_get_effective_policies_workspace_not_found(
        self,
        client: AsyncClient,
        org_admin_headers: dict,
        make_uuid,
    ):
        """
        Returns 404 for non-existent workspace.

        Scenario: Get effective policies for non-existent workspace.
        Expected: 404 Not Found.
        """
        response = await client.get(
            f"/api/v1/policies/mcp-server-workspaces/{make_uuid()}/effective-policies",
            headers=org_admin_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_effective_policies_other_org_forbidden(
        self,
        client: AsyncClient,
        other_org_admin_headers: dict,
        test_workspace,
    ):
        """
        Cannot get effective policies for workspace in another org.

        Scenario: OrgAdmin of Org B tries to get Org A's effective policies.
        Expected: 403 Forbidden.
        """
        response = await client.get(
            f"/api/v1/policies/mcp-server-workspaces/{test_workspace.id}/effective-policies",
            headers=other_org_admin_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_effective_policies_viewer_allowed(
        self,
        client: AsyncClient,
        org_viewer_headers: dict,
        test_workspace,
    ):
        """
        OrgViewer can get effective policies.

        Scenario: Viewer requests effective policies.
        Expected: 200 OK.
        """
        response = await client.get(
            f"/api/v1/policies/mcp-server-workspaces/{test_workspace.id}/effective-policies",
            headers=org_viewer_headers,
        )

        assert response.status_code == 200
