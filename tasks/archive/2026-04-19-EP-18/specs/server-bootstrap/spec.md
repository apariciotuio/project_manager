# EP-18 · Capability 2 — MCP Server Bootstrap

> **Addendum (Round-2 reviews, 2026-04-14)**:
> - **[S-M2]** `params_hash` uses **HMAC-SHA256** with a dedicated audit-pepper secret (`MCP_AUDIT_PEPPER`), not raw SHA-256. Canonical JSON (sorted keys, UTF-8) → HMAC. Plain SHA-256 is rainbow-tableable on low-entropy inputs like `workitem.get({id})` where the id space is enumerable.
> - **[A-M5]** Audit queue backpressure policy:
>   - `mcp_audit_queue_drops_total > 0` is an **error-level alert** (not a metric footnote); PagerDuty integration mandatory.
>   - The synchronous structured-log line carries **every field** of the async audit event; downstream tooling can reconstruct audit from logs if Celery is down. Field parity asserted by test.
>   - Add a **bounded local disk spool** (`/var/spool/mcp-audit/`, capped at 256 MB, fsync-optional) before the in-memory deque's drop-oldest kicks in. Spool is drained by a background worker when the queue recovers.

## Scope

The MCP server process itself: transports (stdio + HTTP/SSE), initialization handshake, discovery (`tools/list`, `resources/list`), error mapping, rate limiting wiring, audit emission, health and metrics. No business tools yet — this capability provides the chassis on which capabilities 3/4/5 plug.

## In Scope

- New process `apps/mcp-server/` with its own Dockerfile + Helm entry
- MCP SDK (official Python SDK) hosting both stdio and HTTP/SSE transports
- Auth middleware calling `MCPTokenVerifyService` (capability 1)
- Central request context `{ actor_id, workspace_id, token_id, client_name?, client_version? }`
- Tool/resource registry with schema + deprecation metadata
- Uniform error mapping layer (service exception → JSON-RPC error)
- Rate limiting shared with REST (EP-12 limiter backend, per-token + per-IP)
- Audit event emission for every call (`mcp.invocation`)
- `/mcp/health` liveness + readiness
- `/metrics` Prometheus endpoint (cluster-internal)
- CI: new `e2e-mcp` job (stdio + HTTP smoke)

## Out of Scope

- Specific business tools (capabilities 3/4/5)
- Write/mutation capability
- Public internet exposure policies beyond cluster ingress (covered in EP-12)

## Scenarios

### Transport & Handshake

- WHEN a client connects via `stdio` AND sends `initialize` with a valid token in the first payload THEN the server responds with `{ protocolVersion, serverInfo, capabilities: { tools: {}, resources: { subscribe: true }, logging: {} } }`
- WHEN a client connects via `POST /mcp` (HTTP JSON-RPC) with `Authorization: Bearer mcp_...` THEN the server verifies the token, sets request context, and dispatches
- WHEN a client opens `GET /mcp/sse` THEN the server verifies the token, upgrades to SSE, and the stream stays open to receive resource-update notifications for subscriptions issued on the same session
- WHEN no `initialize` is received within 30 s on stdio THEN the server closes the connection with reason `initialize_timeout`
- AND the server SHOULD accept at most 100 concurrent HTTP+SSE sessions per pod; extras are rejected with `503 Service Unavailable`

### Auth Enforcement

- WHEN any request arrives without a token THEN the server returns JSON-RPC error `-32001 unauthorized` and closes the connection (stdio) or responds 401 (HTTP single-call)
- WHEN the token verification returns `UnauthenticatedError` (expired/revoked/invalid) THEN the same `-32001` is returned
- WHEN the token's scopes do not include `mcp:read` THEN return `-32003 forbidden`
- AND the session's `{ actor_id, workspace_id }` is immutable for the lifetime of the connection

### Discovery

- WHEN a client calls `tools/list` THEN the server returns every registered tool with `{ name, description, inputSchema, outputSchema, deprecated?, replaced_by?, sunset_at? }` sorted alphabetically
- WHEN a client calls `resources/list` THEN the server returns registered URI templates with `{ uri_template, description, mimeType, subscribable }`
- WHEN a client calls `prompts/list` THEN the server returns an empty list (no prompts in MVP)
- AND `tools/list` is cached in-memory (registry is static per process); response is computed once per process start

### Error Mapping

