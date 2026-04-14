# EP-18 Technical Design — MCP Server (Read & Query Interface)

> **Decision summary**: thin Python adapter reusing the existing FastAPI application service layer, shipped as a separate process (`apps/mcp-server/`). Official MCP Python SDK with stdio + HTTP/SSE transports. New token kind `mcp_token` on EP-00 identity, single `mcp:read` scope, single-workspace binding. Authorization delegated entirely to the application layer. Subscriptions bridged from the existing EP-12 Redis pub/sub bus. Audit events share the EP-12 pipeline. Read-only MVP; writes are a separate epic.

---

## 1. Context & Goals

### Context

The platform already has a Python/FastAPI backend with a layered architecture (Presentation → Application → Domain → Infrastructure). Read endpoints, authz guards, Puppet client, Jira export service, SSE bus, rate limiter and audit pipeline all exist. What is missing is a **protocol-level façade** that lets MCP-capable external agents (Claude Code, copilots, CLIs) consume the platform without going through the HTTP REST API and without re-implementing auth/pagination/schemas.

### Goals

- Ship an MCP server that exposes ~20 read tools + 4 subscribable resources
- Reuse application services 1:1 — zero new business logic
- Token-based auth bound to a single workspace, admin-managed lifecycle
- Same authorization, rate limiting, audit as REST — no parallel implementations
- Schema drift-proof via shared Pydantic models
- Deployable, observable, rate-limited, documented

### Non-Goals

- Writes / mutations (follow-up epic)
- GraphQL / gRPC
- Superadmin cross-workspace tools
- Bulk export
- Dundun chat writes

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   External MCP Clients                       │
│   (Claude Code, Claude Desktop, third-party agents, CLIs)    │
└───────────────┬─────────────────────────────┬────────────────┘
                │ stdio                        │ HTTPS
                ▼                             ▼
┌──────────────────────────────────────────────────────────────┐
│                    apps/mcp-server/ (Python)                 │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  MCP SDK  (stdio + HTTP/SSE transports)                │  │
│  └───────────────┬────────────────────────────────────────┘  │
│                  │                                            │
│  ┌───────────────▼──────────────────────────────────────┐    │
│  │  Middleware: auth → rate-limit → audit → dispatch    │    │
│  └───────────────┬──────────────────────────────────────┘    │
│                  │                                            │
│  ┌───────────────▼──────────────────────────────────────┐    │
│  │  Tool / Resource Registry                             │    │
│  │  (workitem, comments, versions, assistant, semantic, │    │
│  │   tags, attachments, inbox, dashboard, jira, ...)    │    │
│  └───────────────┬──────────────────────────────────────┘    │
│                  │                                            │
└──────────────────┼────────────────────────────────────────────┘
                   │  direct Python calls (in-process)
                   ▼
┌──────────────────────────────────────────────────────────────┐
│                 Shared Application Layer                     │
│   services/ (WorkItemService, CommentService, ReviewService,  │
│    ValidationService, SearchService, InboxService, ...)      │
│                                                              │
│   domain/ (Work items, versions, specs, checklists, tags)    │
│                                                              │
│   infrastructure/ (repos, Puppet client, Jira client,         │
│    SSE bus consumer, audit publisher, rate-limit client)     │
└────────┬──────────────────┬──────────────────┬───────────────┘
         │                  │                  │
    ┌────▼────┐        ┌────▼────┐       ┌─────▼─────┐
    │Postgres │        │  Redis  │       │  Celery   │
    │         │        │(pubsub, │       │ (audit +  │
    │         │        │ rate,   │       │ last-used)│
    │         │        │ cache)  │       │           │
    └─────────┘        └─────────┘       └───────────┘
```

**Key property**: the MCP process is colocated with the application layer as a **separate process in the same repo, same Python environment, same image base** — it imports the service layer directly. No HTTP hop to the REST API. The REST API and the MCP server are two presentation layers over one shared application core.

### Package Layout

```
apps/mcp-server/
  pyproject.toml
  Dockerfile
  helm/values.yaml
  src/
    mcp_server/
      __init__.py
      main.py                    # entry point; picks transport from env
      server.py                  # MCP server bootstrap + registries
      middleware/
        auth.py                  # verify token → request context
        audit.py                 # fire-and-forget event
        rate_limit.py            # reuse EP-12 limiter
        errors.py                # service exception → JSON-RPC
      tools/
        user_me.py
        workitem/
          get.py
          search.py
          children.py
          hierarchy.py
          list_by_epic.py
        comments/list.py
        versions/list.py
        versions/diff.py
        reviews/list.py
        validations/list.py
        timeline/list.py
        assistant/thread_get.py
        assistant/threads_workspace.py
        semantic/search.py
        tags/list.py
        tags/workitems.py
        labels/list.py
        attachments/list.py
        attachments/signed_url.py
        inbox/list.py
        workspace/dashboard.py
        jira/snapshot.py
      resources/
        workitem.py
        epic_tree.py
        workspace_dashboard.py
        user_inbox.py
      bridge/
        sse_bridge.py            # EP-12 bus → MCP notifications
        debounce.py
        authz_gate.py
      schemas/                   # Pydantic — derived from shared DTO source
      health.py
      metrics.py
  tests/
    integration/                 # one file per tool, cross-workspace forbidden check
    e2e/                         # stdio + HTTP smoke, used in CI `e2e-mcp` job
```

Shared code with REST backend (`services/`, `domain/`, `infrastructure/`) lives in the existing `packages/` namespace and is imported by both apps.

---

## 3. Key Technical Decisions

### 3.1 Python, same process-family as REST API

**Decision**: write the MCP server in Python using the official MCP Python SDK; deploy as a separate process that imports the existing application layer directly.

**Reasoning**: the REST API is FastAPI (Python). Rewriting services in another language is wasteful; calling REST over HTTP from a co-deployed MCP server is a pointless round-trip adding latency, auth translation and a second observability surface. Importing the services directly gives perfect alignment with the existing authz logic and DTOs.

**Alternatives rejected**:
- **Node + MCP TS SDK calling REST**: doubles the observability surface, introduces DTO re-encoding, invites authz drift.
- **Embed MCP inside the FastAPI process**: couples scaling; stdio transport conflicts with ASGI; blast-radius of MCP bugs hits REST.
- **Generate tools from an OpenAPI spec**: OpenAPI is for HTTP; MCP tool schemas are richer (input+output, deprecation). Shared Pydantic models serve both.

### 3.2 Single scope `mcp:read`

**Decision**: one scope for MVP; do not pre-split into `mcp:read:workitems`, `mcp:read:comments`, etc.

**Reasoning**: we do not have a concrete use case demanding finer granularity today. Every tool already enforces per-resource authz via the application layer. A premature scope split creates a matrix of (scope × capability × tool) with no operational benefit. YAGNI.

**Future**: add scopes only when a real client requires reduced blast radius (e.g., "a bot that only reads dashboards"). Design leaves room: scope is a list column.

### 3.3 Single-workspace token binding

**Decision**: an MCP token is bound to exactly one workspace. No multi-workspace tokens.

**Reasoning**: the platform's strongest tenancy guarantee is workspace isolation (§3.15). A token valid in two workspaces is a persistent cross-tenant bridge and a compliance nightmare. Users with multi-workspace membership issue one token per workspace; the client config chooses which to present. Cost is trivial; safety gain is large.

### 3.4 Authorization entirely in the application layer

**Decision**: MCP tool handlers never call repositories directly. Every tool passes `{ actor_id, workspace_id }` from the session into the existing service method, and the service enforces authz.

**Reasoning**: single source of truth for authz. Any new capability or rule automatically applies to both REST and MCP. Integration tests per tool assert cross-workspace `-32003` to catch accidental `session.query(Model).all()` patterns.

### 3.5 Schema source of truth

**Decision**: tool input/output schemas are Pydantic models. REST DTOs and MCP tool schemas reference the same Pydantic classes (via a shared `packages/schemas/` module). The MCP SDK generates JSON schema from Pydantic.

**Reasoning**: prevents the most common MCP-failure mode — schema drift between REST and MCP. Any DTO change surfaces in `tools/list` automatically and is caught by the `e2e-mcp` snapshot test.

### 3.6 Transports: stdio and HTTP/SSE both ship day one

**Decision**: both transports enabled from the first release.

**Reasoning**: stdio is table-stakes for local agents (Claude Code). HTTP/SSE is required for remote / hosted agents. The SDK supports both. Stdio alone blocks remote use cases; HTTP alone blocks the most common integration. Ship both.

### 3.7 SSE subscriptions bridged from EP-12

**Decision**: the MCP server is a **consumer** of the EP-12 Redis pub/sub bus. It does not publish events; it does not hold a parallel bus. The `sse_bridge` module subscribes to the relevant channels, filters by workspace, re-authorizes on emit, debounces, throttles, and forwards as `notifications/resources/updated`.

**Reasoning**: events in the platform are already published for the web UI's SSE. Duplicating the bus is wasteful and creates consistency issues. Consuming is cheap (Redis pub/sub is fan-out by design).

### 3.8 Audit pipeline shared with REST

**Decision**: every MCP invocation emits an audit event to the same Celery queue and storage as REST. Event kind is `mcp.invocation`.

**Reasoning**: one query (`SELECT * FROM audit WHERE kind LIKE 'mcp.%' OR kind LIKE 'rest.%'`) reconstructs all user action. Separate stores split the forensics story.

### 3.9 Rate limiting shared with REST

**Decision**: reuse EP-12 Redis-backed token bucket; scope keys under `rl:mcp:token:<id>` and `rl:mcp:ip:<ip_hash>`.

**Reasoning**: prevents the MCP surface from being a backdoor around REST limits. One bucket per token across transports.

### 3.10 Error code policy: prefer `-32003` over `-32002`

**Decision**: return `-32003 forbidden` whenever the caller lacks read permission; reserve `-32002 not_found` only for the narrow case where the caller would have seen the item had it existed (i.e., soft-deleted within their workspace).

**Reasoning**: leaking "item X exists but you can't see it" is a well-known enumeration vector. Default to forbidden; explicit not_found only where it cannot leak.

### 3.11 Verification cache with 5 s TTL

**Decision**: cache verification results in Redis for 5 s; on revoke, explicitly DEL the cache key.

**Reasoning**: balances hot-path cost (argon2id per call is too expensive) with revocation SLO. 5 s is the bound on "time between `DELETE token` and next rejection." Most workflows tolerate this; stricter SLOs can drop TTL to 0 at perf cost.

### 3.12 argon2id cost tuned for API, not login

**Decision**: argon2id parameters tuned for ~10–20 ms on the target hardware (not the login-hardening 100+ ms profile).

**Reasoning**: MCP verification runs on every request. A login-grade hash budget destroys p95. A 10–20 ms hash + HMAC lookup key + 5 s cache is an acceptable combined profile with tractable brute-force cost (~50 M/s/core is still 32 days for 8 random bytes of base64).

### 3.13 Read-only MVP, writes are a separate epic

**Decision**: no mutation tools in this epic.

**Reasoning**: writes require a new scope (`mcp:write`), a tighter auth path (shorter-lived tokens, additional confirmation for destructive ops), a separate security review, and different UX (idempotency keys, dry-run). Bundling with reads doubles scope and delays shipping.

### 3.14 Dashboard caching 30 s

**Decision**: cache `workspace.dashboard` results per-workspace for 30 s.

**Reasoning**: dashboards aggregate heavy queries. 30 s staleness is acceptable (admins watch trends, not seconds). Caching shared with REST.

---

## 4. Data Model Changes

### New table `mcp_tokens`

```sql
CREATE TABLE mcp_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    lookup_key BYTEA NOT NULL,               -- HMAC-SHA256(plaintext, pepper), 32 bytes
    secret_hash TEXT NOT NULL,               -- argon2id hash of plaintext
    scopes TEXT[] NOT NULL DEFAULT '{mcp:read}',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_used_at TIMESTAMPTZ,
    last_used_ip INET,
    revoked_at TIMESTAMPTZ,
    UNIQUE (lookup_key)
);

