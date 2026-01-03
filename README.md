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

| Category | Features |
|----------|----------|
| **Security** | RBAC with wildcard patterns, PII detection (SSN, credit cards, emails, phones), content filtering |
| **Rate Limiting** | Redis-backed sliding window limits per minute/hour |
| **Multi-Tenancy** | Organisation isolation, workspace environments, hierarchical policies |
| **Audit** | Complete request/response logging with guardrail decisions |
| **Infrastructure** | Terraform IaC, AWS App Runner auto-scaling, Aurora Serverless v2 |

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI 0.109, Pydantic v2, SQLAlchemy 2.0 async, Alembic |
| **Database** | PostgreSQL 15 (Aurora Serverless v2), Redis/Valkey |
| **Infrastructure** | Terraform, AWS App Runner, ECR, ElastiCache |
| **Quality** | pytest, Black, Ruff, mypy (strict) |

---

## Architecture

### High-Level System Design

```
                                    ┌─────────────────────────────────────┐
                                    │         AI CLIENTS                  │
                                    │  Claude Desktop • Cursor • VS Code  │
                                    └─────────────────┬───────────────────┘
                                                      │
                                                      │ MCP Requests
                                                      │ Authorization: Bearer <agent-key>
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CERBERUS GATEWAY                                     │
│                                                                                         │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              GOVERNANCE PLANE                                      │ │
│  │                                                                                    │ │
│  │   ┌──────────────┐    ┌──────────────────────────────────────────-┐    ┌─────────┐ │ │
│  │   │    ACCESS    │    │           GUARDRAIL PIPELINE              │    │ FORWARD │ │ │
│  │   │     KEY      │───►│                                           │───►│   TO    │ │ │
│  │   │  VALIDATION  │    │  ┌──────┐ ┌────────┐ ┌─────┐ ┌─────────┐  │    │UPSTREAM │ │ │
│  │   │              │    │  │ RBAC │►│  RATE  │►│ PII │►│ CONTENT │  │    │         │ │ │
│  │   │ • SHA-256    │    │  │      │ │ LIMIT  │ │     │ │ FILTER  │  │    │ • Retry │ │ │
│  │   │   lookup     │    │  └──────┘ └────────┘ └─────┘ └─────────┘  │    │ • Pool  │ │ │
│  │   │ • Derive     │    │       │        │        │         │       │    │         │ │ │
│  │   │   context    │    │       ▼        ▼        ▼         ▼       │    └─────────┘ │ │
│  │   └──────────────┘    │    [BLOCK] [THROTTLE] [REDACT] [ALLOW]    │                │ │
│  │                        └──────────────────────────────────────────┘                │ │
│  │                                         │                                          │ │
│  │   ┌─────────────────────────────────────┼────────────────────────────────────────-┐│ │
│  │   │                           RESPONSE EVALUATION                                 ││ │
│  │   │                     (Same pipeline for MCP responses)                         ││ │
│  │   └───────────────────────────────────────────────────────────────────────────────┘│ │
│  └───────────────────────────────────────────────────────────────────────────────────-┘ │
│                                                                                         │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                               CONTROL PLANE                                        │ │
│  │                                                                                    │ │
│  │   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │ │
│  │   │Organisation │ │  Workspace  │ │Agent Access │ │   Policy    │ │    Audit    │  │ │
│  │   │ Management  │ │ Management  │ │ Key Mgmt    │ │ Management  │ │   Logging   │  │ │
│  │   │             │ │             │ │             │ │             │ │             │  │ │
│  │   │ • Multi-    │ │ • prod/stg/ │ │ • Generate  │ │ • CRUD      │ │ • Request/  │  │ │
│  │   │   tenant    │ │   dev envs  │ │ • Rotate    │ │ • Hierarchy │ │   Response  │  │ │
│  │   │ • Isolation │ │ • MCP URLs  │ │ • Revoke    │ │ • Merge     │ │ • Decisions │  │ │
│  │   └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                 DATA LAYER                                         │ │
│  │                                                                                    │ │
│  │   ┌─────────────────────────────────┐    ┌─────────────────────────────────┐       │ │
│  │   │      PostgreSQL (Aurora)        │    │        Redis (Valkey)           │       │ │
│  │   │                                 │    │                                 │       │ │
│  │   │  • Organisations & Workspaces   │    │  • Rate limit counters          │       │ │
│  │   │  • Users & Agent Access Keys    │    │  • Policy cache                 │       │ │
│  │   │  • Policies & Guardrails        │    │  • Session storage              │       │ │
│  │   │  • Audit Logs                   │    │  • Sliding window state         │       │ │
│  │   │                                 │    │                                 │       │ │
│  │   │  SQLAlchemy 2.0 + asyncpg       │    │  aioredis connection pool       │       │ │
│  │   └─────────────────────────────────┘    └─────────────────────────────────┘       │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                                      │
                                                      │ Governed Request
                                                      ▼
                                    ┌─────────────────────────────────────┐
                                    │         MCP SERVERS                 │
                                    │   Database • Filesystem • APIs      │
                                    └─────────────────────────────────────┘
```

