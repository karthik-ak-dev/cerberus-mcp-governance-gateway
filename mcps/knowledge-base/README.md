# Knowledge Base MCP Example

A complete example demonstrating how to build an MCP (Model Context Protocol) server and client, designed to test **Cerberus Governance Policies**.

## Project Structure

```
knowledge-base/
├── server/                 # MCP Server (backend for AI tools)
│   ├── main.py            # Entry point - starts HTTP or STDIO server
│   ├── tools.py           # Tool definitions (search, get, create articles)
│   ├── resources.py       # Resource definitions (articles as readable content)
│   ├── prompts.py         # Prompt templates (summarize, Q&A, compare)
│   └── data_store.py      # Data layer (manages articles in memory/JSON)
│
├── client/                 # MCP Client (demonstrates how to connect)
│   ├── main.py            # Entry point - interactive CLI client
│   └── handlers.py        # Handlers for server-to-client requests
│
├── data/                   # Sample data
│   └── articles.json      # Knowledge base articles (with test data for policies)
│
└── requirements.txt        # Python dependencies
```

---

# Testing Cerberus Governance with Knowledge Base MCP

This guide walks you through setting up and testing **all Cerberus governance policies** using the Knowledge Base MCP as a test platform.

## Architecture Overview

```
┌────────────────┐         ┌──────────────────────┐         ┌─────────────────┐
│  MCP Client    │ ──────► │  Cerberus Proxy      │ ──────► │  Knowledge Base │
│  (Python CLI)  │ ◄────── │  (Docker Container)  │ ◄────── │  MCP Server     │
└────────────────┘         └──────────┬───────────┘         └─────────────────┘
                                      │
                           ┌──────────┴───────────┐
                           │  Guardrail Policies  │
                           ├──────────────────────┤
                           │ • PII Detection      │
                           │   - pii_ssn          │
                           │   - pii_email        │
                           │   - pii_credit_card  │
                           │   - pii_phone        │
                           │   - pii_ip_address   │
                           │ • Content Filtering  │
                           │   - content_large_documents │
                           │ • RBAC               │
                           │ • Rate Limiting      │
                           │   - rate_limit_per_minute   │
                           └──────────────────────┘
```

---

## Prerequisites

- Docker and Docker Compose installed
- Python 3.10+ (for the MCP client/server)
- `curl` for API calls

---

## Authentication Overview

Cerberus uses **two types of authentication**:

| Type | Purpose | Header Format |
|------|---------|---------------|
| **JWT Token** | Dashboard/Admin API access | `Authorization: Bearer <jwt_token>` |
| **Agent Access Key** | MCP Governance Proxy access | `Authorization: Bearer <agent_key>` |

- **JWT Tokens**: Required for Control Plane APIs (creating orgs, workspaces, policies)
- **Agent Access Keys**: Required for Governance Plane Proxy (MCP requests)

---

## Complete Setup Flow

```
1. Start Cerberus (Docker)
   ↓
2. Seed Database (creates super admin user)
   ↓
3. Login to get JWT Token
   ↓
4. Create Guardrail Definitions (using JWT - SuperAdmin only)
   ↓
5. Create Organisation (using JWT - SuperAdmin only)
   ↓
6. Create MCP Server Workspace (using JWT)
   ↓
7. Create Agent Access Key (using JWT)
   ↓
8. Create Policies (attach guardrails to org/workspace/agent)
   ↓
9. Start MCP Server (Knowledge Base)
   ↓
10. Test Governance Policies (using Agent Access Key)
```

---

## Step 1: Start Cerberus (Docker)

```bash
cd cerberus/docker

# Start all services (Cerberus, PostgreSQL, Redis)
docker-compose up -d

# Verify services are running
docker-compose ps

# Check logs (optional)
docker-compose logs -f cerberus
```

**Services Started:**
| Service | Port | Description |
|---------|------|-------------|
| Cerberus API | 8000 | Control plane & governance proxy |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Rate limiting cache |
| pgAdmin | 5050 | Database admin UI (optional) |

---

## Step 2: Seed Database

The seed script creates initial users for authentication:
- Super admin user: `superadmin@cerberus.com` / `superadmin123`

```bash
# Run from cerberus directory (if using docker)
cd cerberus/docker
docker-compose exec cerberus python -m scripts.seed_db

# Or if running Cerberus locally:
cd cerberus
source .venv/bin/activate
python -m scripts.seed_db
```

