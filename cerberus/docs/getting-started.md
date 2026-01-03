# Getting Started

This guide walks you through setting up Cerberus for local development and basic usage.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Docker (optional, for containerized setup)

---

## Quick Start with Docker

The fastest way to get started:

```bash
# Clone the repository
git clone <repo-url>
cd cerberus

# Navigate to docker directory and start all services
cd docker
docker-compose up -d

# Run migrations
docker-compose exec cerberus alembic upgrade head

# Seed initial data (optional)
docker-compose exec cerberus python -m scripts.seed_db

# Access the API
curl http://localhost:8000/health
```

---

## Manual Setup

### 1. Clone and Install

```bash
# Clone the repository
git clone <repo-url>
cd cerberus

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development (includes testing tools)
pip install -r requirements-dev.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp env.example .env

# Edit .env with your settings
```

**Key Configuration:**

```bash
# Database (required)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cerberus

# Redis (required)
REDIS_URL=redis://localhost:6379/0

# Security (change in production!)
SECRET_KEY=your-secret-key-change-in-production

# MCP Proxy Settings
MCP_REQUEST_TIMEOUT_SECONDS=30.0
MCP_MAX_RETRIES=2
```

### 3. Set Up Database

```bash
# Create the database
createdb cerberus

# Run migrations
alembic upgrade head
```

### 4. Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or install locally
# macOS: brew install redis && brew services start redis
# Ubuntu: sudo apt install redis-server && sudo systemctl start redis
```

### 5. Start the Server

```bash
# Development mode with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. Verify Installation

```bash
# Check health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","service":"cerberus","version":"1.0.0"}

# Detailed health check
curl http://localhost:8000/health/detailed
```

---

## Initial Setup

### 1. Create a Tenant

```bash
curl -X POST http://localhost:8000/control-plane/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "subscription_tier": "enterprise",
    "admin_email": "admin@acme.com",
    "admin_password": "securepassword123"
  }'
```

This creates:
- A tenant with the specified name
- An admin user with `tenant_admin` role
- Initial login credentials

### 2. Login as Admin

```bash
curl -X POST http://localhost:8000/control-plane/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@acme.com",
    "password": "securepassword123",
    "tenant_slug": "acme-corp"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

Save the `access_token` for subsequent requests.

### 3. Create a Workspace

```bash
curl -X POST http://localhost:8000/control-plane/api/v1/workspaces \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "<tenant_id>",
    "name": "Production",
    "slug": "production",
    "environment_type": "production",
    "mcp_server_url": "https://your-mcp-server.com/v1"
  }'
```

**Important:** The `mcp_server_url` is the upstream MCP server that Cerberus will proxy requests to.

### 4. Create an MCP User

```bash
curl -X POST http://localhost:8000/control-plane/api/v1/users \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "<tenant_id>",
    "external_id": "jane.developer",
    "email": "jane@acme.com",
    "display_name": "Jane Developer",
    "role": "developer",
    "password": null,
    "workspace_ids": ["<workspace_id>"]
  }'
```

**Note:** `password: null` creates an MCP-only user who authenticates via access keys.

### 5. Generate an Access Key

```bash
curl -X POST http://localhost:8000/control-plane/api/v1/user-access-keys \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<user_id>",
    "workspace_id": "<workspace_id>",
    "name": "Development Key",
    "scopes": ["decisions:*"],
    "expires_at": "2025-12-31T23:59:59Z"
  }'
```

**Response (save the key!):**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440005",
  "key": "uak_A7xK2mB9cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV2wX3yZ4",
  "user_id": "<user_id>",
  "workspace_id": "<workspace_id>",
  "name": "Development Key"
}
```

**Warning:** The `key` is only shown once! Store it securely.

### 6. Create a Policy

```bash
curl -X POST http://localhost:8000/control-plane/api/v1/policies \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "<tenant_id>",
    "workspace_id": null,
    "user_id": null,
    "name": "Security Baseline",
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
              "allow": ["*"],
              "deny": ["admin/*"]
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
        "action": "redact"
      },
      "secrets_detection": {
        "enabled": true,
        "action": "block"
      }
    }
  }'
```

---

## Using the Proxy

Once setup is complete, MCP clients can send requests through Cerberus:

### Basic Request

