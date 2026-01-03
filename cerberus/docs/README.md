# Cerberus Documentation

Cerberus is a unified governance service for MCP (Model Context Protocol). It provides policy-based access control, data protection, and audit capabilities for AI tool usage.

## Quick Navigation

| Document | Description |
|----------|-------------|
| [Architecture](./architecture.md) | System architecture and request flow |
| [Getting Started](./getting-started.md) | Installation and setup guide |
| [API Reference](./api-reference.md) | Complete API documentation |
| [Authentication](./authentication.md) | Auth flows for admins and MCP clients |
| [Guardrails](./guardrails.md) | Available guardrails and configuration |
| [Migrations](./migrations.md) | Database migrations (local & deployed) |
| [Deployment](./deployment.md) | Production deployment guide |

## What is Cerberus?

Cerberus sits between MCP clients (like Claude Desktop, Cursor) and MCP servers, providing:

- **Access Control**: Role-based permissions for AI tools
- **Data Protection**: PII detection, secrets blocking, content filtering
- **Rate Limiting**: Prevent abuse with configurable limits
- **Audit Logging**: Complete trail of all AI tool usage
- **Multi-tenancy**: Isolated environments for different teams/customers

## Architecture Overview

```
MCP Client (Claude, Cursor, etc.)
       │
       │ POST /governance-plane/api/v1/proxy/{path}
       │ Authorization: Bearer <access_key>
       ▼
┌──────────────────────────────────────────────────────────────┐
│                        CERBERUS                               │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    PROXY ENDPOINT                        │ │
│  │                                                          │ │
│  │  1. Validate access key → derive context                 │ │
│  │  2. Evaluate request against policies (inline)           │ │
│  │  3. Forward to upstream MCP server                       │ │
│  │  4. Evaluate response against policies (inline)          │ │
│  │  5. Return response to client                            │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   CONTROL PLANE                          │ │
│  │  Admin APIs: Tenants, Workspaces, Users, Policies        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 GOVERNANCE ENGINE                        │ │
│  │  Policy Resolution, Guardrail Pipeline, Audit Logging    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
   MCP Server
```

## Key Concepts

### Tenants
Organizations using Cerberus. Each tenant has isolated data and configurations.

### Workspaces
Environments within a tenant (e.g., production, staging, development). Each workspace has:
- Its own MCP server URL
- Policies that override tenant defaults
- Assigned users

### Users
People or services that use MCP tools. Users have:
- A role (developer, analyst, admin, etc.)
- Access to specific workspaces
- User Access Keys for authentication

### Policies
Governance rules applied at tenant, workspace, or user level. Policies configure:
- Which guardrails are enabled
- Guardrail-specific settings (rate limits, RBAC rules, etc.)
- Priority for policy merging

### Guardrails
Security checks executed on every request/response:
- **RBAC**: Role-based tool access control
- **Rate Limiting**: Request throttling
- **PII Detection**: Personal data protection
- **Secrets Detection**: API key/password blocking
- **Content Filter**: Keyword/pattern blocking
- **Custom Rules**: Business-specific logic

## Quick Start

```bash
# Clone repository
git clone <repo>
cd cerberus

# Option A: Docker Compose (recommended)
cd docker
docker-compose up -d  # Migrations run automatically on startup
docker-compose exec cerberus python -m scripts.seed_db  # Optional: seed test data
curl http://localhost:8000/health

# Option B: Manual setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # Edit with your database/Redis URLs
uvicorn app.main:app --reload  # Migrations run automatically on startup
```

See [Getting Started](./getting-started.md) for detailed setup and [Migrations](./migrations.md) for creating new migrations.

## API Endpoints Summary

### Control Plane (Admin)
```
POST   /control-plane/api/v1/auth/login          # Admin login
GET    /control-plane/api/v1/tenants             # List tenants
POST   /control-plane/api/v1/tenants             # Create tenant
GET    /control-plane/api/v1/workspaces/{id}     # Get workspace
POST   /control-plane/api/v1/policies            # Create policy
POST   /control-plane/api/v1/user-access-keys    # Create access key
```

### Proxy (MCP Clients)
```
POST   /governance-plane/api/v1/proxy/{path}     # Proxy MCP request
GET    /governance-plane/api/v1/proxy/{path}     # Proxy GET request
```

### Health
```
GET    /health                                    # Basic health check
GET    /health/detailed                           # Detailed status
```

## License

Proprietary - All rights reserved