- WHEN a handler raises `UnauthenticatedError` THEN the response is `-32001`
- WHEN a handler raises `ForbiddenError` or the caller accesses data outside their workspace THEN the response is `-32003`
- WHEN a handler raises `NotFoundError` on a resource the caller otherwise has permission to read THEN the response is `-32002`; in all other cases return `-32003`
- WHEN a handler raises `ValidationError` THEN the response is `-32602` with `data.details` (safe field names, never raw exception text)
- WHEN a handler raises `RateLimitedError` THEN the response is `-32005` with `data.retry_after_ms`
- WHEN a handler raises `UpstreamUnavailableError` (Puppet, Jira) THEN the response is `-32010` with `data.upstream`
- WHEN a handler raises a generic exception or exceeds a hard timeout (10 s) THEN the response is `-32603 internal` or `-32011 timeout` respectively — stack traces MUST NOT appear in `data`

### Rate Limiting

- WHEN a token exceeds `MCP_PER_TOKEN_RPS` (default 20 RPS, burst 60) THEN calls are rejected with `-32005` and `data.retry_after_ms`
- WHEN an IP exceeds `MCP_PER_IP_RPS` (default 200 RPS, burst 400) THEN calls are rejected with `-32005`
- AND limits share the EP-12 Redis limiter backend; counters scoped under `rl:mcp:token:<id>` and `rl:mcp:ip:<ip_hash>`
- AND SSE keepalive traffic does not count against the limit

### Audit Emission

- AND every tool/resource invocation emits an `mcp.invocation` audit event with `{ actor_id, workspace_id, tool_or_resource, params_hash, duration_ms, result_bytes, status, error_code?, client_name?, client_version?, token_id }`
- AND `params_hash` is sha256 of canonical JSON (sorted keys, UTF-8)
- AND audit emission is fire-and-forget to a Celery queue; on queue unavailability the server logs a local warning and proceeds — the primary response MUST NOT be blocked
- AND synchronous invocation log entry (structured log line) is always written for reconstruction if the queue is down

### Health & Metrics

- WHEN `GET /mcp/health` is called THEN it returns `200 OK` with `{ status: "ok", uptime_s, version, transports: ["stdio", "http+sse"] }` if process is healthy
- WHEN readiness check (Redis + Postgres ping) fails THEN `/mcp/health` returns `503` with `status: "degraded"` and which dep failed
- WHEN `GET /metrics` is called from inside the cluster THEN Prometheus exposition includes per-tool latency histograms, error counters by code, active SSE sessions, tokens cache hit ratio, Puppet upstream errors, Celery audit queue backlog
- AND `/metrics` is not exposed via public ingress

### Versioning & Deprecation

- AND a tool can be registered with `deprecated: true, replaced_by: "v2.<tool>", sunset_at: <iso>`
- AND a deprecated tool still functions until `sunset_at`; clients receive a warning log entry in server logs on use
- AND breaking schema changes bump to `v2.<tool>` co-existing for ≥ 30 days

## Security (Threat → Mitigation)

| Threat | Mitigation |
|---|---|
| Unauthenticated JSON-RPC batch requests bypassing auth | Auth middleware runs before batch unpacking; every sub-request inherits the session's actor/workspace |
| SSE connection hijack / cross-origin | CORS locked to allowlisted origins; SSE requires bearer token at connect; tokens never in query strings |
| DoS via many idle SSE sessions | Per-pod concurrency cap (100); idle timeout (30 min no messages → close) |
| Log injection via client-supplied `client_name`/`client_version` | Sanitized (alphanumeric + `.-_ ` only), truncated to 64 chars |
| Audit queue backpressure causing OOM | Bounded in-memory dropbox (1000 events); on overflow drop oldest and increment `audit_drops_total` metric with alert |
| Stack trace leak via `-32603` | `data` field is a fixed dict `{ error_id }`; full stack goes to server logs only |
| Timing side-channel on auth failures | Constant-time auth path; failure response returned after fixed minimum latency (1 ms jitter) |
| Prompt injection content in tool descriptions to mislead agents | Tool descriptions are static, developer-authored, code-reviewed; client-supplied content never ends up in `tools/list` |
| Stdio server inherited env leaking | Child processes (none expected) run with scrubbed env; server never spawns subprocesses |

## Non-Functional Requirements

- Process startup < 3 s
- `tools/list` response < 20 ms (in-memory)
- Per-tool request overhead (auth + audit) < 10 ms on top of service time
- Memory footprint stable under 512 MB with 100 SSE sessions
- Container image < 250 MB compressed