```bash
curl -X POST http://localhost:8000/governance-plane/api/v1/proxy/v1/tools/call \
  -H "Authorization: Bearer uak_A7xK2mB9cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV2wX3yZ4" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "read_file",
      "arguments": {
        "path": "/workspace/data.txt"
      }
    }
  }'
```

### Response (Allowed)

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

### Response (Blocked)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32001,
    "message": "Request blocked by governance policy",
    "data": {
      "decision_id": "dec_abc123",
      "action": "block_request",
      "guardrails_triggered": ["rbac"]
    }
  }
}
```

---

## Configuring MCP Clients

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "my-server": {
      "url": "http://localhost:8000/governance-plane/api/v1/proxy",
      "headers": {
        "Authorization": "Bearer uak_your_access_key_here"
      }
    }
  }
}
```

### Cursor

Configure in Cursor settings with the proxy URL and access key.

### Custom Client

```python
import httpx

client = httpx.AsyncClient(
    base_url="http://localhost:8000/governance-plane/api/v1/proxy",
    headers={
        "Authorization": "Bearer uak_your_access_key_here",
        "Content-Type": "application/json"
    }
)

response = await client.post("/v1/tools/call", json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "read_file",
        "arguments": {"path": "/data.txt"}
    }
})
```

---

## Using pgAdmin

pgAdmin is included in the Docker setup for database management and visualization.

### Accessing pgAdmin

1. Start the Docker services if not already running:
   ```bash
   cd docker
   docker-compose up -d
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5050
   ```

3. Login with the default credentials:
   - **Email:** `admin@local.dev`
   - **Password:** `admin`

### Registering the Database Server

After logging into pgAdmin, you need to register the PostgreSQL server:

1. Right-click on **Servers** in the left panel
2. Select **Register** → **Server...**
3. In the **General** tab:
   - **Name:** `Cerberus Local` (or any name you prefer)
4. In the **Connection** tab:
   - **Host name/address:** `db`
   - **Port:** `5432`
   - **Maintenance database:** `cerberus`
   - **Username:** `postgres`
   - **Password:** `postgres`
   - Check **Save password** to avoid re-entering it
5. Click **Save**

You should now see the Cerberus database under **Servers** → **Cerberus Local** → **Databases** → **cerberus**.

### Common pgAdmin Tasks

**View Tables:**
Navigate to **Servers** → **Cerberus Local** → **Databases** → **cerberus** → **Schemas** → **public** → **Tables**

**Run SQL Queries:**
Right-click on the database and select **Query Tool**, or use the keyboard shortcut `Alt+Shift+Q`

**View Table Data:**
Right-click on any table → **View/Edit Data** → **All Rows**

---

## Development

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app

# Specific test file
pytest tests/test_proxy.py

# Watch mode
pytest-watch
```

### Code Formatting

```bash
# Format code
black app tests

# Sort imports
isort app tests

# Type checking
mypy app
```

### Database Migrations

See [Migrations Guide](./migrations.md) for complete details on:
- Creating and applying migrations
- Local development workflow (Docker and non-Docker)
- Staging/Production migrations (AWS App Runner + Aurora)

---

## Common Issues

### Database Connection Error

```
sqlalchemy.exc.OperationalError: connection refused
```

**Solution:** Ensure PostgreSQL is running and the `DATABASE_URL` is correct.

### Redis Connection Error

```
redis.exceptions.ConnectionError: Error connecting to localhost:6379
```

**Solution:** Ensure Redis is running and the `REDIS_URL` is correct.

### Invalid Access Key

```json
{"detail": "Invalid or expired access key"}
```

**Solution:**
- Verify the key is correct (check for typos)
- Ensure the key is not expired or revoked
- Confirm the key has appropriate scopes

### Rate Limited

```json
{"error": {"code": -32001, "message": "Rate limit exceeded"}}
```

**Solution:**
- Wait for the rate limit window to reset
- Adjust rate limits in the policy if appropriate

---

## Next Steps

- [Architecture](./architecture.md) - Understand the system design
- [API Reference](./api-reference.md) - Complete API documentation
- [Guardrails](./guardrails.md) - Configure security policies
- [Authentication](./authentication.md) - Learn about auth flows
- [Deployment](./deployment.md) - Production deployment guide
