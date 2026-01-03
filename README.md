# Cerberus - MCP Governance Gateway

<p align="center">
  <strong>Enterprise-grade governance layer for the Model Context Protocol (MCP)</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-0.109-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-15-blue.svg" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Terraform-1.0+-purple.svg" alt="Terraform">
  <img src="https://img.shields.io/badge/AWS-App%20Runner-orange.svg" alt="AWS">
</p>

---

## Overview

**Cerberus** is a unified governance service that acts as a security gateway between AI clients (Claude Desktop, Cursor, VS Code, etc.) and MCP servers. It provides policy-based access control, PII protection, rate limiting, and comprehensive audit logging for AI tool usage in enterprise environments.

### The Problem

As organizations adopt AI assistants that connect to internal tools via MCP, they face critical governance challenges:
- **No visibility** into what tools AI agents are accessing
- **No control** over sensitive data exposure (PII, credentials, proprietary code)
- **No audit trail** for compliance and security investigations
- **No rate limiting** to prevent abuse or runaway costs

### The Solution

Cerberus sits as a transparent proxy between AI clients and MCP servers, enabling:

```
AI Client (Claude, Cursor, etc.)
         │
         ▼
┌─────────────────────────────────────┐
│         CERBERUS GATEWAY            │
│  ┌─────────────────────────────┐    │
│  │   Policy Evaluation Engine  │    │
│  │   • RBAC (tool access)      │    │
│  │   • PII Detection/Redaction │    │
│  │   • Rate Limiting           │    │
│  │   • Content Filtering       │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │     Audit & Analytics       │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
         │
         ▼
    MCP Server (Your Internal Tools)
```

---

## Key Features

### Security & Governance

| Feature | Description |
|---------|-------------|
| **Role-Based Access Control** | Define which tools each agent can access using allow/deny lists with wildcard patterns |
| **PII Detection** | Automatically detect and block/redact SSN, credit cards, emails, phone numbers, IP addresses |
| **Rate Limiting** | Redis-backed sliding window rate limiting per minute/hour with configurable quotas |
| **Content Filtering** | Block oversized documents, structured data dumps, and large code blocks |
| **Audit Logging** | Complete audit trail of every request/response with guardrail decisions |

### Multi-Tenancy & Scale

| Feature | Description |
|---------|-------------|
| **Organisation Isolation** | Complete data isolation between customer organisations |
| **Workspace Environments** | Separate policies for production, staging, and development |
| **Hierarchical Policies** | Organisation → Workspace → Agent policy inheritance with overrides |
| **Async Architecture** | Built on asyncio for high concurrency with connection pooling |

### Enterprise Ready

| Feature | Description |
|---------|-------------|
| **Infrastructure as Code** | Complete Terraform modules for AWS deployment |
| **Auto-Scaling** | AWS App Runner with 1-5 instance auto-scaling |
| **Serverless Database** | Aurora Serverless v2 with scale-to-zero for cost efficiency |
| **Health Monitoring** | Health endpoints, CloudWatch integration, budget alerts |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              CERBERUS ARCHITECTURE                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                         GOVERNANCE PLANE (Proxy)                           │  │
│  │                                                                            │  │
│  │   Request ──► Key Validation ──► Guardrail Pipeline ──► Forward to MCP    │  │
│  │                                        │                                   │  │
│  │                                        ▼                                   │  │
│  │                              ┌─────────────────┐                           │  │
│  │                              │   Guardrails    │                           │  │
│  │                              │  • RBAC         │                           │  │
│  │                              │  • PII          │                           │  │
│  │                              │  • Rate Limit   │                           │  │
│  │                              │  • Content      │                           │  │
│  │                              └─────────────────┘                           │  │
│  │                                        │                                   │  │
│  │   Response ◄─ Guardrail Pipeline ◄────┘                                    │  │
│  │                                                                            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                         CONTROL PLANE (Admin APIs)                         │  │
│  │                                                                            │  │
│  │   • Organisations           • Agent Access Keys        • Audit Logs        │  │
│  │   • MCP Server Workspaces   • Policies & Guardrails    • Analytics         │  │
│  │   • Users & Roles           • JWT Authentication                           │  │
│  │                                                                            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐             │
│  │    PostgreSQL (Aurora)      │    │    Redis (Valkey/Cache)     │             │
│  │    • Multi-tenant data      │    │    • Rate limit counters    │             │
│  │    • Audit logs             │    │    • Policy cache           │             │
│  │    • Async with asyncpg     │    │    • Session storage        │             │
│  └─────────────────────────────┘    └─────────────────────────────┘             │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend
- **Framework:** FastAPI 0.109 with Pydantic v2 for validation
- **Database:** PostgreSQL 15 with SQLAlchemy 2.0 async ORM
- **Cache:** Redis/Valkey for rate limiting and caching
- **Migrations:** Alembic with PostgreSQL advisory locks for safe cluster deploys