**Note:** The seed script also creates demo guardrails and organisations. If you want a clean setup, you can skip seeding and create everything via API (but you'll need to create a super admin user first via database or another method).

---

## Steps 3-8: Complete Setup (Run in Same Terminal)

**IMPORTANT:** Run all these commands in the same terminal session to preserve variables.

```bash
# =============================================================================
# STEP 3: SET BASE URL AND LOGIN
# =============================================================================

BASE_URL="http://localhost:8000/control-plane/api/v1"

# Login as super admin (no organisation_slug needed)
echo "Logging in as super admin..."
curl -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "superadmin@cerberus.com",
    "password": "superadmin123"
  }' | tee /tmp/auth.json

# Extract JWT token and set AUTH_HEADER
JWT_TOKEN=$(cat /tmp/auth.json | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
AUTH_HEADER="Authorization: Bearer $JWT_TOKEN"
echo ""
echo "JWT Token obtained. AUTH_HEADER set."

# =============================================================================
# STEP 4: CREATE GUARDRAIL DEFINITIONS
# =============================================================================

echo ""
echo "Creating guardrail definitions..."

# Create PII - SSN Guardrail
curl -s -X POST "$BASE_URL/guardrails" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"guardrail_type": "pii_ssn", "category": "pii"}' | tee /tmp/guardrail-ssn.json
SSN_GUARDRAIL_ID=$(cat /tmp/guardrail-ssn.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "SSN Guardrail ID: $SSN_GUARDRAIL_ID"

# Create PII - Credit Card Guardrail
curl -s -X POST "$BASE_URL/guardrails" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"guardrail_type": "pii_credit_card", "category": "pii"}' | tee /tmp/guardrail-cc.json
CC_GUARDRAIL_ID=$(cat /tmp/guardrail-cc.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Credit Card Guardrail ID: $CC_GUARDRAIL_ID"

# Create PII - Email Guardrail
curl -s -X POST "$BASE_URL/guardrails" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"guardrail_type": "pii_email", "category": "pii"}' | tee /tmp/guardrail-email.json
EMAIL_GUARDRAIL_ID=$(cat /tmp/guardrail-email.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Email Guardrail ID: $EMAIL_GUARDRAIL_ID"

# Create PII - Phone Guardrail
curl -s -X POST "$BASE_URL/guardrails" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"guardrail_type": "pii_phone", "category": "pii"}' | tee /tmp/guardrail-phone.json
PHONE_GUARDRAIL_ID=$(cat /tmp/guardrail-phone.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Phone Guardrail ID: $PHONE_GUARDRAIL_ID"

# Create PII - IP Address Guardrail
curl -s -X POST "$BASE_URL/guardrails" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"guardrail_type": "pii_ip_address", "category": "pii"}' | tee /tmp/guardrail-ip.json
IP_GUARDRAIL_ID=$(cat /tmp/guardrail-ip.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "IP Address Guardrail ID: $IP_GUARDRAIL_ID"

# Create Rate Limit - Per Minute Guardrail
curl -s -X POST "$BASE_URL/guardrails" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"guardrail_type": "rate_limit_per_minute", "category": "rate_limit"}' | tee /tmp/guardrail-rate.json
RATE_GUARDRAIL_ID=$(cat /tmp/guardrail-rate.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Rate Limit Guardrail ID: $RATE_GUARDRAIL_ID"

# Create RBAC Guardrail
curl -s -X POST "$BASE_URL/guardrails" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"guardrail_type": "rbac", "category": "rbac"}' | tee /tmp/guardrail-rbac.json
RBAC_GUARDRAIL_ID=$(cat /tmp/guardrail-rbac.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "RBAC Guardrail ID: $RBAC_GUARDRAIL_ID"

# Create Content - Large Documents Guardrail
curl -s -X POST "$BASE_URL/guardrails" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"guardrail_type": "content_large_documents", "category": "content"}' | tee /tmp/guardrail-content.json
CONTENT_GUARDRAIL_ID=$(cat /tmp/guardrail-content.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Content Guardrail ID: $CONTENT_GUARDRAIL_ID"

echo ""
echo "All guardrails created."

# =============================================================================
# STEP 5: CREATE ORGANISATION
# =============================================================================

echo ""
echo "Creating organisation..."

curl -s -X POST "$BASE_URL/organisations" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Organisation",
    "subscription_tier": "default",
    "admin_email": "admin@test.com"
  }' | tee /tmp/org.json

ORG_ID=$(cat /tmp/org.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Organisation ID: $ORG_ID"

# =============================================================================
# STEP 6: CREATE MCP SERVER WORKSPACE
# =============================================================================

echo ""
echo "Creating MCP Server Workspace..."

# Note: host.docker.internal is Docker's special DNS name that allows
# containers to reach services on the host machine. Since Cerberus runs
# in Docker and the MCP server runs on your host at localhost:8080,
# we use host.docker.internal:8080 so Cerberus can forward requests to it.
curl -s -X POST "$BASE_URL/organisations/$ORG_ID/mcp-server-workspaces" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Knowledge Base Dev",
    "environment_type": "development",
    "mcp_server_url": "http://host.docker.internal:8080",
    "settings": {
      "fail_mode": "closed",
      "decision_timeout_ms": 5000,
      "log_level": "verbose"
    }
  }' | tee /tmp/workspace.json

WORKSPACE_ID=$(cat /tmp/workspace.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Workspace ID: $WORKSPACE_ID"

# =============================================================================
# STEP 7: CREATE AGENT ACCESS KEY
# =============================================================================

echo ""
echo "Creating Agent Access Key..."

curl -s -X POST "$BASE_URL/mcp-server-workspaces/$WORKSPACE_ID/agent-accesses" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Agent",
    "description": "Agent for testing governance policies"
  }' | tee /tmp/agent.json

ACCESS_KEY=$(cat /tmp/agent.json | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])")
AGENT_ID=$(cat /tmp/agent.json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo ""
echo "================================================"
echo "SAVE THESE VALUES (key only shown once!):"
echo "Agent ID: $AGENT_ID"
echo "Access Key: $ACCESS_KEY"
echo "================================================"

# =============================================================================
# STEP 8: CREATE POLICIES (ALL AT AGENT LEVEL)
# =============================================================================

echo ""
echo "Creating policies (all at agent level)..."

# PII Policy: Block SSN
curl -s -X POST "$BASE_URL/policies" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "organisation_id": "'"$ORG_ID"'",
    "mcp_server_workspace_id": "'"$WORKSPACE_ID"'",
    "agent_access_id": "'"$AGENT_ID"'",
    "guardrail_id": "'"$SSN_GUARDRAIL_ID"'",
    "name": "Block SSN",
    "action": "block",
    "config": {"direction": "both"}
  }' > /dev/null
echo "Created: Block SSN (pii_ssn)"

# PII Policy: Block Credit Cards
curl -s -X POST "$BASE_URL/policies" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "organisation_id": "'"$ORG_ID"'",
    "mcp_server_workspace_id": "'"$WORKSPACE_ID"'",
    "agent_access_id": "'"$AGENT_ID"'",
    "guardrail_id": "'"$CC_GUARDRAIL_ID"'",
    "name": "Block Credit Cards",
    "action": "block",
    "config": {"direction": "both"}
  }' > /dev/null
echo "Created: Block Credit Cards (pii_credit_card)"

# PII Policy: Redact Emails
curl -s -X POST "$BASE_URL/policies" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "organisation_id": "'"$ORG_ID"'",
    "mcp_server_workspace_id": "'"$WORKSPACE_ID"'",
    "agent_access_id": "'"$AGENT_ID"'",
    "guardrail_id": "'"$EMAIL_GUARDRAIL_ID"'",
    "name": "Redact Emails",
    "action": "redact",
    "config": {"direction": "both", "redaction_pattern": "[REDACTED:EMAIL]"}
  }' > /dev/null
echo "Created: Redact Emails (pii_email)"

# PII Policy: Redact Phones
curl -s -X POST "$BASE_URL/policies" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "organisation_id": "'"$ORG_ID"'",
    "mcp_server_workspace_id": "'"$WORKSPACE_ID"'",
    "agent_access_id": "'"$AGENT_ID"'",
    "guardrail_id": "'"$PHONE_GUARDRAIL_ID"'",
    "name": "Redact Phones",
    "action": "redact",
    "config": {"direction": "both", "redaction_pattern": "[REDACTED:PHONE]"}
  }' > /dev/null
echo "Created: Redact Phones (pii_phone)"

# PII Policy: Redact IP Addresses
curl -s -X POST "$BASE_URL/policies" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "organisation_id": "'"$ORG_ID"'",
    "mcp_server_workspace_id": "'"$WORKSPACE_ID"'",
    "agent_access_id": "'"$AGENT_ID"'",
    "guardrail_id": "'"$IP_GUARDRAIL_ID"'",
    "name": "Redact IPs",
    "action": "redact",
    "config": {"direction": "both", "redaction_pattern": "[REDACTED:IP]"}
  }' > /dev/null
echo "Created: Redact IPs (pii_ip_address)"

# Rate Limit Policy: 10 requests per minute
curl -s -X POST "$BASE_URL/policies" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "organisation_id": "'"$ORG_ID"'",
    "mcp_server_workspace_id": "'"$WORKSPACE_ID"'",
    "agent_access_id": "'"$AGENT_ID"'",
    "guardrail_id": "'"$RATE_GUARDRAIL_ID"'",
    "name": "Rate Limit 10/min",
    "action": "block",
    "config": {"limit": 10}
  }' > /dev/null
echo "Created: Rate Limit 10/min (rate_limit_per_minute)"

# RBAC Policy: Read-only access
curl -s -X POST "$BASE_URL/policies" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "organisation_id": "'"$ORG_ID"'",
    "mcp_server_workspace_id": "'"$WORKSPACE_ID"'",
    "agent_access_id": "'"$AGENT_ID"'",
    "guardrail_id": "'"$RBAC_GUARDRAIL_ID"'",
    "name": "RBAC Read Only",
    "action": "block",
    "config": {
      "default_action": "deny",
      "allowed_tools": ["search_articles", "get_article", "list_articles", "list_categories"],
      "denied_tools": ["create_article", "update_article", "delete_article"]
    }
  }' > /dev/null
echo "Created: RBAC Read Only (rbac)"

# Content Policy: Block Large Documents
curl -s -X POST "$BASE_URL/policies" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "organisation_id": "'"$ORG_ID"'",
    "mcp_server_workspace_id": "'"$WORKSPACE_ID"'",
    "agent_access_id": "'"$AGENT_ID"'",
    "guardrail_id": "'"$CONTENT_GUARDRAIL_ID"'",
    "name": "Block Large Documents",
    "action": "block",
    "config": {"direction": "both", "max_chars": 10000}
  }' > /dev/null
echo "Created: Block Large Documents (content_large_documents)"

echo ""
echo "All 8 policies created (all at agent level)."

# =============================================================================
# VERIFY SETUP
# =============================================================================

echo ""
echo "Verifying effective policies..."
curl -s "$BASE_URL/policies/mcp-server-workspaces/$WORKSPACE_ID/effective-policies?agent_access_id=$AGENT_ID" \
  -H "$AUTH_HEADER" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Total policies: {len(d.get(\"data\", d.get(\"policies\", [])))}')"

echo ""
echo "================================================"
echo "SETUP COMPLETE!"
echo ""
echo "Variables set in this session:"
echo "  BASE_URL=$BASE_URL"
echo "  AUTH_HEADER=(JWT token set)"
echo "  ORG_ID=$ORG_ID"
echo "  WORKSPACE_ID=$WORKSPACE_ID"
echo "  AGENT_ID=$AGENT_ID"
echo "  ACCESS_KEY=$ACCESS_KEY"
echo ""
echo "Guardrail IDs:"
echo "  SSN_GUARDRAIL_ID=$SSN_GUARDRAIL_ID"
echo "  CC_GUARDRAIL_ID=$CC_GUARDRAIL_ID"
echo "  EMAIL_GUARDRAIL_ID=$EMAIL_GUARDRAIL_ID"
echo "  PHONE_GUARDRAIL_ID=$PHONE_GUARDRAIL_ID"
echo "  IP_GUARDRAIL_ID=$IP_GUARDRAIL_ID"
echo "  RATE_GUARDRAIL_ID=$RATE_GUARDRAIL_ID"
echo "  RBAC_GUARDRAIL_ID=$RBAC_GUARDRAIL_ID"
echo "================================================"
```

---

## Step 9: Start Knowledge Base MCP Server (separate terminal)

Open a **new terminal** and run:

```bash
cd mcps/knowledge-base

# Create virtual environment (first time only)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start server on port 8080
python -m server.main --transport http --port 8080
```

---

## Step 10: Test Governance Policies

Go back to your **original terminal** (where variables are still set) and test:

**Important:** MCP requests use the **Agent Access Key** (not JWT token).

---

### 10.1 Test PII BLOCK Policies (SSN & Credit Card)

These policies have `action: "block"` - the entire response is blocked if PII is detected.

#### Test SSN Blocking

```bash
# Article contains SSN data - should be BLOCKED
curl -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_article",
      "arguments": {"article_id": "pii-block-ssn"}
    }
  }'
```

**Expected Result:**
```json
{
  "error": {
    "code": -32001,
    "message": "Response blocked by governance policy: Blocked due to SSN detection",
    "data": {"guardrails_triggered": ["pii_ssn"]}
  }
}
```

#### Test Credit Card Blocking

```bash
# Article contains credit card data - should be BLOCKED
curl -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_article",
      "arguments": {"article_id": "pii-block-cc"}
    }
  }'
```

**Expected Result:**
```json
{
  "error": {
    "code": -32001,
    "message": "Response blocked by governance policy: Blocked due to CREDIT_CARD detection",
    "data": {"guardrails_triggered": ["pii_credit_card"]}
  }
}
```

---

### 10.2 Test PII REDACT Policies (Email, Phone, IP)

These policies have `action: "redact"` - PII is replaced with redaction tokens.

```bash
# Article contains emails, phones, IPs - should be REDACTED (not blocked)
curl -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "get_article",
      "arguments": {"article_id": "pii-redact-contact"}
    }
  }'
```

**Expected Result:** Response returns successfully with redacted content:
- `support.lead@example.com` → `[REDACTED:EMAIL]`
- `(555) 123-4567` → `[REDACTED:PHONE]`
- `192.168.1.100` → `[REDACTED:IP]`

---

### 10.3 Test Mixed PII (Block Takes Precedence)

When an article contains both block-level PII (SSN/CC) and redact-level PII (email/phone/IP), blocking takes precedence.

```bash
# Article contains ALL PII types - should be BLOCKED (SSN/CC takes precedence)
curl -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "get_article",
      "arguments": {"article_id": "pii-mixed-all"}
    }
  }'
```

**Expected Result:** BLOCKED (credit card or SSN detected first in pipeline)

---

### 10.4 Test Clean Article (No PII)

```bash
# Regular article with no PII - should return normally
curl -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/call",
    "params": {
      "name": "get_article",
      "arguments": {"article_id": "1"}
    }
  }'
```

**Expected Result:** Full article content returned (Python Async/Await tutorial)

---

### 10.5 Test RBAC (Tool Access Control)

The RBAC policy allows read operations and denies write operations.

#### Allowed: Read Operations

```bash
# search_articles is in allowed_tools - should PASS
curl -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 10,
    "method": "tools/call",
    "params": {
      "name": "search_articles",
      "arguments": {"query": "python"}
    }
  }'
```

**Expected Result:** Search results returned

#### Blocked: Write Operations

```bash
# create_article is in denied_tools - should be BLOCKED
curl -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 11,
    "method": "tools/call",
    "params": {
      "name": "create_article",
      "arguments": {
        "title": "New Article",
        "category": "python",
        "content": "Test content",
        "author": "Test User"
      }
    }
  }'
```

**Expected Result:**
```json
{
  "error": {
    "code": -32001,
    "message": "Request blocked by governance policy: Tool 'create_article' is explicitly denied",
    "data": {"guardrails_triggered": ["rbac"]}
  }
}
```

```bash
# delete_article is in denied_tools - should be BLOCKED
curl -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 12,
    "method": "tools/call",
    "params": {
      "name": "delete_article",
      "arguments": {"article_id": "1"}
    }
  }'
```

**Expected Result:** BLOCKED - Tool 'delete_article' is in denied_tools

---

### 10.6 Test Rate Limiting

```bash
# Rate limit is 10 requests per minute - send 15 requests
for i in {1..15}; do
  echo -n "Request $i: "
  RESPONSE=$(curl -s -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_KEY" \
    -d '{
      "jsonrpc": "2.0",
      "id": '"$i"',
      "method": "tools/call",
      "params": {
        "name": "list_articles",
        "arguments": {}
      }
    }')
  if echo "$RESPONSE" | grep -q '"result"'; then
    echo "✓ ALLOWED"
  else
    echo "✗ BLOCKED (rate limit)"
  fi
  sleep 0.1
done
```

**Expected Result:**
- Requests 1-10: ✓ ALLOWED
- Requests 11+: ✗ BLOCKED (rate limit exceeded)

---

## Available Guardrail Types

### PII Detection

| Type | Category | Action | Description |
|------|----------|--------|-------------|
| `pii_ssn` | pii | block | Social Security Numbers (format validated) |
| `pii_credit_card` | pii | block | Credit/debit card numbers (Luhn validated) |
| `pii_email` | pii | redact | Email addresses |
| `pii_phone` | pii | redact | Phone numbers (10+ digits) |
| `pii_ip_address` | pii | redact | IP addresses (IPv4) |

### Other Guardrails

| Type | Category | Description |
|------|----------|-------------|
| `rbac` | rbac | Tool access control (allowed/denied lists) |
| `rate_limit_per_minute` | rate_limit | Limit requests per minute |
| `rate_limit_per_hour` | rate_limit | Limit requests per hour |
| `content_large_documents` | content | Block documents exceeding size threshold |
| `content_structured_data` | content | Block large tables |
| `content_source_code` | content | Block large code blocks |

---

## Test Data Reference

The knowledge base includes special test articles:

| Article ID | Purpose | PII Types | Expected Result |
|------------|---------|-----------|-----------------|
| `pii-block-ssn` | SSN Blocking | SSN only | **BLOCKED** |
| `pii-block-cc` | Credit Card Blocking | Credit cards only | **BLOCKED** |
| `pii-redact-contact` | PII Redaction | Email, phone, IP | **REDACTED** (content returned) |
| `pii-mixed-all` | Mixed PII | All types | **BLOCKED** (SSN/CC takes precedence) |
| `1` to `5` | Clean articles | None | Normal response |
| `content-test-1` | Content Filter | N/A | For content size testing |
| `restricted-1` | RBAC Test | N/A | Admin-only content |
| `rate-test-1` | Rate Limit | N/A | Use for repeated requests |

---

## Complete Test Flow

Run these tests in order to validate all governance policies are working correctly.

### Prerequisites

Make sure you have:
1. Cerberus running (`docker-compose up -d`)
2. MCP Server running (`python -m server.main --transport http --port 8080`)
3. `ACCESS_KEY` environment variable set from setup

```bash
# Set your access key (from setup output)
export ACCESS_KEY="your-agent-access-key-here"
```

---

### Test 1: Verify Clean Article (Baseline)

First, verify that articles without PII return normally.

```bash
echo "=== TEST 1: Clean Article (No PII) ==="
curl -s -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_article","arguments":{"article_id":"1"}}}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('✓ PASS: Article returned' if 'result' in r else '✗ FAIL: '+str(r))"
```

**Expected:** ✓ PASS: Article returned

---

### Test 2: SSN Blocking (pii_ssn)

Test that SSN data is blocked entirely.

```bash
echo "=== TEST 2: SSN Blocking ==="
curl -s -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_article","arguments":{"article_id":"pii-block-ssn"}}}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('✓ PASS: Blocked - '+r['error']['message'] if 'error' in r and 'pii_ssn' in str(r) else '✗ FAIL: Should have blocked SSN')"
```

**Expected:** ✓ PASS: Blocked - Response blocked by governance policy: Blocked due to SSN detection

---

### Test 3: Credit Card Blocking (pii_credit_card)

Test that credit card data is blocked entirely.

```bash
echo "=== TEST 3: Credit Card Blocking ==="
curl -s -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_article","arguments":{"article_id":"pii-block-cc"}}}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('✓ PASS: Blocked - '+r['error']['message'] if 'error' in r and 'pii_credit_card' in str(r) else '✗ FAIL: Should have blocked credit card')"
```

**Expected:** ✓ PASS: Blocked - Response blocked by governance policy: Blocked due to CREDIT_CARD detection

---

### Test 4: PII Redaction (pii_email, pii_phone, pii_ip_address)

Test that emails, phones, and IPs are redacted (not blocked).

```bash
echo "=== TEST 4: PII Redaction (Email/Phone/IP) ==="
RESPONSE=$(curl -s -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_article","arguments":{"article_id":"pii-redact-contact"}}}')

# Check response contains result (not blocked) and has redaction tokens
if echo "$RESPONSE" | grep -q '"result"'; then
  if echo "$RESPONSE" | grep -q '\[REDACTED:EMAIL\]'; then
    echo "✓ Email redacted"
  else
    echo "✗ Email NOT redacted"
  fi
  if echo "$RESPONSE" | grep -q '\[REDACTED:PHONE\]'; then
    echo "✓ Phone redacted"
  else
    echo "✗ Phone NOT redacted"
  fi
  if echo "$RESPONSE" | grep -q '\[REDACTED:IP'; then
    echo "✓ IP redacted"
  else
    echo "✗ IP NOT redacted"
  fi
else
  echo "✗ FAIL: Response was blocked instead of redacted"
  echo "$RESPONSE" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"
fi
```

**Expected:**
```
✓ Email redacted
✓ Phone redacted
✓ IP redacted
```

---

### Test 5: Mixed PII - Block Takes Precedence

When an article contains both block-level PII (SSN/CC) and redact-level PII (email/phone/IP), blocking should take precedence.

```bash
echo "=== TEST 5: Mixed PII (Block Takes Precedence) ==="
curl -s -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"get_article","arguments":{"article_id":"pii-mixed-all"}}}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('✓ PASS: Blocked (as expected)' if 'error' in r else '✗ FAIL: Should have blocked due to SSN/CC')"
```

**Expected:** ✓ PASS: Blocked (as expected)

---

### Test 6: RBAC - Allowed Tools

Test that allowed tools (read operations) work.

```bash
echo "=== TEST 6: RBAC - Allowed Tool (search_articles) ==="
curl -s -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"search_articles","arguments":{"query":"python"}}}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('✓ PASS: Search allowed' if 'result' in r else '✗ FAIL: '+str(r))"
```

**Expected:** ✓ PASS: Search allowed

---

### Test 7: RBAC - Denied Tools

Test that denied tools (write operations) are blocked.

```bash
echo "=== TEST 7: RBAC - Denied Tool (create_article) ==="
curl -s -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"create_article","arguments":{"title":"Test","category":"test","content":"Test","author":"Test"}}}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('✓ PASS: Blocked by RBAC' if 'error' in r and 'rbac' in str(r) else '✗ FAIL: Should have blocked')"
```

**Expected:** ✓ PASS: Blocked by RBAC

---

### Test 8: Rate Limiting

Test that rate limiting kicks in after the configured limit.

```bash
echo "=== TEST 8: Rate Limiting (10 req/min) ==="
echo "Sending 12 requests..."
PASSED=0
BLOCKED=0
for i in {1..12}; do
  RESPONSE=$(curl -s -X POST "http://localhost:8000/governance-plane/api/v1/proxy/message" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_KEY" \
    -d '{"jsonrpc":"2.0","id":'"$i"',"method":"tools/call","params":{"name":"list_articles","arguments":{}}}')
  if echo "$RESPONSE" | grep -q '"result"'; then
    ((PASSED++))
  else
    ((BLOCKED++))
  fi
  sleep 0.05
done
echo "Results: $PASSED passed, $BLOCKED blocked"
if [ $BLOCKED -gt 0 ]; then
  echo "✓ PASS: Rate limiting is working"
else
  echo "✗ FAIL: Rate limiting did not trigger (try waiting 1 minute and retry)"
fi
```

**Expected:** ✓ PASS: Rate limiting is working (some requests blocked after limit)

---

### Run All Tests

Save this as `test-governance.sh` and run: `bash test-governance.sh`

```bash
#!/bin/bash

# Ensure ACCESS_KEY is set
if [ -z "$ACCESS_KEY" ]; then
  echo "ERROR: ACCESS_KEY not set. Run: export ACCESS_KEY='your-key'"
  exit 1
fi

PROXY_URL="http://localhost:8000/governance-plane/api/v1/proxy/message"
PASS=0
FAIL=0

test_request() {
  local name="$1"
  local article_id="$2"
  local expect_block="$3"  # "block" or "allow"

  RESPONSE=$(curl -s -X POST "$PROXY_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_KEY" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"get_article\",\"arguments\":{\"article_id\":\"$article_id\"}}}")

  HAS_ERROR=$(echo "$RESPONSE" | grep -c '"error"')

  if [ "$expect_block" = "block" ] && [ "$HAS_ERROR" -gt 0 ]; then
    echo "✓ $name: BLOCKED (as expected)"
    ((PASS++))
  elif [ "$expect_block" = "allow" ] && [ "$HAS_ERROR" -eq 0 ]; then
    echo "✓ $name: ALLOWED (as expected)"
    ((PASS++))
  else
    echo "✗ $name: FAILED (expected $expect_block)"
    ((FAIL++))
  fi
}

echo "========================================"
echo "    CERBERUS GOVERNANCE TEST SUITE     "
echo "========================================"
echo ""

echo "--- PII BLOCK Tests ---"
test_request "SSN Blocking" "pii-block-ssn" "block"
test_request "Credit Card Blocking" "pii-block-cc" "block"
test_request "Mixed PII (block wins)" "pii-mixed-all" "block"

echo ""
echo "--- PII REDACT Tests ---"
test_request "Email/Phone/IP Redaction" "pii-redact-contact" "allow"

echo ""
echo "--- Clean Article Test ---"
test_request "No PII Article" "1" "allow"

echo ""
echo "--- RBAC Tests ---"
# Test allowed tool
RESPONSE=$(curl -s -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_articles","arguments":{"query":"test"}}}')
if echo "$RESPONSE" | grep -q '"result"'; then
  echo "✓ RBAC Allow (search_articles): ALLOWED"
  ((PASS++))
else
  echo "✗ RBAC Allow (search_articles): FAILED"
  ((FAIL++))
fi

# Test denied tool
RESPONSE=$(curl -s -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"create_article","arguments":{"title":"T","category":"t","content":"t","author":"t"}}}')
if echo "$RESPONSE" | grep -q '"error"'; then
  echo "✓ RBAC Deny (create_article): BLOCKED"
  ((PASS++))
else
  echo "✗ RBAC Deny (create_article): FAILED"
  ((FAIL++))
fi

echo ""
echo "========================================"
echo "    RESULTS: $PASS passed, $FAIL failed"
echo "========================================"

if [ $FAIL -eq 0 ]; then
  echo "All tests passed! ✓"
  exit 0
else
  echo "Some tests failed. Check configuration."
  exit 1
fi
```

---

## Quick Setup Script

Save this as `setup-cerberus.sh` and run: `bash setup-cerberus.sh`

```bash
#!/bin/bash
set -e

BASE_URL="http://localhost:8000/control-plane/api/v1"

echo "=== Step 1: Login as Super Admin ==="
AUTH_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"superadmin@cerberus.com","password":"superadmin123"}')
JWT_TOKEN=$(echo "$AUTH_RESPONSE" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
AUTH_HEADER="Authorization: Bearer $JWT_TOKEN"
echo "Logged in as super admin"

echo ""
echo "=== Step 2: Create Guardrails ==="
SSN_ID=$(curl -s -X POST "$BASE_URL/guardrails" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d '{"guardrail_type":"pii_ssn","category":"pii"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "pii_ssn: $SSN_ID"

CC_ID=$(curl -s -X POST "$BASE_URL/guardrails" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d '{"guardrail_type":"pii_credit_card","category":"pii"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "pii_credit_card: $CC_ID"

EMAIL_ID=$(curl -s -X POST "$BASE_URL/guardrails" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d '{"guardrail_type":"pii_email","category":"pii"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "pii_email: $EMAIL_ID"

PHONE_ID=$(curl -s -X POST "$BASE_URL/guardrails" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d '{"guardrail_type":"pii_phone","category":"pii"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "pii_phone: $PHONE_ID"

IP_ID=$(curl -s -X POST "$BASE_URL/guardrails" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d '{"guardrail_type":"pii_ip_address","category":"pii"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "pii_ip_address: $IP_ID"

RATE_ID=$(curl -s -X POST "$BASE_URL/guardrails" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d '{"guardrail_type":"rate_limit_per_minute","category":"rate_limit"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "rate_limit_per_minute: $RATE_ID"

RBAC_ID=$(curl -s -X POST "$BASE_URL/guardrails" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d '{"guardrail_type":"rbac","category":"rbac"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "rbac: $RBAC_ID"

CONTENT_ID=$(curl -s -X POST "$BASE_URL/guardrails" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d '{"guardrail_type":"content_large_documents","category":"content"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "content_large_documents: $CONTENT_ID"

echo "All 8 guardrails created"

echo ""
echo "=== Step 3: Create Organisation ==="
ORG_RESPONSE=$(curl -s -X POST "$BASE_URL/organisations" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Org","subscription_tier":"default","admin_email":"admin@test.com"}')
ORG_ID=$(echo "$ORG_RESPONSE" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "Organisation: $ORG_ID"

echo ""
echo "=== Step 4: Create Workspace ==="
WS_RESPONSE=$(curl -s -X POST "$BASE_URL/organisations/$ORG_ID/mcp-server-workspaces" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"name":"KB Dev","environment_type":"development","mcp_server_url":"http://host.docker.internal:8080"}')
WORKSPACE_ID=$(echo "$WS_RESPONSE" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "Workspace: $WORKSPACE_ID"

echo ""
echo "=== Step 5: Create Agent Access ==="
AGENT_RESPONSE=$(curl -s -X POST "$BASE_URL/mcp-server-workspaces/$WORKSPACE_ID/agent-accesses" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Agent"}')
AGENT_ID=$(echo "$AGENT_RESPONSE" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
ACCESS_KEY=$(echo "$AGENT_RESPONSE" | python3 -c "import sys,json;print(json.load(sys.stdin)['key'])")
echo "Agent: $AGENT_ID"

echo ""
echo "=== Step 6: Create Policies (all at agent level) ==="

# All policies at agent level
curl -s -X POST "$BASE_URL/policies" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "{\"organisation_id\":\"$ORG_ID\",\"mcp_server_workspace_id\":\"$WORKSPACE_ID\",\"agent_access_id\":\"$AGENT_ID\",\"guardrail_id\":\"$SSN_ID\",\"name\":\"Block SSN\",\"action\":\"block\",\"config\":{\"direction\":\"both\"}}" > /dev/null
echo "Created: Block SSN (pii_ssn)"

curl -s -X POST "$BASE_URL/policies" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "{\"organisation_id\":\"$ORG_ID\",\"mcp_server_workspace_id\":\"$WORKSPACE_ID\",\"agent_access_id\":\"$AGENT_ID\",\"guardrail_id\":\"$CC_ID\",\"name\":\"Block CC\",\"action\":\"block\",\"config\":{\"direction\":\"both\"}}" > /dev/null
echo "Created: Block Credit Cards (pii_credit_card)"

curl -s -X POST "$BASE_URL/policies" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "{\"organisation_id\":\"$ORG_ID\",\"mcp_server_workspace_id\":\"$WORKSPACE_ID\",\"agent_access_id\":\"$AGENT_ID\",\"guardrail_id\":\"$EMAIL_ID\",\"name\":\"Redact Email\",\"action\":\"redact\",\"config\":{\"direction\":\"both\",\"redaction_pattern\":\"[REDACTED:EMAIL]\"}}" > /dev/null
echo "Created: Redact Email (pii_email)"

curl -s -X POST "$BASE_URL/policies" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "{\"organisation_id\":\"$ORG_ID\",\"mcp_server_workspace_id\":\"$WORKSPACE_ID\",\"agent_access_id\":\"$AGENT_ID\",\"guardrail_id\":\"$PHONE_ID\",\"name\":\"Redact Phone\",\"action\":\"redact\",\"config\":{\"direction\":\"both\",\"redaction_pattern\":\"[REDACTED:PHONE]\"}}" > /dev/null
echo "Created: Redact Phone (pii_phone)"

curl -s -X POST "$BASE_URL/policies" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "{\"organisation_id\":\"$ORG_ID\",\"mcp_server_workspace_id\":\"$WORKSPACE_ID\",\"agent_access_id\":\"$AGENT_ID\",\"guardrail_id\":\"$IP_ID\",\"name\":\"Redact IP\",\"action\":\"redact\",\"config\":{\"direction\":\"both\",\"redaction_pattern\":\"[REDACTED:IP]\"}}" > /dev/null
echo "Created: Redact IP (pii_ip_address)"

curl -s -X POST "$BASE_URL/policies" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "{\"organisation_id\":\"$ORG_ID\",\"mcp_server_workspace_id\":\"$WORKSPACE_ID\",\"agent_access_id\":\"$AGENT_ID\",\"guardrail_id\":\"$RATE_ID\",\"name\":\"Rate Limit\",\"action\":\"block\",\"config\":{\"limit\":10}}" > /dev/null
echo "Created: Rate Limit (rate_limit_per_minute)"

curl -s -X POST "$BASE_URL/policies" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "{\"organisation_id\":\"$ORG_ID\",\"mcp_server_workspace_id\":\"$WORKSPACE_ID\",\"agent_access_id\":\"$AGENT_ID\",\"guardrail_id\":\"$RBAC_ID\",\"name\":\"RBAC\",\"action\":\"block\",\"config\":{\"default_action\":\"deny\",\"allowed_tools\":[\"search_articles\",\"get_article\",\"list_articles\"],\"denied_tools\":[\"create_article\",\"delete_article\"]}}" > /dev/null
echo "Created: RBAC (rbac)"

curl -s -X POST "$BASE_URL/policies" -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "{\"organisation_id\":\"$ORG_ID\",\"mcp_server_workspace_id\":\"$WORKSPACE_ID\",\"agent_access_id\":\"$AGENT_ID\",\"guardrail_id\":\"$CONTENT_ID\",\"name\":\"Block Large Docs\",\"action\":\"block\",\"config\":{\"direction\":\"both\",\"max_chars\":10000}}" > /dev/null
echo "Created: Block Large Documents (content_large_documents)"

echo ""
echo "All 8 policies created (all at agent level)."

echo ""
echo "================================================"
echo "SETUP COMPLETE!"
echo ""
echo "Export these variables to test:"
echo "  export ACCESS_KEY=\"$ACCESS_KEY\""
echo ""
echo "Then start MCP server in another terminal:"
echo "  cd mcps/knowledge-base"
echo "  python -m server.main --transport http --port 8080"
echo ""
echo "Test with:"
echo "  curl -X POST 'http://localhost:8000/governance-plane/api/v1/proxy/message' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'Authorization: Bearer $ACCESS_KEY' \\"
echo "    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"list_articles\",\"arguments\":{}}}'"
echo "================================================"
```

---

## Troubleshooting

### "Authorization header required" on Control Plane APIs
- You need a JWT token from `/auth/login`
- Include `Authorization: Bearer <jwt_token>` header

### "Invalid or expired token" on Control Plane APIs
- JWT tokens expire after some time
- Login again to get a new token

### "Authorization required" on Governance Proxy
- You need an Agent Access Key (not JWT token)
- Include `Authorization: Bearer <agent_key>` header

### "No MCP server URL configured" error
- Check workspace has `mcp_server_url` set
- Use `http://host.docker.internal:8080` for Docker (see below)

### Understanding `host.docker.internal`
When Cerberus runs in Docker and the MCP server runs on your host machine:
- `localhost` inside a Docker container refers to the container itself, NOT your host
- `host.docker.internal` is Docker's special DNS name that resolves to the host machine's IP
- So `http://host.docker.internal:8080` → your host's `localhost:8080`

```
Your Machine (Host)
├── Docker Container (Cerberus @ port 8000)
│   └── Needs to reach: host.docker.internal:8080
│           ↓ (resolves to host IP)
└── MCP Server @ localhost:8080
```

### Policies not being applied
- Check policies are enabled (`is_enabled: true`)
- Verify guardrail_id is correct
- Check effective policies endpoint

### View Cerberus Logs

```bash
docker-compose logs -f cerberus | grep -E "(PII|RBAC|RateLimit|decision|policy)"
```

---

## Cleanup

```bash
cd cerberus/docker
docker-compose down      # Stop containers
docker-compose down -v   # Stop and remove volumes (resets database)
```

---

## API Reference

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | None | Login, get JWT tokens |
| POST | `/auth/refresh` | None | Refresh JWT tokens |

### Control Plane (requires JWT token)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | `/guardrails` | Any | List guardrail definitions |
| POST | `/guardrails` | SuperAdmin | Create guardrail definition |
| GET/POST | `/organisations` | SuperAdmin | List/create organisations |
| GET/POST | `/organisations/{id}/mcp-server-workspaces` | OrgAdmin+ | List/create workspaces |
| GET/POST | `/mcp-server-workspaces/{id}/agent-accesses` | OrgAdmin+ | List/create agent keys |
| POST | `/policies` | OrgAdmin+ | Create policy |
| GET | `/policies/organisations/{id}/policies` | Any | List org policies |
| GET | `/policies/mcp-server-workspaces/{id}/effective-policies` | Any | Get effective policies |

### Governance Plane (requires Agent Access Key)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/proxy/message` | Proxy MCP request through governance |

---

## Default Credentials (after seeding)

| User | Email | Password | Role |
|------|-------|----------|------|
| Super Admin | superadmin@cerberus.com | superadmin123 | super_admin |
| Org Admin | admin@demo.com | admin123 | org_admin |
| Viewer | viewer@demo.com | viewer123 | org_viewer |

---

## MCP Tools Reference

| Tool | Type | Description |
|------|------|-------------|
| `search_articles` | Read | Search knowledge base |
| `get_article` | Read | Get article by ID |
| `list_articles` | Read | List all articles |
| `list_categories` | Read | List categories |
| `create_article` | Write | Create new article |
| `update_article` | Write | Update existing article |
| `delete_article` | Delete | Delete article |