### Request Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────-┐
│                                    REQUEST LIFECYCLE                                     │
├─────────────────────────────────────────────────────────────────────────────────────────-┤
│                                                                                          │
│  1. KEY VALIDATION              2. REQUEST GUARDRAILS         3. UPSTREAM FORWARD        │
│  ─────────────────              ────────────────────          ──────────────────         │
│  │                              │                              │                         │
│  │  Authorization: Bearer xxx   │  Load effective policy       │  Forward to MCP server  │
│  │         │                    │  (org → workspace → agent)   │         │               │
│  │         ▼                    │         │                    │         ▼               │
│  │  SHA-256 hash lookup         │         ▼                    │  Connection pooling     │
│  │         │                    │  Execute pipeline:           │  Retry with backoff     │
│  │         ▼                    │  RBAC → Rate → PII → Content │  Timeout handling       │
│  │  Derive context:             │         │                    │                         │
│  │  • organisation_id           │         ▼                    │                         │
│  │  • workspace_id              │  BLOCK ──► 403 Response      │                         │
│  │  • mcp_server_url            │  ALLOW ──► Continue ─────────┼──►                      │
│  │                              │  MODIFY ─► Transform & Go    │                         │
│  │                              │                              │                         │
│  └──────────────────────────────┴──────────────────────────────┴─────────────────────────│
│                                                                                          │
│  4. RESPONSE GUARDRAILS         5. AUDIT & RETURN                                        │
│  ──────────────────────         ─────────────────                                        │
│  │                              │                                                        │
│  │  Same pipeline on response   │  Async audit log write                                 │
│  │         │                    │         │                                              │
│  │         ▼                    │         ▼                                              │
│  │  PII Detection → Redaction   │  Return to client with:                                │
│  │  Secrets → Block             │  • X-Request-ID                                        │
│  │  Content → Filter            │  • X-Decision-ID                                       │
│  │                              │  • Guardrail metadata                                  │
│  │                              │                                                        │
│  └──────────────────────────────┴────────────────────────────────────────────────────────│
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────-┐ │
│  │                              PERFORMANCE TARGETS                                    │ │
│  │   Key Validation: <5ms  │  Policy Load: <5ms  │  Guardrails: <20ms  │  Total: <30ms │ │
│  └────────────────────────────────────────────────────────────────────────────────────-┘ │
└────────────────────────────────────────────────────────────────────────────────────────-─┘
```

### Multi-Tenant Data Model

```
┌─────────────────────────────────────────────────────────────────────────────────────────-┐
│                                    DATA MODEL                                            │
├─────────────────────────────────────────────────────────────────────────────────────────-┤
│                                                                                          │
│                              ┌─────────────────────┐                                     │
│                              │    ORGANISATION     │                                     │
│                              │    (Tenant Root)    │                                     │
│                              ├─────────────────────┤                                     │
│                              │ • name, slug        │                                     │
│                              │ • subscription_tier │                                     │
│                              │ • settings (JSON)   │                                     │
│                              │ • is_active         │                                     │
│                              └──────────┬──────────┘                                     │
│                                         │                                                │
│           ┌─────────────────────────────┼─────────────────────────────┐                  │
│           │                             │                             │                  │
│           ▼                             ▼                             ▼                  │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐           │ 
│  │   MCP WORKSPACE     │    │        USER         │    │       POLICY        │           │
│  │   (Environment)     │    │   (Dashboard Only)  │    │   (Org-Level)       │           │
│  ├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤           │
│  │ • name, slug        │    │ • email             │    │ • guardrail_id      │           │
│  │ • environment_type  │    │ • password_hash     │    │ • action            │           │
│  │ • mcp_server_url    │    │ • role (admin/view) │    │ • config (JSON)     │           │
│  │ • settings (JSON)   │    │ • is_active         │    │ • priority          │           │
│  └──────────┬──────────┘    └─────────────────────┘    └─────────────────────┘           │
│             │                                                                            │
│             ├──────────────────────────────────┐                                         │
│             │                                  │                                         │
│             ▼                                  ▼                                         │
│  ┌─────────────────────┐            ┌─────────────────────┐                              │
│  │    AGENT ACCESS     │            │       POLICY        │                              │
│  │   (MCP Auth Key)    │            │  (Workspace-Level)  │                              │
│  ├─────────────────────┤            ├─────────────────────┤                              │
│  │ • name, description │            │ (Overrides org)     │                              │
│  │ • key_hash (SHA256) │            └──────────┬──────────┘                              │
│  │ • key_prefix        │                       │                                         │
│  │ • is_active         │                       ▼                                         │
│  │ • expires_at        │            ┌─────────────────────┐                              │
│  │ • last_used_at      │            │       POLICY        │                              │
│  │ • usage_count       │            │   (Agent-Level)     │                              │
│  └──────────┬──────────┘            ├─────────────────────┤                              │
│             │                       │ (Overrides both)    │                              │
│             │                       └─────────────────────┘                              │
│             │                                                                            │
│             │              POLICY RESOLUTION: Org → Workspace → Agent                    │
│             │              (Higher specificity wins)                                     │
│             │                                                                            │
│             ▼                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐             │
│  │                              AUDIT LOG                                  │             │
│  ├─────────────────────────────────────────────────────────────────────────┤             │
│  │ • request_id, decision_id    • action (allow/block/modify)              │             │
│  │ • organisation_id            • guardrail_events (JSON)                  │             │
│  │ • workspace_id               • processing_time_ms                       │             │
│  │ • agent_access_id            • timestamp                                │             │
│  └─────────────────────────────────────────────────────────────────────────┘             │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────-┘
```

### AWS Production Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              AWS PRODUCTION DEPLOYMENT                                  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   Internet                                                                              │
│       │                                                                                 │
│       ▼                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐           │
│   │                         AWS APP RUNNER                                  │           │
│   │                                                                         │           │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                     │           │
│   │   │  Instance   │  │  Instance   │  │  Instance   │   Auto-scaling      │           │
│   │   │   (256MB)   │  │   (256MB)   │  │   (256MB)   │   1-5 instances     │           │
│   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                     │           │
│   │          └─────────────────┼─────────────────┘                          │           │
│   │                            │                                            │           │
│   │   Built-in: HTTPS • Load Balancing • Health Checks • Zero-downtime      │           │
│   └────────────────────────────┼────────────────────────────────────────────┘           │
│                                │                                                        │
│                    VPC Connector (Private Subnets)                                      │
│   ┌────────────────────────────┼────────────────────────────────────────────┐           │
│   │                            │                          DEFAULT VPC       │           │
│   │           ┌────────────────┴────────────────┐                           │           │
│   │           │                                 │                           │           │
│   │           ▼                                 ▼                           │           │
│   │   ┌─────────────────────┐       ┌─────────────────────┐                 │           │
│   │   │  Aurora Serverless  │       │  ElastiCache Valkey │                 │           │
│   │   │   v2 PostgreSQL     │       │     (Redis)         │                 │           │
│   │   │                     │       │                     │                 │           │
│   │   │  • 0-8 ACU scaling  │       │  • t4g.micro/small  │                 │           │
│   │   │  • Scale-to-zero    │       │  • Rate limiting    │                 │           │
│   │   │  • Auto-pause       │       │  • Policy cache     │                 │           │
│   │   │  • 7-day backups    │       │                     │                 │           │
│   │   └─────────────────────┘       └─────────────────────┘                 │           │
│   └─────────────────────────────────────────────────────────────────────────┘           │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────-┐          │
│   │                          SUPPORTING SERVICES                             │          │
│   │                                                                          │          │
│   │   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐             │          │
│   │   │    ECR    │  │ S3 Bucket │  │ DynamoDB  │  │  Budget   │             │          │
│   │   │ (Images)  │  │ (TF State)│  │ (TF Lock) │  │ (Alerts)  │             │          │
│   │   └───────────┘  └───────────┘  └───────────┘  └───────────┘             │          │
│   │                                                                          │          │
│   │   Terraform IaC  •  Multi-stage Docker  •  GitHub Actions Ready          │          │
│   └─────────────────────────────────────────────────────────────────────────-┘          │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

> **Deep Dive:** See [Architecture Documentation](cerberus/docs/architecture.md) for detailed component interactions and request flows.

---

## Project Structure

```
cerberus/
├── app/
│   ├── control_plane/          # Admin REST APIs
│   │   ├── api/v1/             # Versioned endpoints
│   │   └── services/           # Business logic
│   ├── governance_plane/       # Proxy & policy engine
│   │   ├── proxy/              # MCP proxy service
│   │   ├── engine/             # Decision engine
│   │   └── guardrails/         # RBAC, PII, rate limit, content
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── db/repositories/        # Repository pattern
│   └── core/                   # Security, exceptions, utils
├── infra/                      # Terraform modules
│   ├── modules/                # aurora, valkey, apprunner, ecr
│   └── environments/           # stage, prod
├── tests/                      # Unit & integration tests
├── docs/                       # Comprehensive documentation
└── docker/                     # Containerization
```

---

## Quick Start

```bash
# Clone and setup
cd cerberus
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Start dependencies
docker compose up -d postgres redis