### Infrastructure
- **Compute:** AWS App Runner (auto-scaling containers)
- **Database:** Aurora Serverless v2 (scale-to-zero capability)
- **Cache:** ElastiCache Valkey
- **IaC:** Terraform with modular architecture
- **Containers:** Multi-stage Docker builds

### Development
- **Testing:** pytest with pytest-asyncio, integration test suite
- **Quality:** Black, Ruff, mypy with strict configuration
- **CI/CD:** GitHub Actions ready

---

## Project Structure

```
cerberus/
├── app/
│   ├── control_plane/          # Admin REST APIs
│   │   ├── api/v1/             # Versioned endpoints
│   │   └── services/           # Business logic
│   │
│   ├── governance_plane/       # Proxy & policy engine
│   │   ├── proxy/              # MCP proxy service
│   │   ├── engine/             # Decision engine
│   │   ├── guardrails/         # Guardrail implementations
│   │   │   ├── rbac/           # Role-based access control
│   │   │   ├── pii/            # PII detection (SSN, CC, etc.)
│   │   │   ├── rate_limit/     # Redis-backed rate limiting
│   │   │   └── content/        # Content size filtering
│   │   └── events/             # Audit event system
│   │
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── db/                     # Database layer
│   │   └── repositories/       # Repository pattern
│   ├── cache/                  # Redis client & caching
│   ├── config/                 # Settings & constants
│   └── core/                   # Security, exceptions, utils
│
├── infra/                      # Terraform infrastructure
│   ├── modules/
│   │   ├── aurora/             # Aurora Serverless v2
│   │   ├── valkey/             # ElastiCache
│   │   ├── apprunner/          # App Runner service
│   │   └── ecr/                # Container registry
│   └── environments/
│       ├── stage/
│       └── prod/
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── docs/                       # Comprehensive documentation
└── docker/                     # Containerization
```

---

## Guardrails

### Available Guardrail Types

| Category | Type | Direction | Action | Description |
|----------|------|-----------|--------|-------------|
| **RBAC** | `rbac` | Request | Block | Tool access control with allow/deny lists |
| **PII** | `pii_ssn` | Both | Block | Social Security Numbers (validated format) |
| **PII** | `pii_credit_card` | Both | Block | Credit/debit cards (Luhn algorithm validated) |
| **PII** | `pii_email` | Both | Redact | Email addresses |
| **PII** | `pii_phone` | Both | Redact | Phone numbers |
| **PII** | `pii_ip_address` | Both | Redact | IPv4 addresses |
| **Rate Limit** | `rate_limit_per_minute` | Request | Throttle | Requests per minute quota |
| **Rate Limit** | `rate_limit_per_hour` | Request | Throttle | Requests per hour quota |
| **Content** | `content_large_documents` | Both | Block | Document size limits |
| **Content** | `content_structured_data` | Both | Block | Table/CSV row limits |
| **Content** | `content_source_code` | Both | Block | Code block size limits |

### Guardrail Pipeline Flow

```
Request/Response
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│                    GUARDRAIL PIPELINE                       │
│                                                             │
│   ┌──────┐   ┌────────────┐   ┌─────┐   ┌─────────┐        │
│   │ RBAC │──►│ Rate Limit │──►│ PII │──►│ Content │──► ... │
│   └──────┘   └────────────┘   └─────┘   └─────────┘        │
│       │            │             │            │             │
│       ▼            ▼             ▼            ▼             │
│    [BLOCK]     [THROTTLE]    [MODIFY]     [ALLOW]          │
│                                                             │
│   Pipeline short-circuits on BLOCK                          │
│   MODIFY actions transform content and continue             │
│   ALLOW passes through to next guardrail                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
Forward/Return (if allowed)
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15 (or use Docker)
- Redis 7 (or use Docker)

### Local Development

```bash
# Clone and setup
cd cerberus
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start dependencies
docker compose up -d postgres redis

# Configure environment
cp env.example .env
# Edit .env with your settings

# Run migrations
alembic upgrade head

# Seed database (optional)
python scripts/seed_db.py

# Start server
uvicorn app.main:app --reload --port 8000
```

### Using Docker

```bash
cd cerberus/docker
docker compose up -d

# Application available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

---

## API Overview

