# API Reference

Complete API documentation for Cerberus.

## Base URLs

| Environment | URL |
|-------------|-----|
| Local Development | `http://localhost:8000` |
| Production | Configure via deployment |

## Authentication

Cerberus uses two authentication methods:

| API | Authentication | Header |
|-----|----------------|--------|
| Control Plane (Admin) | JWT Token | `Authorization: Bearer <jwt>` |
| Proxy (MCP Clients) | User Access Key | `Authorization: Bearer <uak_xxx>` |

---

## Proxy API

The proxy endpoint is used by MCP clients to send requests through Cerberus governance.

### POST /governance-plane/api/v1/proxy/{path}

Proxy an MCP request to the upstream server with inline governance.

**Authentication:** User Access Key

**Path Parameters:**
- `path` (optional): Path to forward to upstream (e.g., `v1/tools/call`)

**Request:**
```http
POST /governance-plane/api/v1/proxy/v1/tools/call HTTP/1.1
Authorization: Bearer uak_A7xK2mB9cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV2wX3yZ4
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "read_file",
    "arguments": {
      "path": "/workspace/data.txt"
    }
  }
}
```

**Response (Allowed):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "File contents here..."
      }
    ]
  }
}
```

**Response (Blocked):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32001,
    "message": "Request blocked by governance policy: Tool 'read_file' denied for role 'analyst'",
    "data": {
      "decision_id": "dec_abc123",
      "action": "block_request",
      "guardrails_triggered": ["rbac"]
    }
  }
}
```

**Response Headers:**
```
X-Request-ID: req_xyz789
X-Request-Decision-ID: dec_abc123
X-Response-Decision-ID: dec_def456
```

**Supported HTTP Methods:**
- `POST` - Primary method for MCP JSON-RPC
- `GET` - Query params preserved
- `PUT`, `PATCH` - Body forwarded
- `DELETE` - Optional body
- `OPTIONS`, `HEAD` - No body

---

## Control Plane API

Admin APIs for managing tenants, workspaces, users, and policies.

### Authentication

#### POST /control-plane/api/v1/auth/login

Authenticate and receive JWT tokens.

**Request:**
```json
{
  "email": "admin@acme.com",
  "password": "secretpassword",
  "tenant_slug": "acme-corp"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

#### POST /control-plane/api/v1/auth/refresh

Refresh an expired access token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

### Tenants

#### GET /control-plane/api/v1/tenants

List all tenants. **Requires:** `super_admin`

**Response:**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Acme Corporation",
      "slug": "acme-corp",
      "subscription_tier": "enterprise",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}
```

#### POST /control-plane/api/v1/tenants

Create a new tenant. **Requires:** `super_admin`

**Request:**
```json
{
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "subscription_tier": "enterprise",
  "admin_email": "admin@acme.com",
  "admin_password": "securepassword"
}
```

#### GET /control-plane/api/v1/tenants/{tenant_id}

Get tenant details. **Requires:** `tenant_admin` or `super_admin`

#### PUT /control-plane/api/v1/tenants/{tenant_id}

Update tenant. **Requires:** `tenant_admin` or `super_admin`

#### DELETE /control-plane/api/v1/tenants/{tenant_id}

Soft delete tenant. **Requires:** `super_admin`

---

### Workspaces

#### GET /control-plane/api/v1/workspaces/{workspace_id}

Get workspace details. **Requires:** `workspace_admin` or higher

**Response:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Production",
  "slug": "production",
  "environment_type": "production",
  "mcp_server_url": "https://mcp.acme.com/production",
  "settings": {
    "fail_mode": "closed",
    "decision_timeout_ms": 5000
  },
  "is_active": true
}
```

#### POST /control-plane/api/v1/workspaces

Create workspace. **Requires:** `tenant_admin`

**Request:**
```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Production",
  "slug": "production",
  "environment_type": "production",
  "mcp_server_url": "https://mcp.acme.com/production"
}
```

#### PUT /control-plane/api/v1/workspaces/{workspace_id}

Update workspace. **Requires:** `workspace_admin`

#### DELETE /control-plane/api/v1/workspaces/{workspace_id}

Delete workspace. **Requires:** `tenant_admin`

---

### Users

#### GET /control-plane/api/v1/users

List users. **Requires:** `tenant_admin`

**Query Parameters:**
- `tenant_id` (required for non-super_admin)
- `role` (optional): Filter by role
- `page`, `per_page`: Pagination

#### POST /control-plane/api/v1/users

Create user. **Requires:** `tenant_admin`

**Request:**
```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "external_id": "jane.developer",
  "email": "jane@acme.com",
  "display_name": "Jane Developer",
  "role": "developer",
  "password": null,
  "workspace_ids": ["660e8400-e29b-41d4-a716-446655440001"]
}
```

**Notes:**
- Set `password` to create a portal user (can login to admin UI)
- Set `password: null` for MCP-only users (authenticate via access keys)

#### GET /control-plane/api/v1/users/{user_id}

Get user details.

#### PUT /control-plane/api/v1/users/{user_id}

Update user.

#### DELETE /control-plane/api/v1/users/{user_id}

Soft delete user.

---

### User Access Keys

#### POST /control-plane/api/v1/user-access-keys

Create an access key for a user. **Requires:** `tenant_admin`

**Request:**
```json
{
  "user_id": "770e8400-e29b-41d4-a716-446655440002",
  "workspace_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Jane's Production Key",
  "scopes": ["decisions:*"],
  "expires_at": "2025-12-31T23:59:59Z"
}
```

**Response:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440005",
  "key": "uak_A7xK2mB9cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV2wX3yZ4",
  "user_id": "770e8400-e29b-41d4-a716-446655440002",
  "workspace_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Jane's Production Key",
  "scopes": ["decisions:*"],
  "created_at": "2024-01-15T12:00:00Z"
}
```

