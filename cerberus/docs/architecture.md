# Architecture

Cerberus is a unified governance service that combines MCP proxying with inline policy enforcement. This eliminates the need for a separate gateway service.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CERBERUS SERVICE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         PROXY LAYER                                     │ │
│  │                                                                         │ │
│  │   POST /governance-plane/api/v1/proxy/{path}                           │ │
│  │                                                                         │ │
│  │   • Accepts MCP requests from clients                                  │ │
│  │   • Validates access keys (derives tenant/workspace/user context)      │ │
│  │   • Runs governance checks inline (no network hop)                     │ │
│  │   • Forwards allowed requests to upstream MCP servers                  │ │
│  │   • Evaluates responses before returning to client                     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                       CONTROL PLANE                                     │ │
│  │                                                                         │ │
│  │   /control-plane/api/v1/*                                              │ │
│  │                                                                         │ │
│  │   • Tenant Management (create, update, delete organizations)           │ │
│  │   • Workspace Management (environments with MCP server URLs)           │ │
│  │   • User Management (developers, admins, analysts)                     │ │
│  │   • Policy Management (guardrail configurations)                       │ │
│  │   • Access Key Management (create, revoke, rotate)                     │ │
│  │   • Audit Logs & Analytics                                             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     GOVERNANCE ENGINE                                   │ │
│  │                                                                         │ │
│  │   • Policy Resolution (merge tenant → workspace → user policies)       │ │
│  │   • Decision Engine (orchestrates guardrail execution)                 │ │
│  │   • Guardrail Pipeline (RBAC, Rate Limit, PII, Secrets, etc.)         │ │
│  │   • Event Emitter (audit log creation)                                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        DATA LAYER                                       │ │
│  │                                                                         │ │
│  │   PostgreSQL                    Redis                                   │ │
│  │   • Tenants, Workspaces        • Policy cache                          │ │
│  │   • Users, Access Keys         • Rate limit counters                   │ │
│  │   • Policies, Audit Logs       • Session data                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Request Flow

### MCP Client Request (Proxy Endpoint)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PROXY REQUEST FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   MCP Client (Claude, Cursor, etc.)                                         │
│       │                                                                      │
│       │ POST /governance-plane/api/v1/proxy/v1/tools/call                   │
│       │ Authorization: Bearer uak_xxxxx...                                   │
│       │ Body: { "jsonrpc": "2.0", "method": "tools/call", ... }             │
│       ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  STEP 1: ACCESS KEY VALIDATION                                       │   │
│   │                                                                      │   │
│   │  1. Extract key from Authorization header                           │   │
│   │  2. Hash key (SHA-256) and lookup in database                       │   │
│   │  3. Validate: is_active, not_revoked, not_expired                   │   │
│   │  4. Derive context from key's relationships:                        │   │
│   │     • user_id      (from key)                                       │   │
│   │     • workspace_id (from key)                                       │   │
│   │     • tenant_id    (from user → tenant)                             │   │
│   │     • mcp_server_url (from workspace)                               │   │
│   │                                                                      │   │
│   │  Invalid key → 401 Unauthorized                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  STEP 2: REQUEST EVALUATION (Inline)                                 │   │
│   │                                                                      │   │
│   │  1. Load effective policy (merged from tenant/workspace/user)       │   │
│   │  2. Build guardrail pipeline for REQUEST direction                  │   │
│   │  3. Execute guardrails in order:                                    │   │
│   │     • RBAC → Rate Limit → Custom → Content → PII → Secrets         │   │
│   │  4. Short-circuit on BLOCK, apply MODIFY if needed                  │   │
│   │                                                                      │   │
│   │  BLOCK → Return error response to client                            │   │
│   │  ALLOW/MODIFY → Continue to Step 3                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  STEP 3: FORWARD TO UPSTREAM                                         │   │
│   │                                                                      │   │
│   │  1. Build upstream URL: {mcp_server_url}/{path}                     │   │
│   │  2. Forward request with Cerberus headers:                          │   │
│   │     • X-Tenant-ID, X-Workspace-ID, X-User-ID                        │   │
│   │     • X-Gateway-Request-ID, X-Forwarded-For                         │   │
│   │  3. Optionally forward client Authorization header                  │   │
│   │  4. Handle response with retry logic                                │   │
│   │                                                                      │   │
│   │  Timeout/Error → Return 504/502 error                               │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  STEP 4: RESPONSE EVALUATION (Inline)                                │   │
│   │                                                                      │   │
│   │  1. Build guardrail pipeline for RESPONSE direction                 │   │
│   │  2. Execute guardrails in order:                                    │   │
│   │     • Secrets → PII → DLP → Content → Custom                        │   │
│   │  3. Short-circuit on BLOCK, apply MODIFY (redaction) if needed      │   │
│   │                                                                      │   │
│   │  BLOCK → Return error response to client                            │   │
│   │  ALLOW/MODIFY → Continue to Step 5                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  STEP 5: AUDIT & RETURN                                              │   │
│   │                                                                      │   │
│   │  1. Create audit log entry (non-blocking)                           │   │
│   │  2. Return response to client with headers:                         │   │
│   │     • X-Request-ID                                                  │   │
│   │     • X-Request-Decision-ID                                         │   │
│   │     • X-Response-Decision-ID                                        │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│   MCP Client receives response                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
cerberus/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── config/
│   │   ├── settings.py            # Pydantic settings (env vars)
│   │   └── constants.py           # Enums and constants
│   ├── core/
│   │   ├── logging.py             # Structured logging
│   │   ├── security.py            # Password hashing, JWT
│   │   └── utils.py               # Utility functions
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── tenant.py
│   │   ├── workspace.py
│   │   ├── user.py
│   │   ├── user_access_key.py
│   │   ├── policy.py
│   │   └── audit_log.py
│   ├── schemas/                   # Pydantic request/response schemas
│   │   ├── tenant.py
│   │   ├── workspace.py
│   │   ├── user.py
│   │   ├── policy.py
│   │   ├── decision.py
│   │   └── proxy.py
│   ├── db/
│   │   ├── session.py             # Database session management
│   │   └── repositories/          # Data access layer
│   ├── cache/
│   │   └── redis_client.py        # Redis connection
│   ├── control_plane/             # Admin APIs
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   ├── dependencies.py    # JWT auth dependencies
│   │   │   └── v1/                # Endpoint handlers
│   │   └── services/              # Business logic
│   ├── governance_plane/          # Proxy & Governance
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   ├── dependencies.py    # Access key validation
│   │   │   └── v1/
│   │   │       └── proxy.py       # Proxy endpoint
│   │   ├── proxy/
│   │   │   ├── client.py          # HTTP client for upstream
│   │   │   └── service.py         # Proxy orchestration
│   │   ├── engine/
│   │   │   ├── decision_engine.py # Policy evaluation orchestrator
│   │   │   ├── pipeline.py        # Guardrail execution pipeline
│   │   │   └── policy_loader.py   # Policy loading & caching
│   │   ├── guardrails/            # Guardrail implementations
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   ├── rbac/
│   │   │   ├── rate_limit/
│   │   │   ├── pii/
│   │   │   ├── secrets/
│   │   │   ├── content/
│   │   │   └── custom/
│   │   └── events/
│   │       └── emitter.py         # Audit log emission
│   └── middleware/
│       ├── logging.py             # Request logging
│       └── error_handler.py       # Global exception handling
├── alembic/                       # Database migrations
├── docker/                        # Docker configuration
├── tests/                         # Test suite
└── docs/                          # Documentation
```

## Data Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA MODEL                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                              TENANT                                          │
│                         (Organization)                                       │
│                     ┌─────────────────────┐                                 │
│                     │ id                   │                                 │
│                     │ name, slug           │                                 │
│                     │ subscription_tier    │                                 │
│                     │ settings (JSON)      │                                 │
│                     └──────────┬──────────┘                                 │
│                                │                                             │
│          ┌─────────────────────┼─────────────────────┐                      │
│          │                     │                     │                      │
│          ▼                     ▼                     ▼                      │
│   ┌─────────────┐       ┌─────────────┐       ┌─────────────┐              │
│   │  WORKSPACE  │       │    USER     │       │   POLICY    │              │
│   │             │       │             │       │ (tenant lvl)│              │
│   │ id          │       │ id          │       │             │              │
│   │ name, slug  │       │ external_id │       │ guardrails  │              │
│   │ environment │       │ email, role │       │ priority    │              │
│   │ mcp_server_ │       │ password_   │       │             │              │
│   │   url       │       │   hash      │       │             │              │
│   └──────┬──────┘       └──────┬──────┘       └─────────────┘              │
│          │                     │                                             │
│          │     ┌───────────────┤                                             │
│          │     │               │                                             │
│          │     │ user_workspaces (M:M)                                       │
│          │     │                                                             │
│          │     ▼                                                             │
│          │  ┌──────────────────────────────────────────┐                    │
│          │  │           USER_ACCESS_KEY                 │                    │
│          │  │                                           │                    │
│          │  │ id                                        │                    │
│          └──┤ workspace_id  ← Determines routing       │                    │
│             │ user_id       ← Determines identity      │                    │
│             │ key_hash      ← SHA256 for lookup        │                    │
│             │ scopes        ← ["decisions:*"]          │                    │
│             │ is_active, is_revoked, expires_at        │                    │
│             │                                           │                    │
│             │ DERIVED CONTEXT:                          │                    │
│             │ • tenant_id    (user → tenant)           │                    │
│             │ • mcp_server_url (workspace)             │                    │
│             └──────────────────────────────────────────┘                    │
│                                                                              │
│   AUDIT_LOG                                                                  │
│   ┌──────────────────────────────────────────┐                              │
│   │ decision_id, request_id                   │                              │
│   │ tenant_id, workspace_id, user_id          │                              │
│   │ direction, method, tool_name              │                              │
│   │ action (allow/block/modify)               │                              │
│   │ guardrail_events (JSON)                   │                              │
│   │ processing_time_ms                        │                              │
│   └──────────────────────────────────────────┘                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Policy Resolution

Policies are merged in order of specificity:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        POLICY HIERARCHY                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   When evaluating a request for tenant T, workspace W, user U:               │
│                                                                              │
│   1. Load Tenant-Level Policies                                              │
│      WHERE tenant_id = T AND workspace_id IS NULL AND user_id IS NULL        │
│      → Organization defaults (apply to everyone)                             │
│                                                                              │
│   2. Load Workspace-Level Policies                                           │
│      WHERE tenant_id = T AND workspace_id = W AND user_id IS NULL            │
│      → Environment overrides (production stricter than dev)                  │
│                                                                              │
│   3. Load User-Level Policies                                                │
│      WHERE tenant_id = T AND workspace_id = W AND user_id = U                │
│      → Individual exceptions (special access for specific users)             │
│                                                                              │
│   4. Sort by Priority (DESC)                                                 │
│      Higher priority = applied last = wins conflicts                         │
│                                                                              │
│   5. Deep Merge Guardrail Configs                                            │
│      Later policies override earlier ones                                    │
│                                                                              │
│   Result: Single effective guardrail configuration                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Guardrail Pipeline

Guardrails execute in a specific order based on direction:

### Request Direction (outbound to MCP server)
```
1. RBAC          → Permission check (fast, blocks early)
2. Rate Limit    → Throttling check (Redis lookup)
3. Custom Rules  → Business-specific validation
4. Content Filter→ Keyword/pattern blocking
5. PII Detection → Personal data in request
6. Secrets       → API keys in request
```

### Response Direction (inbound from MCP server)
```
1. Secrets       → API keys/passwords in response (critical)
2. PII Detection → Personal data in response
3. DLP           → Data loss prevention
4. Content Filter→ Inappropriate content
5. Custom Rules  → Business-specific validation
```

## Performance Considerations

| Component | Target Latency | Strategy |
|-----------|----------------|----------|
| Key Validation | < 5ms | Indexed hash lookup |
| Policy Loading | < 5ms | Redis cache |
| Guardrail Pipeline | < 20ms | Early exit, efficient algorithms |
| Upstream Request | Variable | Connection pooling, retries |
| Audit Logging | Non-blocking | Fire-and-forget |
| **Total Overhead** | **< 30ms** | Inline processing |

## Error Handling

Cerberus fails secure by default:

```python
# When governance fails, block the request
try:
    result = await engine.evaluate(request)
except Exception:
    return BLOCK_REQUEST  # Fail secure
```

MCP error responses follow JSON-RPC 2.0:

| Code | Meaning |
|------|---------|
| -32001 | Governance blocked |
| -32002 | Upstream timeout |
| -32003 | Upstream error |
| -32700 | Parse error |
| -32600 | Invalid request |
