# Authentication

Cerberus uses two authentication mechanisms for different purposes.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AUTHENTICATION OVERVIEW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   CONTROL PLANE (Admin)              PROXY (MCP Clients)                    │
│   ─────────────────────              ───────────────────                    │
│                                                                              │
│   WHO: Admins, Managers              WHO: AI Tools, Developers              │
│                                                                              │
│   AUTH: JWT Tokens                   AUTH: User Access Keys                 │
│         (email + password)                 (uak_xxxxx)                      │
│                                                                              │
│   PURPOSE: Manage tenants,           PURPOSE: Proxy MCP requests            │
│            users, policies                    with governance               │
│                                                                              │
│   HEADER: Authorization: Bearer      HEADER: Authorization: Bearer          │
│           <jwt_token>                        <uak_xxxxx>                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Aspect | Control Plane (JWT) | Proxy (User Access Key) |
|--------|--------------------|-----------------------|
| **Who uses it** | Admins via portal | MCP clients/AI tools |
| **Credential** | Email + Password | Access Key |
| **Context source** | JWT payload | Key's DB relationships |
| **Tenant isolation** | JWT `tenant_id` claim | Key → User → Tenant |
| **Workspace** | Path parameter | Key's `workspace_id` |
| **Expiration** | Short-lived (1h) | Configurable (months/years) |

---

## User Access Keys (MCP Clients)

User Access Keys are the primary authentication for MCP clients using the proxy endpoint.

### Key Format

```
uak_A7xK2mB9cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV2wX3yZ4
│   └─────────────────────────────────────────────────┘
│                    Base64 random data
└── Prefix
```

### Creating a Key

```bash
POST /control-plane/api/v1/user-access-keys
Authorization: Bearer <admin-jwt>
Content-Type: application/json

{
  "user_id": "770e8400-e29b-41d4-a716-446655440002",
  "workspace_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Production Key",
  "scopes": ["decisions:*"],
  "expires_at": "2025-12-31T23:59:59Z"
}
```

**Response (key shown only once):**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440005",
  "key": "uak_A7xK2mB9cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV2wX3yZ4",
  "user_id": "770e8400-e29b-41d4-a716-446655440002",
  "workspace_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Production Key"
}
```

**Important:** The plain key is only returned once at creation. Store it securely.

### Using a Key

```bash
POST /governance-plane/api/v1/proxy/v1/tools/call
Authorization: Bearer uak_A7xK2mB9cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV2wX3yZ4
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": { "name": "read_file", "arguments": { "path": "/data.txt" } }
}
```

### Key Validation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     ACCESS KEY VALIDATION                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   1. Extract key from Authorization header                                   │
│      Authorization: Bearer uak_A7xK2mB9c...                                 │
│                                                                              │
│   2. Hash the key (SHA-256)                                                  │
│      SHA256("uak_A7xK2mB9c...") → "a1b2c3d4e5f6..."                         │
│                                                                              │
│   3. Database lookup with joins                                              │
│      SELECT * FROM user_access_keys                                          │
│      JOIN users ON user_access_keys.user_id = users.id                       │
│      JOIN workspaces ON user_access_keys.workspace_id = workspaces.id        │
│      WHERE key_hash = 'a1b2c3d4e5f6...'                                      │
│        AND is_active = true                                                  │
│        AND is_revoked = false                                                │
│        AND (expires_at IS NULL OR expires_at > NOW())                        │
│                                                                              │
│   4. Derive context from relationships                                       │
│      ┌─────────────────────────────────────────────────────────────┐        │
│      │ UserAccessKeyContext:                                        │        │
│      │   access_key_id: "990e8400..."                               │        │
│      │   user_id:       "770e8400..." (from key)                    │        │
│      │   workspace_id:  "660e8400..." (from key)                    │        │
│      │   tenant_id:     "550e8400..." (from user → tenant)         │        │
│      │   mcp_server_url: "https://mcp.acme.com/prod" (from workspace)│       │
│      │   scopes:        ["decisions:*"]                             │        │
│      └─────────────────────────────────────────────────────────────┘        │
│                                                                              │
│   5. Update usage tracking                                                   │
│      last_used_at = NOW()                                                    │
│      usage_count += 1                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Properties

| Property | Description |
|----------|-------------|
| `user_id` | The user identity for RBAC and audit |
| `workspace_id` | Determines which workspace/MCP server |
| `scopes` | Permissions (e.g., `decisions:*`) |
| `is_active` | Can be disabled without revoking |
| `is_revoked` | Permanently revoked |
| `expires_at` | Optional expiration date |

### Why Access Keys?

1. **Zero Client Friction**: MCP clients only need one header
2. **Secure Identity**: Cannot be spoofed (derived from DB relationships)
3. **Clear Routing**: Key → Workspace → MCP Server URL
4. **Fine-grained Access**: One key per workspace, easy to revoke
5. **Audit Trail**: All requests tracked with user identity

---

## JWT Authentication (Admin Portal)

JWT tokens are used for the Control Plane (admin APIs).

### Login Flow

```bash
POST /control-plane/api/v1/auth/login
Content-Type: application/json

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