**Warning:** The `key` field is only shown once! Store it securely.

#### GET /control-plane/api/v1/user-access-keys

List access keys. **Requires:** `tenant_admin`

**Query Parameters:**
- `user_id` (optional): Filter by user

#### DELETE /control-plane/api/v1/user-access-keys/{key_id}

Revoke an access key.

#### POST /control-plane/api/v1/user-access-keys/{key_id}/rotate

Rotate a key (create new, revoke old).

---

### Policies

#### POST /control-plane/api/v1/policies

Create a policy. **Requires:** `tenant_admin`

**Request:**
```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "workspace_id": null,
  "user_id": null,
  "name": "Organization Security Baseline",
  "priority": 100,
  "enabled": true,
  "guardrails": {
    "rbac": {
      "enabled": true,
      "default_action": "deny",
      "rules": [
        {
          "role": "developer",
          "tools": {
            "allow": ["filesystem/*", "git/*"],
            "deny": ["database/drop_*"]
          }
        }
      ]
    },
    "rate_limit": {
      "enabled": true,
      "default_limits": {
        "requests_per_minute": 100
      }
    },
    "pii_detection": {
      "enabled": true,
      "action": "redact",
      "types": {
        "ssn": {"enabled": true, "action": "block"},
        "email": {"enabled": true, "action": "redact"}
      }
    }
  }
}
```

**Policy Scope:**
- `workspace_id: null, user_id: null` → Tenant-level (applies to all)
- `workspace_id: <id>, user_id: null` → Workspace-level (environment override)
- `workspace_id: <id>, user_id: <id>` → User-level (individual exception)

#### GET /control-plane/api/v1/workspaces/{workspace_id}/policies

List policies for a workspace.

#### GET /control-plane/api/v1/policies/{policy_id}

Get policy details.

#### PUT /control-plane/api/v1/policies/{policy_id}

Update policy.

#### DELETE /control-plane/api/v1/policies/{policy_id}

Delete policy.

---

### Audit Logs

#### GET /control-plane/api/v1/logs/decisions

Query audit logs. **Requires:** `workspace_admin`

**Query Parameters:**
- `workspace_id` (required)
- `start_date`, `end_date`: Date range
- `user_id`: Filter by user
- `action`: Filter by action (allow, block_request, block_response, modify)
- `tool_name`: Filter by tool
- `page`, `per_page`: Pagination

**Response:**
```json
{
  "items": [
    {
      "id": "log_abc123",
      "decision_id": "dec_xyz789",
      "tenant_id": "550e8400...",
      "workspace_id": "660e8400...",
      "user_id": "770e8400...",
      "direction": "request",
      "method": "tools/call",
      "tool_name": "read_file",
      "action": "allow",
      "allowed": true,
      "processing_time_ms": 12,
      "guardrail_events": [...],
      "created_at": "2024-01-15T12:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 20
}
```

#### GET /control-plane/api/v1/logs/decisions/{decision_id}

Get detailed decision log.

---

### Analytics

#### GET /control-plane/api/v1/analytics/dashboard

Get dashboard summary. **Requires:** `workspace_admin`

**Query Parameters:**
- `workspace_id` (required)
- `period`: `day`, `week`, `month`

**Response:**
```json
{
  "total_requests": 15420,
  "allowed_requests": 14200,
  "blocked_requests": 1220,
  "block_rate": 0.079,
  "avg_processing_time_ms": 8.5,
  "top_blocked_guardrails": [
    {"guardrail": "rbac", "count": 800},
    {"guardrail": "rate_limit", "count": 320}
  ],
  "requests_by_tool": [
    {"tool": "filesystem/read", "count": 5200},
    {"tool": "git/commit", "count": 3100}
  ]
}
```

---

## Health Endpoints

### GET /health

Basic health check (no auth required).

**Response:**
```json
{
  "status": "healthy",
  "service": "cerberus",
  "version": "1.0.0"
}
```

### GET /health/detailed

Detailed health with component status.

**Response:**
```json
{
  "status": "healthy",
  "service": "cerberus",
  "version": "1.0.0",
  "environment": "production",
  "components": {
    "database": {"status": "healthy"},
    "redis": {"status": "healthy"},
    "control_plane": {"status": "healthy"},
    "governance_plane": {"status": "healthy"},
    "proxy": {
      "status": "healthy",
      "mode": "inline-governance",
      "mcp_timeout_seconds": 30,
      "mcp_max_retries": 2
    }
  }
}
```

---

## Error Responses

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (DELETE) |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 422 | Validation Error |
| 429 | Rate Limited |
| 500 | Internal Server Error |
| 502 | Bad Gateway (upstream error) |
| 504 | Gateway Timeout |

### Error Response Format

```json
{
  "detail": "Human-readable error message"
}
```

### Validation Errors (422)

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

### MCP Error Codes (Proxy)

| Code | Meaning |
|------|---------|
| -32001 | Governance blocked |
| -32002 | Upstream timeout |
| -32003 | Upstream error |
| -32700 | Parse error |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |
