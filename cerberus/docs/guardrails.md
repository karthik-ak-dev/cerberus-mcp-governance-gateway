# Guardrails

Cerberus provides a comprehensive set of guardrails that evaluate every MCP request and response in real-time.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GUARDRAIL PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   MCP Request → ┌─────────────────────────────────────────────────────┐     │
│                 │                  GUARDRAIL PIPELINE                  │     │
│                 │                                                      │     │
│                 │   ┌─────┐  ┌───────────┐  ┌─────┐  ┌─────────────┐  │     │
│                 │   │RBAC │→ │Rate Limit │→ │ PII │→ │Content Filter│  │     │
│                 │   └─────┘  └───────────┘  └─────┘  └─────────────┘  │     │
│                 │                                                      │     │
│                 │   Each guardrail returns: ALLOW | BLOCK | MODIFY     │     │
│                 │   Pipeline stops on BLOCK, continues otherwise       │     │
│                 │                                                      │     │
│                 └─────────────────────────────────────────────────────┘     │
│                         │                                                    │
│                         ▼                                                    │
│                 Final Decision: allow / block_request / block_response / modify
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Guardrail Actions

Each guardrail can return one of these actions:

| Action | Effect | Use Case |
|--------|--------|----------|
| `ALLOW` | Continue to next guardrail | Check passed |
| `BLOCK_REQUEST` | Stop pipeline, deny request | RBAC denied, rate limited |
| `BLOCK_RESPONSE` | Stop pipeline, deny response | PII detected in response |
| `MODIFY` | Transform message, continue | PII redacted |
| `LOG_ONLY` | Record event, continue | Audit finding |
| `THROTTLE` | Rate limit exceeded | Too many requests |

---

## Available Guardrail Types

### 1. RBAC (Agent Tool Access Control)

**Type:** `rbac`

**Purpose:** Control which tools agents can access using simple allow/deny lists.

**Direction:** Request only

**Configuration:**
```json
{
  "allowed_tools": ["search_articles", "get_article", "list_articles"],
  "denied_tools": ["create_article", "update_article", "delete_article"],
  "default_action": "deny"
}
```

**How it works:**
1. Extract tool name from `tools/call` method
2. Check `denied_tools` first - if matches, block
3. Check `allowed_tools` - if matches, allow
4. If `allowed_tools` defined but no match, block
5. Otherwise use `default_action`

**Wildcards:**
- `*` matches any characters
- `filesystem/*` matches `filesystem/read`, `filesystem/write`, etc.
- `database/drop_*` matches `database/drop_table`, `database/drop_index`, etc.

---

### 2. PII Detection (Granular)

Each PII type is a separate guardrail for granular control.

**Types:**
- `pii_credit_card` - Credit/debit card numbers (Luhn validated)
- `pii_ssn` - Social Security Numbers (format validated)
- `pii_email` - Email addresses
- `pii_phone` - Phone numbers (10+ digits)
- `pii_ip_address` - IP addresses (IPv4)

**Direction:** Both (configurable)

**Configuration:**
```json
{
  "direction": "both",
  "redaction_pattern": "[REDACTED:SSN]"
}
```

**Direction options:**
- `"request"` - Only check outgoing requests
- `"response"` - Only check incoming responses
- `"both"` - Check both directions

**How it works:**
1. Extract all text content from message
2. Scan for PII patterns using regex and validators
3. Block or redact based on policy action

**Example redaction:**
```
Original: "Contact john@example.com at 555-123-4567"
Redacted: "Contact [REDACTED:EMAIL] at [REDACTED:PHONE]"
```

---

### 3. Content Filter

Filter large or structured content.

**Types:**
- `content_large_documents` - Block documents exceeding size threshold
- `content_structured_data` - Block structured data exceeding row limits
- `content_source_code` - Block source code exceeding size threshold

**Direction:** Both (configurable)

**Configuration:**

For `content_large_documents`:
```json
{
  "direction": "both",
  "max_chars": 10000
}
```

For `content_structured_data`:
```json
{
  "direction": "both",
  "max_rows": 50
}
```

For `content_source_code`:
```json
{
  "direction": "both",
  "max_chars": 5000
}
```

---

### 4. Rate Limiting

Prevent abuse by limiting request frequency.

**Types:**
- `rate_limit_per_minute` - Limit requests per minute
- `rate_limit_per_hour` - Limit requests per hour

**Direction:** Request only

**Configuration:**
```json
{
  "limit": 60
}
```

**How it works:**
1. Track request count per agent per time window
2. Use Redis for distributed counting (sliding window)
3. Block if limit exceeded

**Response on block:**
```json
{
  "error": {
    "code": -32001,
    "message": "Rate limit exceeded: 61/60 requests per minute",
    "data": {
      "guardrails_triggered": ["rate_limit"],
      "retry_after_seconds": 45
    }
  }
}
```

---

## Execution Order

### Request Direction (outbound to MCP server)