# Configure and run
cp env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

> **Full Guide:** See [Getting Started](cerberus/docs/getting-started.md) for detailed setup instructions.

---

## Guardrails

| Category | Type | Action | Description |
|----------|------|--------|-------------|
| **RBAC** | `rbac` | Block | Tool access control with allow/deny lists |
| **PII** | `pii_ssn`, `pii_credit_card` | Block | SSN and credit cards (Luhn validated) |
| **PII** | `pii_email`, `pii_phone`, `pii_ip_address` | Redact | Contact info redaction |
| **Rate Limit** | `rate_limit_per_minute/hour` | Throttle | Configurable quotas |
| **Content** | `content_large_documents`, `content_source_code` | Block | Size limits |

> **Configuration:** See [Guardrails Documentation](cerberus/docs/guardrails.md) for configuration details.

---

## Deployment

```
AWS App Runner (auto-scaling 1-5 instances)
    │ VPC Connector
    ├──► Aurora Serverless v2 PostgreSQL
    └──► ElastiCache Valkey (Redis)
```

| Environment | Idle Cost | Active Cost |
|-------------|-----------|-------------|
| **Staging** | ~$15/month | ~$20/month |
| **Production** | ~$35/month | ~$70/month |

> **Full Guide:** See [Deployment Documentation](cerberus/docs/deployment.md) for Terraform deployment instructions.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](cerberus/docs/architecture.md) | System design, data flow, component interactions |
| [Getting Started](cerberus/docs/getting-started.md) | Local development setup |
| [API Reference](cerberus/docs/api-reference.md) | Complete endpoint documentation |
| [Authentication](cerberus/docs/authentication.md) | JWT and API key authentication flows |
| [Guardrails](cerberus/docs/guardrails.md) | Guardrail types and configuration |
| [Deployment](cerberus/docs/deployment.md) | AWS deployment with Terraform |
| [Migrations](cerberus/docs/migrations.md) | Database migration workflows |

---

## Technical Highlights

| Aspect | Implementation |
|--------|----------------|
| **Async Architecture** | Built on `asyncio` with `asyncpg` and `httpx` for high concurrency |
| **Type Safety** | Strict `mypy`, Pydantic v2, SQLAlchemy 2.0 type hints |
| **Security** | Bcrypt passwords, SHA-256 API key hashes, Luhn-validated PII detection |
| **Database Design** | Soft deletes, advisory locks for migrations, composite indexes |
| **Extensibility** | Plugin-based guardrail system with simple base class |

---

## Development

```bash
# Tests
pytest tests/unit -v
pytest tests/integration -v

# Quality
black app tests && ruff check app tests && mypy app
```

---

## Skills Demonstrated

- **Backend:** Async Python, FastAPI, SQLAlchemy 2.0, Pydantic
- **Architecture:** Multi-tenant SaaS, Repository pattern, Event-driven audit
- **Security:** RBAC, PII detection, Rate limiting, JWT/API key auth
- **Infrastructure:** Terraform, AWS (App Runner, Aurora, ElastiCache)
- **Database:** PostgreSQL, Redis, Migration strategies
- **Quality:** Type safety, Testing, Documentation

---

## License

This project is for portfolio demonstration purposes.