### JWT Payload

```json
{
  "sub": "880e8400-e29b-41d4-a716-446655440003",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "tenant_admin",
  "type": "access",
  "exp": 1704070800,
  "iat": 1704067200
}
```

### Using JWT

```bash
GET /control-plane/api/v1/tenants/550e8400.../workspaces
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Token Refresh

Access tokens expire after 1 hour. Use the refresh token to get new tokens:

```bash
POST /control-plane/api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

## User Types

Cerberus supports two types of users:

### Portal Users (Admins)

- Have `password_hash` set
- Can login to admin portal
- Use JWT authentication
- Roles: `super_admin`, `tenant_admin`, `workspace_admin`

### MCP Users

- Have `password_hash` as NULL
- Cannot login to admin portal
- Authenticate via User Access Keys
- Roles: `developer`, `analyst`, `viewer`

---

## Role Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ROLE HIERARCHY                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   super_admin                                                                │
│   ├── Can: Access ALL tenants                                               │
│   ├── Can: Create/delete tenants                                            │
│   └── Can: Platform-wide operations                                         │
│                                                                              │
│   tenant_admin                                                               │
│   ├── Can: Manage OWN tenant only                                           │
│   ├── Can: Create workspaces, users, policies                               │
│   ├── Can: Generate access keys                                             │
│   └── Cannot: Access other tenants                                          │
│                                                                              │
│   workspace_admin                                                            │
│   ├── Can: Manage assigned workspaces                                       │
│   ├── Can: View logs and analytics                                          │
│   └── Cannot: Create workspaces or manage tenant                            │
│                                                                              │
│   developer / analyst / viewer                                               │
│   ├── Can: Use MCP tools via access keys                                    │
│   ├── Subject to: RBAC policies                                             │
│   └── Cannot: Access admin APIs                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Security Best Practices

### Access Keys

1. **Rotate regularly**: Create new keys and revoke old ones
2. **Use expiration**: Set `expires_at` for time-limited access
3. **Scope appropriately**: Use minimal required scopes
4. **Monitor usage**: Review `last_used_at` and `usage_count`
5. **Revoke immediately**: When a key is compromised

### JWT Tokens

1. **Short expiration**: Access tokens expire in 1 hour
2. **Secure storage**: Store refresh tokens securely
3. **HTTPS only**: Never transmit tokens over HTTP
4. **Logout properly**: Clear tokens on logout

### General

1. **Strong passwords**: Enforce complexity for portal users
2. **Tenant isolation**: Users can only access their tenant
3. **Audit logging**: All actions are logged
4. **Principle of least privilege**: Assign minimal required roles