```
┌─────────────────────────────────────────────────────────────────┐
│  REQUEST GUARDRAIL ORDER (fast checks first)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. RBAC          → Can this agent use this tool?              │
│  2. Rate Limit    → Within rate limits?                        │
│  3. PII Detection → No PII being sent?                         │
│  4. Content Filter→ Content within limits?                     │
│                                                                 │
│  Rationale: Check permissions before expensive scans           │
└─────────────────────────────────────────────────────────────────┘
```

### Response Direction (inbound from MCP server)

```
┌─────────────────────────────────────────────────────────────────┐
│  RESPONSE GUARDRAIL ORDER (security-critical first)            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. PII Detection → SSN, credit cards in response?             │
│  2. Content Filter→ Content within limits?                     │
│                                                                 │
│  Rationale: Block sensitive data leakage first                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Policy Configuration

Guardrails are configured through policies. Each policy links ONE guardrail to ONE entity.

### Policy Levels

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         POLICY HIERARCHY                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   1. ORGANISATION LEVEL (baseline)                                          │
│      mcp_server_workspace_id: null, agent_access_id: null                   │
│      └── Applies to all workspaces and agents in organisation              │
│                                                                              │
│   2. WORKSPACE LEVEL (environment override)                                 │
│      mcp_server_workspace_id: <id>, agent_access_id: null                   │
│      └── Overrides organisation settings for specific workspace            │
│      └── Example: stricter rules for production                             │
│                                                                              │
│   3. AGENT LEVEL (individual exception)                                     │
│      mcp_server_workspace_id: <id>, agent_access_id: <id>                   │
│      └── Overrides workspace settings for specific agent                    │
│      └── Example: elevated permissions for admin agent                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Example: Creating Policies via API

**1. Organisation-level PII blocking:**
```bash
curl -X POST "/api/v1/policies" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "organisation_id": "org-uuid",
    "guardrail_id": "pii-ssn-guardrail-uuid",
    "name": "Block SSN Org-wide",
    "action": "block",
    "config": {"direction": "both"}
  }'
```

**2. Workspace-level rate limiting:**
```bash
curl -X POST "/api/v1/policies" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "organisation_id": "org-uuid",
    "mcp_server_workspace_id": "workspace-uuid",
    "guardrail_id": "rate-limit-guardrail-uuid",
    "name": "Production Rate Limit",
    "action": "block",
    "config": {"limit": 100}
  }'
```

**3. Agent-level RBAC:**
```bash
curl -X POST "/api/v1/policies" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "organisation_id": "org-uuid",
    "mcp_server_workspace_id": "workspace-uuid",
    "agent_access_id": "agent-uuid",
    "guardrail_id": "rbac-guardrail-uuid",
    "name": "Read-Only Agent",
    "action": "block",
    "config": {
      "allowed_tools": ["search_*", "get_*", "list_*"],
      "denied_tools": ["create_*", "update_*", "delete_*"],
      "default_action": "deny"
    }
  }'
```

---

## Performance

Guardrails are optimized for low-latency inline evaluation:

| Component | Target | Implementation |
|-----------|--------|----------------|
| Total pipeline | < 50ms | Async execution |
| Policy lookup | < 5ms | Redis caching |
| Per-guardrail | < 10ms | Efficient algorithms |
| Audit logging | Non-blocking | Fire-and-forget |

**Optimization Strategies:**
1. **Early Exit:** Pipeline short-circuits on block
2. **Guardrail Order:** Fast checks (RBAC) before expensive scans (PII)
3. **Policy Caching:** Effective policies cached in Redis
4. **Async I/O:** All operations are non-blocking

---

## Audit Trail

Every guardrail evaluation is logged:

```json
{
  "decision_id": "dec-abc123",
  "organisation_id": "550e8400...",
  "mcp_server_workspace_id": "660e8400...",
  "agent_access_id": "770e8400...",
  "direction": "request",
  "method": "tools/call",
  "tool_name": "get_article",
  "decision": "allow",
  "processing_time_ms": 8,
  "guardrail_results": {
    "rbac": {
      "triggered": false,
      "action_taken": "allow",
      "details": { "tool": "get_article", "match_type": "allowed_tools" }
    },
    "rate_limit": {
      "triggered": false,
      "action_taken": "allow",
      "details": { "current_count": 45, "limit": 60 }
    }
  },
  "created_at": "2024-01-15T12:00:00Z"
}
```

---

## Best Practices

### Policy Design

1. **Start restrictive:** Default deny, explicitly allow
2. **Layer policies:** Organisation baseline → Workspace specifics → Agent exceptions
3. **Use wildcards wisely:** Prefer explicit patterns over broad wildcards
4. **Test thoroughly:** Verify policies in staging before production

### Rate Limiting

1. **Set appropriate limits:** Based on actual usage patterns
2. **Per-tool limits:** More restrictive for expensive operations
3. **Monitor usage:** Adjust based on analytics

### PII Detection

1. **Block sensitive types:** SSN, credit cards should block, not redact
2. **Redact common PII:** Email, phone can usually be redacted
3. **Review false positives:** Tune patterns for your data

### RBAC

1. **Use allowed_tools for whitelisting:** Define what's explicitly allowed
2. **Use denied_tools for blacklisting:** Block specific dangerous tools
3. **Set default_action to deny:** Block by default, explicitly allow