CREATE INDEX idx_mcp_tokens_ws_user_active
    ON mcp_tokens (workspace_id, user_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_mcp_tokens_expires_active
    ON mcp_tokens (expires_at) WHERE revoked_at IS NULL;
```

### New capability `mcp:issue`

Added to the capability enumeration in EP-00. Workspace admins receive it by default. Superadmin implicit.

### No other schema changes

Everything else is read-only projection over existing tables.

---

## 5. Security Approach

Security-by-design checklist applied:

1. **Threat model**
   - Token theft → argon2id + short TTL + rotation UX + revocation < 5 s
   - Cross-workspace data leak → token binding + service-layer authz + integration tests
   - Enumeration → `-32003` default, `-32002` only in safe cases
   - Payload DoS → size caps, pagination, truncation with flag
   - Puppet authz drift → server-side post-filter
   - Log/audit injection → strict sanitization of client-supplied metadata
   - SSE session exhaustion → per-pod caps, idle timeout, subscription caps
   - Prompt-injection via content relayed to agents → content labeled untrusted; no server-side interpretation

2. **Input validation**: every tool input is a Pydantic model; the framework rejects malformed payloads before the handler runs.

3. **Auth**: single scope, single workspace, argon2id hashed, HMAC lookup key, Redis-cached verification with explicit invalidation, 30-day default TTL, 90-day max, 10-token per-user-per-workspace limit.

4. **Authz**: delegated to application layer; MCP layer is a pass-through.

5. **Audit**: every invocation produces an immutable `mcp.invocation` event with token_id, tool, params_hash, duration, status, error_code, client identity.

6. **Observability**: Prometheus metrics, structured logs with redacted bearer headers, trace spans spanning auth → service → response.

7. **Rate limiting**: per-token + per-IP, shared with REST.

---

## 6. Testing Strategy

### Unit

- Pydantic schema validation — happy + rejection cases
- Error mapping layer — one case per service exception class
- Cursor signing / verification
- argon2id verification with known-vector fixture

### Integration (per tool, mandatory)

For each tool:
1. Happy path — returns expected shape
2. **Cross-workspace forbidden** — asserts `-32003` for an id in another workspace (mandatory, enforced in code review)
3. Pagination — cursor round-trip, `limit` clamping
4. Authz edge — missing capability returns `-32003` or omits fields per spec
5. Error mapping — service exception correctly translates

### E2E (CI `e2e-mcp` job)

- Stdio transport: launch server, run `initialize` + `tools/list` + one call for each tool family
- HTTP transport: same over `POST /mcp`
- SSE subscribe: subscribe to `workitem://<id>`, trigger an update via REST API in the same CI env, assert notification within 3 s
- Snapshot test of `tools/list` output — any change requires reviewer confirmation

### Load

- 1k concurrent SSE subscriptions per pod — stable memory under 512 MB
- 200 RPS sustained on `workitem.get` — p95 under 150 ms with warmed caches
- Puppet outage simulation — `semantic.search` degrades to `-32010` without cascading failures

### Security

- Enumeration test: compare response times/bodies between unauthorized and not-found — must be indistinguishable for hidden-existence cases
- Token revocation latency test: revoke then call; assert rejection within 5 s
- argon2id timing consistency: 100 samples, verify std-dev within budget

---

## 7. Observability

### Metrics

- `mcp_tool_duration_seconds{tool}` — histogram, p50/p95/p99 per tool
- `mcp_tool_errors_total{tool, code}` — counter
- `mcp_sessions_active{transport}` — gauge
- `mcp_subscriptions_active` — gauge
- `mcp_sse_bridge_lag_ms` — histogram
- `mcp_token_cache_hits_total` / `mcp_token_cache_misses_total` — counters
- `mcp_token_verifications_total{result}` — counter
- `mcp_audit_queue_drops_total` — counter (alert > 0)
- `mcp_upstream_errors_total{upstream}` — counter
- `mcp_rate_limit_rejections_total{scope}` — counter

### Logs

- Structured JSON, correlation id per session + per request
- Never log bearer tokens, plaintext secrets, or raw request bodies
- Sample successful traces at 10%; log all errors

### Alerts

- `mcp_audit_queue_drops_total > 0` for 1 minute
- `mcp_sse_bridge_lag_ms` p95 > 2 s for 5 minutes
- `mcp_token_verifications_total{result="failed"}` spike > 10× 7-day baseline
- `/mcp/health` readiness failing > 2 minutes
- Puppet upstream error rate > 20% for 5 minutes

---

## 8. Rollout Plan

1. **Internal alpha** — enable for superadmin-issued tokens, Claude Code local stdio only. Read a subset of tools (user.me, workitem.get, workitem.search). Soak for 1 week.
2. **Closed beta** — admin UI for token issuance; enable HTTP/SSE transport in staging; all tools; subscriptions. Soak 2 weeks with 3 pilot workspaces.
3. **GA** — feature flag flip per workspace. Monitor metrics. Document public tool catalog.
4. **Follow-up epic** — write / mutation tools.

Rollback: flag per workspace; kill switch disables MCP auth globally (rejects all tokens with `-32001`). REST API unaffected.

---

## 9. Open Risks

- **MCP SDK maturity**: the official Python SDK is young; expect patches. Pin version; vendor critical fixes if needed.
- **Schema drift** still possible if a service returns untyped dicts; mitigated by code-review rule "MCP tool must consume a typed service return".
- **Audit queue backpressure**: if Celery is unavailable the fallback log must be surveilled; alert configured.
- **Puppet SLA**: `semantic.search` is only as reliable as Puppet. Document expected availability to MCP clients.

---

## 10. Dependencies (Planning Order)

1. EP-00 — token model extension (`mcp_tokens`, capability `mcp:issue`)
2. EP-12 — rate limiter, audit queue, SSE bus (already present; ensure consumer API is stable)
3. EP-01 / EP-04 / EP-05 / EP-06 / EP-07 — service read methods already exposed to REST
4. EP-08 — inbox service read access
5. EP-09 — dashboard aggregator service
6. EP-10 — admin surface for token management UI
7. EP-11 — jira snapshot read
8. EP-13 — Puppet client

No new cross-epic dependencies are introduced.