### Control Plane (Admin)

```
Authentication:
  POST /api/v1/auth/login                    # Get JWT token
  POST /api/v1/auth/refresh                  # Refresh token

Organisations:
  GET  /api/v1/organisations                 # List organisations
  POST /api/v1/organisations                 # Create organisation
  GET  /api/v1/organisations/{id}            # Get organisation

MCP Server Workspaces:
  GET  /api/v1/organisations/{id}/mcp-server-workspaces
  POST /api/v1/organisations/{id}/mcp-server-workspaces

Agent Access Keys:
  GET  /api/v1/mcp-server-workspaces/{id}/agent-accesses
  POST /api/v1/mcp-server-workspaces/{id}/agent-accesses
  POST /api/v1/agent-accesses/{id}/rotate    # Rotate key

Policies:
  GET  /api/v1/policies/mcp-server-workspaces/{id}/effective-policies
  POST /api/v1/policies                      # Create policy

Audit & Analytics:
  GET  /api/v1/organisations/{id}/audit-logs
  GET  /api/v1/organisations/{id}/analytics
```

### Governance Plane (Proxy)

```
MCP Proxy:
  POST /governance-plane/api/v1/proxy/mcp    # Proxy MCP request

  Headers:
    Authorization: Bearer <agent-access-key>
```

---

## Deployment

### AWS Architecture

```
Internet
    │
    ▼
AWS App Runner (auto-scaling 1-5 instances)
    │ VPC Connector
    ├──► Aurora Serverless v2 PostgreSQL
    └──► ElastiCache Valkey (Redis)

Supporting:
    • ECR (container images)
    • S3 (Terraform state)
    • CloudWatch (logs)
    • Budget Alerts
```

### Deploy with Terraform

```bash
# 1. Bootstrap state backend (one-time)
cd infra/bootstrap
terraform init && terraform apply

# 2. Configure environment
cd ../environments/stage
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

# 3. Deploy
terraform init
terraform apply
```

### Cost Estimates

| Environment | Idle | Active |
|-------------|------|--------|
| **Staging** | ~$15/month | ~$20/month |
| **Production** | ~$35/month | ~$70/month |

*Aurora Serverless v2 scales to zero, App Runner scales 1-5 instances*

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](cerberus/docs/architecture.md) | System design and request flows |
| [Getting Started](cerberus/docs/getting-started.md) | Local development setup |
| [API Reference](cerberus/docs/api-reference.md) | Complete API documentation |
| [Authentication](cerberus/docs/authentication.md) | JWT and API key flows |
| [Guardrails](cerberus/docs/guardrails.md) | Guardrail configuration |
| [Deployment](cerberus/docs/deployment.md) | Production deployment guide |
| [Migrations](cerberus/docs/migrations.md) | Database migration guide |

---

## Technical Highlights

### Async-First Architecture
- Built entirely on `asyncio` for high concurrency
- `asyncpg` for non-blocking database operations
- `httpx` async HTTP client for MCP proxy
- Connection pooling for both database and Redis

### Type Safety
- Strict `mypy` configuration
- Pydantic v2 for runtime validation
- SQLAlchemy 2.0 with full type hints
- No `Any` types in business logic

### Security
- Passwords hashed with bcrypt
- API keys stored as SHA-256 hashes
- JWT with configurable expiration
- PII detection with Luhn validation for credit cards

### Database Design
- Soft deletes with `deleted_at` timestamp
- Unique constraints with soft-delete awareness
- Advisory locks for safe migrations in clusters
- Composite indexes for common query patterns

### Extensible Guardrails
```python
# Adding a new guardrail is simple:
class CustomGuardrail(BaseGuardrail):
    guardrail_type = "custom_check"

    async def evaluate(
        self,
        context: GuardrailContext
    ) -> GuardrailResult:
        # Your logic here
        return GuardrailResult(action=Action.ALLOW)
```

---

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit -v

# Integration tests (requires database)
pytest tests/integration -v

# With coverage
pytest --cov=app tests/
```

### Code Quality

```bash
# Format
black app tests

# Lint
ruff check app tests

# Type check
mypy app
```

---

## License

This project is for portfolio demonstration purposes.

---

## Author

Built as a demonstration of enterprise software architecture, security best practices, and production-grade Python development.

**Skills Demonstrated:**
- Async Python with FastAPI
- Multi-tenant SaaS architecture
- Security (RBAC, PII detection, rate limiting)
- Infrastructure as Code with Terraform
- Database design with PostgreSQL
- Caching strategies with Redis
- Test-driven development
- Clean code and documentation
