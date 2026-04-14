# EP-18 · Capability 1 — Auth & Token Lifecycle

## Scope

MCP-specific identity artifact on top of EP-00: a new token kind (`mcp_token`) with scope `mcp:read`, bound to a single workspace, issued/rotated/revoked by workspace admins, verified by the MCP server on every request. Includes an admin UI for lifecycle management and audit visibility.

## In Scope

- DB table `mcp_tokens`, argon2id-hashed secret
- New capability `mcp:issue` (workspace-scoped); superadmin implicit
- Services: `MCPTokenIssueService`, `MCPTokenVerifyService`, `MCPTokenRevokeService`, `MCPTokenRotateService`
- REST endpoints under `/api/v1/admin/mcp-tokens/*`
- Verification cache (Redis, 5s TTL) for revocation responsiveness without hot-path DB hit
- Admin UI: list, issue (plaintext shown **once**), revoke, rotate, view audit of recent uses
- Audit events `mcp_token.*`

## Out of Scope

- Multi-workspace tokens (never)
- Fine-grained scopes (`mcp:read:workitems` etc.) — single scope MVP
- User self-service token issuance — admin-issued only in MVP
- Token-to-token delegation

## Scenarios

### Issuance

- WHEN a user with capability `mcp:issue` calls `POST /api/v1/admin/mcp-tokens` with `{ user_id, name, expires_in_days? }` THEN the service validates `expires_in_days ≤ 90` (default 30), creates a row with argon2id hash, and returns `{ id, plaintext_token, name, expires_at }` — plaintext is returned **only on this response**
- WHEN a user without `mcp:issue` calls the endpoint THEN the server returns `403 Forbidden`
- WHEN the target `user_id` is not a member of the caller's workspace THEN the server returns `400 validation_error` with code `USER_NOT_IN_WORKSPACE`
- WHEN a user already holds 10 active (non-revoked, non-expired) tokens for the workspace THEN the endpoint returns `409 Conflict` with code `TOKEN_LIMIT_REACHED` — admin may override by first revoking an existing token
- AND the plaintext token format is `mcp_<base64url-32bytes>` (detectable by secret scanners)

### Listing & Audit

- WHEN an admin calls `GET /api/v1/admin/mcp-tokens?user_id=?&include_revoked=?` THEN the server returns paginated tokens with `{ id, user_id, name, created_at, expires_at, last_used_at, last_used_ip, revoked_at?, created_by }` — **never the hash**
- WHEN a non-admin calls `GET /api/v1/admin/mcp-tokens/mine` THEN the server returns the caller's own tokens with the same metadata (no plaintext, no hash)
- AND `last_used_at` / `last_used_ip` are updated asynchronously (fire-and-forget Celery task); best-effort; write skipped if latency > 50ms

### Revocation

- WHEN an admin calls `DELETE /api/v1/admin/mcp-tokens/:id` THEN `revoked_at = now()` is set atomically and the server responds `204`
- WHEN a token is revoked THEN the next MCP request presenting it is rejected within **5 seconds** (verification cache TTL)
- WHEN a user revokes their own token via `/mine/:id` THEN the server allows it without `mcp:issue`
- AND revoking an already-revoked token is idempotent (`204`)

### Rotation

- WHEN an admin calls `POST /api/v1/admin/mcp-tokens/:id/rotate` THEN the old token is revoked, a new token with the same `name`, `user_id`, `workspace_id` and a fresh `expires_at` (reset to default TTL) is created, and the plaintext is returned **once**
- AND the rotation emits two audit events: `mcp_token.revoked` then `mcp_token.issued` with `rotated_from: <old_id>` and `rotated_to: <new_id>` cross-reference

### Verification (called by MCP server on every request)

- WHEN the MCP server presents a bearer token to `MCPTokenVerifyService.verify(plaintext)` THEN the service computes the lookup key (HMAC of the plaintext with a server pepper), finds the row, verifies the argon2id hash, checks `revoked_at IS NULL` and `expires_at > now()`
- WHEN verification succeeds THEN the service returns `{ actor_id, workspace_id, scopes, token_id }` and caches it under `mcp:token:<token_id>` with TTL 5s
- WHEN any check fails THEN the service raises `UnauthenticatedError` and the failure is logged **without** the plaintext
- WHEN a cache hit exists AND `revoked_at` is still NULL in cache payload THEN the cached result is returned without DB hit
- WHEN a token is revoked THEN the row's `revoked_at` change propagates via cache invalidation (key delete on revoke)
- AND verification MUST complete in < 50 ms p95 (argon2id cost tuned accordingly — not the login-hardening profile)

## Security (Threat → Mitigation)

| Threat | Mitigation |
|---|---|
| Plaintext token leaked in logs | Verification layer redacts the `Authorization` header; service logs carry only `token_id` never plaintext |
| Offline brute force of stolen DB dump | argon2id with workspace-appropriate cost; HMAC pepper stored outside DB in secrets manager |
| Timing attack on token lookup | Constant-time HMAC lookup key + `argon2id.verify`; reject-fast only after both steps |
| Revocation delay longer than SLO | Cache TTL = 5s; explicit cache DEL on revoke; verification path reads cache-or-DB not cache-only |
| Enumeration of valid `token_id` via error differences | Uniform `UnauthenticatedError` with identical response body for any failure |
| Abuse of `mcp:issue` to mint tokens for other users | `user_id` must be a member of the caller's workspace; audit event records both `issued_to` and `issued_by`; superadmin actions additionally flagged |
| Stale `last_used_at` exposing compromised token use late | Async update budget 50ms; if exceeded, drop — but audit event for the MCP call is always emitted synchronously (synchronous audit is the authoritative trail) |
| Token format misidentified by scanners | Prefix `mcp_` + fixed length + base64url; publish regex in docs for secret-scanning integrations |

## Non-Functional Requirements

- Verification p95 < 50 ms, p99 < 150 ms (argon2id tuned to this budget, **not** the login profile)
- Revocation propagation ≤ 5 s end-to-end
- Admin endpoints p95 < 300 ms
- DB: `mcp_tokens` indexed on `(lookup_key)` unique, `(workspace_id, user_id, revoked_at)` for listing
