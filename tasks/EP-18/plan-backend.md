# EP-18 Backend Implementation Plan

Blueprint for `develop-backend`. Layered DDD decomposition. Each step cites the WHEN/THEN/AND scenario it satisfies and names the boundary tested.

**Stack**: FastAPI · Python 3.12 · SQLAlchemy 2 · Alembic · Postgres 16 · Redis 7 · Celery · argon2-cffi · official **MCP Python SDK** · Pydantic v2.

**Packages (existing monorepo convention)**

- `packages/domain/` — entities, value objects, domain exceptions, pure logic
- `packages/application/` — services, DTOs, orchestration
- `packages/infrastructure/` — repositories, adapters, Redis, Celery publishers
- `packages/schemas/` — Pydantic models shared by REST + MCP
- `apps/api/` — existing FastAPI REST app
- `apps/mcp-server/` — **new** MCP server process

**Legend**
- `[S:<cap>/spec.md#scenarios:<line>]` → spec scenario citation
- `[T:<kind>]` → test kind: unit / integration / e2e / load / security

Every step follows `RED → GREEN → REFACTOR`.

---

## 0. Pre-flight

### 0.1 Shared schema module

**Why**: prevent REST/MCP drift. Single Pydantic source.

- Create `packages/schemas/mcp/` with `__init__.py` empty (per backend standards)
- Move `WorkItemDetail`, `WorkItemSummary`, `CommentDTO`, `VersionDTO`, `ReviewDTO`, `ValidationDTO`, `TimelineEventDTO`, `AssistantMessageDTO`, `SemanticSearchResult`, `TagDTO`, `LabelDTO`, `AttachmentMetadataDTO`, `InboxItemDTO`, `DashboardDTO`, `JiraSnapshotDTO` here — if duplicates exist in `apps/api/`, replace with imports
- Add `schema_version: Final[str]` constant with a CI guard: any change to a shared model without bumping the constant fails CI

[T:unit] snapshot of Pydantic `model_json_schema()` per DTO — diff forces review.

### 0.2 Branch + CI

- Branch `feature/EP-18-mcp-read`
- Add CI job `e2e-mcp` (runs only on `apps/mcp-server/**` or `packages/schemas/**` touches)
- Add `e2e-mcp-stdio` + `e2e-mcp-http` smoke matrix

---

## 1. Capability 1 — Auth & Token Lifecycle

Target spec: `specs/auth-and-tokens/spec.md`

### 1.1 Domain layer

**Entity `MCPToken`** (`packages/domain/mcp/token.py`)

Fields: `id, workspace_id, user_id, name, lookup_key: bytes, secret_hash: str, scopes: list[str], created_by, created_at, expires_at, last_used_at?, last_used_ip?, revoked_at?`

Invariants (pure, enforced in `__init__` or factory):
- `expires_at > created_at`
- `(expires_at - created_at) <= 90 days`
- `scopes` non-empty, subset of known set
- `name` 1..80 chars, printable

Methods:
- `is_active(now) -> bool`
- `revoke(now) -> None` (raises `AlreadyRevokedError` only if caller needs it; the service absorbs idempotency)

[T:unit] `test_mcptoken_invariants` — boundary values on expiry, name length, empty scopes.

**Value object `MCPPlaintextToken`** (`packages/domain/mcp/plaintext.py`)

Immutable wrapper with:
- `value: str`
- Regex validated: `^mcp_[A-Za-z0-9_-]{43}$`
- `__repr__` redacts: `MCPPlaintextToken(mcp_****)` — protects accidental logs

[T:unit] `test_plaintext_repr_never_leaks_value`.

**Domain exceptions** (`packages/domain/mcp/exceptions.py`)

- `TokenNotFoundError`
- `TokenRevokedError`
- `TokenExpiredError`
- `TokenScopeMismatchError`
- `TokenLimitReachedError`
- `TokenUserNotInWorkspaceError`

All inherit from a base `MCPAuthError` and from the shared `UnauthenticatedError` / `ForbiddenError` / `ValidationError` hierarchy used elsewhere — so the existing error mapper covers them.

### 1.2 Infrastructure layer

**Repository `MCPTokenRepository`** (`packages/infrastructure/persistence/mcp_token_repo.py`)

Interface (in `packages/domain/mcp/repository.py`):
```python
class MCPTokenRepository(Protocol):
    async def add(self, token: MCPToken) -> None: ...
    async def get_by_id(self, token_id: UUID) -> MCPToken | None: ...
    async def get_by_lookup_key(self, key: bytes) -> MCPToken | None: ...
    async def list_by_user(self, ws_id: UUID, user_id: UUID, *, include_revoked: bool) -> list[MCPToken]: ...
    async def count_active_for_user(self, ws_id: UUID, user_id: UUID) -> int: ...
    async def mark_revoked(self, token_id: UUID, now: datetime) -> bool: ...
    async def touch_last_used(self, token_id: UUID, now: datetime, ip: IPv4Address | IPv6Address | None) -> None: ...
```

Implementation uses SQLAlchemy Core (not ORM on hot path — verification is hot).

**Mapper** `MCPTokenMapper` — bidirectional between `mcp_tokens` row and `MCPToken` entity.

**Alembic migration** `revision = "ep18_mcp_tokens"`:
```sql
CREATE TABLE mcp_tokens ( ... )  -- as in design.md §4
CREATE UNIQUE INDEX ... ON mcp_tokens(lookup_key)
CREATE INDEX idx_mcp_tokens_ws_user_active ON mcp_tokens(workspace_id, user_id) WHERE revoked_at IS NULL
CREATE INDEX idx_mcp_tokens_expires_active ON mcp_tokens(expires_at) WHERE revoked_at IS NULL
```

[T:integration] `test_migration_round_trip` — upgrade then downgrade succeeds.

**Adapter `TokenHasher`** (`packages/infrastructure/security/token_hasher.py`)

- `hmac_lookup_key(plaintext: MCPPlaintextToken, pepper: bytes) -> bytes` — HMAC-SHA256
- `hash_secret(plaintext) -> str` — argon2id with parameters tuned for 10–20 ms on reference hardware (t=2, m=32 MiB, p=1 is a starting point; benchmark in CI)
- `verify_secret(plaintext, hash) -> bool`

Pepper read from env `MCP_TOKEN_PEPPER` (base64, 32 bytes). Missing pepper at boot → fail-fast.

[T:unit]
- `test_hmac_is_deterministic_same_pepper`
- `test_hmac_differs_across_peppers`
- `test_argon2_verify_matches_hash_within_budget` (timing bound p95 ≤ 20 ms)
- `test_boot_aborts_when_pepper_missing`

**Adapter `TokenSecretGenerator`** (`packages/infrastructure/security/token_secret.py`)

- `generate() -> MCPPlaintextToken` — `secrets.token_urlsafe(32)` → 43 chars base64url → prefix `mcp_`

[T:unit] `test_generated_token_matches_plaintext_regex`.

**Adapter `MCPTokenCache`** (`packages/infrastructure/cache/mcp_token_cache.py`)

Backed by existing Redis client (EP-12).

Keys: `mcp:token:<token_id>` with 5 s TTL.
Value: JSON `{ actor_id, workspace_id, scopes, expires_at_iso }`.

Methods:
- `get(token_id)` / `put(token_id, payload)` / `delete(token_id)`

[T:integration] `test_cache_ttl_5_seconds_eviction` — real Redis via testcontainers.

### 1.3 Application layer

All services take `actor_context: ActorContext` (existing pattern) from the REST dependency.

**`MCPTokenIssueService.execute(cmd: IssueTokenCommand) -> IssueTokenResult`**

Command: `{ actor_id, workspace_id, target_user_id, name, expires_in_days? }`.

Flow:
1. Authz: `actor_context` must hold `mcp:issue` on `workspace_id` OR be superadmin
2. Validate `expires_in_days` (default 30, max 90) — `ValidationError` otherwise → `[S:auth/issuance]`
3. Verify target is member of workspace — else `TokenUserNotInWorkspaceError`
4. Check active-token count ≤ 9 — else `TokenLimitReachedError` → `[S:auth/issuance]`
5. Generate plaintext via `TokenSecretGenerator`
6. Compute `lookup_key` and `secret_hash`
7. Build `MCPToken` entity; repository `add`
8. Publish audit `mcp_token.issued { token_id, issued_to, issued_by, workspace_id, expires_at }`
9. Return `IssueTokenResult(token_id, plaintext: MCPPlaintextToken, expires_at)` — **only time plaintext crosses service boundary**

[T:unit] happy path with fakes.
[T:integration] DB + Redis; assert audit event published; assert only return path carries plaintext.

**`MCPTokenVerifyService.verify(plaintext: str) -> VerifiedIdentity`**

Flow (order matters):
1. Parse into `MCPPlaintextToken` — regex reject → `UnauthenticatedError`
2. Compute `lookup_key` (HMAC)
3. Cache lookup by token_id? not possible without token_id. Instead:
   - Repo `get_by_lookup_key` (indexed unique) → `MCPToken | None`
   - If `None` → `UnauthenticatedError`
4. Cache check `cache.get(token.id)`:
   - HIT → validate `revoked_at IS NULL` in cached value; if revoked → `UnauthenticatedError`; else return cached `VerifiedIdentity`
   - MISS → continue
5. `argon2.verify_secret` → mismatch → `UnauthenticatedError`
6. Active checks: `revoked_at is None`, `expires_at > now()`, `"mcp:read" in scopes` → else appropriate error
7. `cache.put(token.id, payload)` with 5 s TTL
8. Enqueue fire-and-forget `touch_last_used(token_id, now, ip)` Celery task
9. Return `VerifiedIdentity(actor_id, workspace_id, scopes, token_id)`

All failure modes go through a **uniform response path** — fixed latency floor (1 ms jitter) to dampen timing side-channel → `[S:auth/verification:security]`.

[T:unit] table-driven over all failure modes.
[T:integration]
- `test_verify_returns_from_cache_on_second_call_no_db` (count DB queries)
- `test_verify_rejects_within_5s_after_revoke` (real Redis, real DB)
- `test_verify_constant_time_distribution` (statistical)
[T:security] enumeration indistinguishability.

**`MCPTokenRevokeService.execute(cmd: RevokeTokenCommand) -> None`**

Authz: `mcp:issue` or owner-of-token (self-service).
Steps: repo `mark_revoked` (idempotent — UPDATE returning count); on first revoke emit audit; always `cache.delete(token_id)`.

[T:unit] idempotency + cache delete on both first and subsequent calls.

**`MCPTokenRotateService.execute(cmd: RotateTokenCommand) -> IssueTokenResult`**

Transactionally:
- Revoke old (emit `mcp_token.revoked { rotated_to: <pending> }`)
- Issue new (emit `mcp_token.issued { rotated_from: <old_id> }`)
- Both audit events correlated via a `rotation_id` (uuid4)

[T:integration] two events emitted with matching `rotation_id`, old token caches invalidated, new plaintext returned once.

**`MCPTokenListQuery.execute(query: ListTokensQuery) -> Page[TokenSummary]`**

Pagination: offset or cursor-based. Use the shared cursor helper from EP-09.

[T:integration] workspace isolation — admin from WS_A cannot see WS_B tokens.

### 1.4 Presentation layer — REST admin endpoints

Location: `apps/api/presentation/controllers/admin/mcp_tokens.py`

Routes (all under `/api/v1/admin/mcp-tokens` + `/api/v1/admin/mcp-tokens/mine` for self-service):

| Method | Path | Service |
|---|---|---|
| POST | `/` | IssueService |
| GET | `/` | ListQuery (filter by user_id, include_revoked) |
| DELETE | `/{id}` | RevokeService |
| POST | `/{id}/rotate` | RotateService |
| GET | `/mine` | ListQuery (scoped to actor) |
| DELETE | `/mine/{id}` | RevokeService (self) |

Response bodies use `success` envelope `{ data, message }` per backend standards.

[T:integration] per route — happy path + 401 + 403 + 409 (limit) + 400 (validation) + cross-workspace isolation.

### 1.5 Security (layered)

| Layer | Control |
|---|---|
| Domain | Invariants on TTL, name, scope |
| Infra | argon2id with tuned cost; HMAC pepper from secrets; no plaintext in DB |
| Application | Uniform error responses; fixed-latency failure path; audit on every state-changing op |
| Presentation | Bearer redaction in access logs; `Cache-Control: no-store` on issuance responses; OpenAPI `secret: true` on response.plaintext field |

---

## 2. Capability 2 — MCP Server Bootstrap

Target spec: `specs/server-bootstrap/spec.md`

### 2.1 Application context

`MCPServerSession` (in-memory, per connection):
```python
@dataclass(frozen=True, slots=True)
class MCPServerSession:
    actor_id: UUID
    workspace_id: UUID
    token_id: UUID
    scopes: tuple[str, ...]
    client_name: str | None
    client_version: str | None
    transport: Literal["stdio", "http", "sse"]
    connected_at: datetime
```

Immutable post-`initialize`. Stored in SDK-provided context; retrieved in every handler via helper `current_session()`.

### 2.2 Middleware stack (composition order)

1. **Transport adapter** (SDK) — decodes JSON-RPC
2. **Auth** — `verify(plaintext) → session`; stores into context
3. **Rate limiter** — `rl:mcp:token:<id>` and `rl:mcp:ip:<hash>` token buckets
4. **Audit wrapper** — wraps dispatch; times; emits `mcp.invocation` on success/failure
5. **Error mapper** — converts raised exceptions to JSON-RPC errors
6. **Dispatch** — registry lookup → handler

[T:unit] per middleware unit with the next one mocked (boundary tests).
[T:integration] composed stack — auth failure never reaches rate limiter; rate limit never reaches audit-emit-before-limit check; etc.

### 2.3 Registry

`ToolRegistry` and `ResourceRegistry` — module-level singletons populated by `@register_tool(name=..., input_schema=..., output_schema=..., deprecated=False, replaced_by=None, sunset_at=None)` decorators.

[T:unit] `test_registry_rejects_duplicate_names`.
[T:integration] snapshot test: `tools/list` output against `docs/mcp-tools-snapshot.json`; updating snapshot requires reviewer sign-off (enforce via CODEOWNERS on the snapshot file).

### 2.4 Error mapper

Single `map_exception(exc) → JsonRpcError` function. Table-driven.

| Exception | Code | Name |
|---|---|---|
| `UnauthenticatedError` | -32001 | unauthorized |
| `ForbiddenError` | -32003 | forbidden |
| `NotFoundError` (whitelisted callers) | -32002 | not_found |
| `ValidationError` | -32602 | invalid_params |
| `RateLimitedError` | -32005 | rate_limited |
| `UpstreamUnavailableError` | -32010 | upstream_unavailable |
| `TimeoutError` | -32011 | timeout |
| `ConflictError` | -32009 | conflict |
| default | -32603 | internal |

`data` dict fixed shape per code. Stack traces **never** populated — only `error_id` (uuid4) that correlates to server logs.

[T:unit] one case per class.
[T:security] `test_error_data_never_contains_stack_trace_or_sql`.

### 2.5 Audit emitter

`AuditPublisher` wraps Celery `app.send_task("mcp.invocation", ...)`. In-memory bounded dropbox (`deque(maxlen=1000)`) with background drain loop. On overflow: drop oldest, increment `mcp_audit_queue_drops_total`.

Synchronous structured-log line always written via `logger.info("mcp.invocation", extra=...)` — the async Celery event is the primary audit record, the log line is the fallback.

[T:integration] `test_audit_fires_and_forgets_when_celery_unavailable` — response latency unaffected.
[T:integration] `test_audit_drops_on_overflow_and_increments_metric`.

### 2.6 Rate limiter

Reuse `packages/infrastructure/rate_limit/token_bucket.py` (EP-12). Two buckets per request: per-token, per-IP. Either exhausted → `RateLimitedError`.

`MCP_PER_TOKEN_RPS=20`, burst 60. `MCP_PER_IP_RPS=200`, burst 400. Env-tunable.

[T:integration] token exhaustion triggers `-32005` with retry-after.

### 2.7 Transports

**Stdio**: SDK default; wire into auth middleware by reading `initialize.params.meta.token` first. Reject after 30 s without `initialize`.

**HTTP JSON-RPC**: FastAPI-independent minimal ASGI app under Uvicorn on port `MCP_LISTEN_HTTP`. Endpoints: `POST /mcp`, `GET /mcp/sse`, `GET /mcp/health`, `GET /metrics`.

**SSE**: hand-rolled (SDK supports), bridged to subscriptions (capability 5). Keepalive ping 25 s. Idle-close 30 min.

[T:e2e]
- `e2e-mcp-stdio`: spawn process, write `initialize` + `tools/list`, assert.
- `e2e-mcp-http`: POST `initialize` + `tools/list` + `workitem.get` (needs capabilities 1 and 3 merged).

### 2.8 Health + metrics

`/mcp/health` returns `200 {status:"ok",...}` if Postgres + Redis ping succeed; `503 {status:"degraded"}` otherwise.

`/metrics` exposes histograms/counters enumerated in design §7. Bind only to cluster-internal interface (Uvicorn `--host`).

### 2.9 CI integration

- GitHub Action `e2e-mcp.yml` runs on every PR touching `apps/mcp-server/**` or `packages/schemas/**`
- Contains: unit, integration (Postgres + Redis via services), stdio + HTTP e2e
- Tools-list snapshot diff in CI

### 2.10 Security (layered)

| Layer | Control |
|---|---|
| Transport | CORS allowlist on SSE; bearer required; tokens never in query string |
| Middleware | Auth runs before dispatch; constant-time failure path |
| Dispatch | Registry is static; client cannot register tools |
| Logs | Bearer header redacted; client_name/version sanitized |
| Ops | `/metrics` on cluster-internal interface only |

---

## 3. Capability 3 — Read Tools: Work Items & Content

Target spec: `specs/read-tools-workitem-content/spec.md`

### 3.1 Per-tool pattern (followed for all 12)

```python
# apps/mcp-server/src/mcp_server/tools/workitem/get.py
from packages.schemas.mcp import WorkItemDetail, WorkItemGetInput
from packages.application.workitem.services import WorkItemReadService

@register_tool(
    name="workitem.get",
    input_schema=WorkItemGetInput,
    output_schema=WorkItemDetail,
)
async def workitem_get(inp: WorkItemGetInput) -> WorkItemDetail:
    s = current_session()
    svc: WorkItemReadService = container.get(WorkItemReadService)
    return await svc.get(
        actor_id=s.actor_id,
        workspace_id=s.workspace_id,
        work_item_id=inp.id,
        options=inp.options,
    )
```

Handler is ≤ 30 lines. No repository imports. No raw SQL. No workspace_id from input.

### 3.2 Service method additions

Many service methods already exist for REST. For any missing method:

1. Add to `packages/application/<bounded-context>/services.py`
2. Add repository method if needed (domain interface + infra implementation)
3. Do not re-implement authz — reuse existing decorator `@enforce_read(work_item)` or whatever pattern EP-01 established

Methods to verify / add:

| Tool | Service method expected | Add if missing |
|---|---|---|
| `user.me` | `IdentityService.me(actor_id, ws_id)` | likely exists |
| `workitem.get` | `WorkItemReadService.get(..., options)` | add `options.include_spec_body` |
| `workitem.search` | `WorkItemSearchService.search(filters, cursor, limit)` | ensure filter schema matches spec |
| `workitem.children` | `HierarchyService.direct_children(parent_id)` | likely exists (EP-05) |
| `workitem.hierarchy` | `HierarchyService.hierarchy(node_id)` | extend to include roll-up |
| `workitem.listByEpic` | `HierarchyService.list_by_epic(epic_id, group_by?)` | add if missing |
| `comments.list` | `CommentReadService.list(work_item_id, filters, cursor)` | ensure orphan flag exposed |
| `versions.list` | `VersionReadService.list(...)` | likely exists |
| `versions.diff` | `VersionDiffService.diff(from, to)` | add truncation logic |
| `reviews.list` | `ReviewReadService.list(work_item_id)` | likely exists |
| `validations.list` | `ValidationReadService.list(work_item_id)` | include override fields |
| `timeline.list` | `TimelineReadService.list(work_item_id, filters, cursor)` | add actor_kind merge logic |

Each added/extended service method gets its own TDD cycle **before** the MCP handler is written.

### 3.3 Cursor signing

Shared helper `packages/infrastructure/pagination/cursor.py`:
- Encodes `{ position, filter_hash }` as base64url HMAC-signed payload
- `decode()` verifies signature → `ValidationError("INVALID_CURSOR")` on mismatch

[T:unit] tamper test.
[T:security] sign with key A, verify with key B fails.

### 3.4 Payload truncation

For `workitem.get`:
- If `sum(len(section.body) for section in spec.sections) > 256 KB`:
  - Omit bodies of largest sections until under cap
  - Populate `omitted_section_ids: list[UUID]` and `truncated: true`

For `versions.diff`:
- Per-section body cap 64 KB
- On overflow replace body with `{truncated: true, size_bytes: n}`

[T:unit] on service layer, boundary cases.

### 3.5 Per-tool test matrix

Every tool has exactly:
1. [T:unit] input schema validation
2. [T:integration] happy path with test DB + workspace fixtures
3. [T:integration] **cross-workspace forbidden** (MANDATORY)
4. [T:integration] authz-edge (missing capability)
5. [T:integration] pagination (if applicable)
6. [T:security] enumeration indistinguishability for that tool's hidden-existence case

CI guard: grep for new tool files without corresponding cross-workspace test fails the build.

### 3.6 Security (layered)

| Layer | Control |
|---|---|
| Schema | Input validation rejects unknown fields; enum fields constrained |
| Service | Authz enforced; no workspace_id from caller |
| Tool handler | No repository import (lint rule) |
| Pagination | HMAC-signed cursors |
| Response | Size caps; redaction flags |

---

## 4. Capability 4 — Read Tools: Assistant, Search, Extras

Target spec: `specs/read-tools-assistant-search-extras/spec.md`

### 4.1 Service-layer extensions

| Tool | Service | Action |
|---|---|---|
| `assistant.threads.get` | `AssistantReadService.thread_for_work_item(work_item_id)` | add if missing; cap 200 messages |
| `assistant.threads.workspace` | `AssistantReadService.workspace_threads(ws_id)` | add summary-only variant |
| `semantic.search` | `SemanticSearchService.search(q, filters, include_external)` | wrap Puppet client; server-side post-filter authz |
| `tags.list` | `TagReadService.list(include_archived)` | likely exists |
| `tags.workitems` | `WorkItemSearchService.by_tags(ids, mode)` | add AND/OR |
| `labels.list` | `LabelReadService.list()` | add if missing |
| `attachments.list` | `AttachmentReadService.list_metadata(work_item_id)` | metadata only |
| `attachments.signedUrl` | `AttachmentSignedUrlService.issue(attachment_id, token_id)` | TTL ≤ 5 min, token-bound |
| `inbox.list` | `InboxService.list_for_user(user_id, cursor)` | priority ordering |
| `workspace.dashboard` | `DashboardService.overview(ws_id, caller_capabilities)` | conditional blocks |
| `jira.snapshot` | `JiraExportService.snapshot(work_item_id)` | already exists from EP-11 |

### 4.2 Puppet proxy

**Upstream contract** (from Puppet OpenAPI v0.1.1):

- `POST /api/v1/retrieval/semantic/` — body `QueryRequest { query, categories?: str[], tags?: str[], top_k?: int = 5 }` → `QueryResponse { query, sources: Source[], metadata }`
- `Source { page_id?, title?, content, category?, tags?, score? }` — **no HTML, no highlighting**; content is raw text
- Puppet has **no workspace concept**. Isolation is the platform's responsibility via category conventions.

**Category naming convention** (platform-owned, enforced both at ingestion and at query):
- Workspace content: `tuio-wmp:ws:<workspace_uuid>:workitem`, `:section`, `:comment`
- External Tuio docs: `tuio-docs:*`
- Any `Source` outside those prefixes is dropped defensively.

`SemanticSearchService.search(query, include_external, limit, filters)`:

1. Build `categories` list:
   - Always include `tuio-wmp:ws:<session.workspace_id>:workitem`, `:section`, `:comment`
   - If `include_external` → append `tuio-docs:work-items`, `tuio-docs:adr`, etc. (configurable allowlist)
2. Map caller filters to Puppet `tags` (platform tag_id string form) — unknown/foreign tag ids → `ForbiddenError`
3. `top_k = min(limit, 50)` — Puppet default is 5; we override per request
4. Call Puppet with 3 s timeout → on timeout/5xx → `UpstreamUnavailableError("puppet")`
5. **Category defensive filter**: drop any `Source` whose `category` does not match the requested allowlist (protects against misconfigured ingestion / category-regex bypass)
6. **Authz re-check (critical)**: for every `Source` with a workspace category, resolve `page_id → platform entity id` and call the existing platform read-check; drop on forbidden. For `tuio-docs:*` sources, no entity check (content is intentionally public within Tuio).
7. **Generate `snippet_html` server-side** from `Source.content`:
   - Extract the span around the first query-term match (120 chars)
   - Wrap matches in `<em>`; HTML-escape everything else via `bleach` allowlist `{em, strong, br}`
8. Build `results[]` and `facets{}` from the surviving sources (facet aggregation over surviving set, not raw Puppet response)

**Entity ID mapping**. Requires `page_id` to encode platform entity identity for workspace sources. Convention (established at ingestion side, tracked in EP-13 ingestion work): `page_id = "<entity_kind>:<uuid>"` e.g. `workitem:9e7f...`, `section:ab12...`, `comment:c0de...`. Unknown format → drop defensively.

[T:integration]
- `test_semantic_search_scopes_categories_to_session_workspace`
- `test_semantic_search_include_external_adds_tuio_docs_categories`
- `test_semantic_search_drops_sources_with_unknown_category_prefix`
- `test_semantic_search_drops_sources_for_unreadable_platform_entities`
- `test_semantic_search_generates_snippet_from_raw_content_with_em_wrapping`
- `test_semantic_search_sanitizes_snippet_against_xss`
- `test_semantic_search_timeout_returns_minus32010`
- `test_semantic_search_foreign_tag_returns_minus32003`
- `test_semantic_search_on_ws_with_no_ingestion_returns_empty_workspace_results_but_docs_still_work` — **acceptance of the pre-ingestion state**

### 4.2.1 Known limitation during rollout

Puppet's platform-ingestion endpoints are **not yet implemented** (tracked outside EP-18). Until they ship and the platform fans its work items / sections / comments into Puppet under `tuio-wmp:ws:<uuid>:*`:

- `semantic.search` with `include_external: false` (default) returns `results: []` on workspace content — behavior is correct, just empty
- `semantic.search` with `include_external: true` returns useful Tuio-docs results
- Tool description and user-facing docs MUST state this explicitly so agents don't misinterpret empty results as "nothing matches"
- No client changes are required when ingestion goes live — the same tool starts returning workspace content automatically

### 4.3 Signed URL for attachments

`AttachmentSignedUrlService.issue(attachment_id, token_id) -> SignedUrl`:
- Verify caller can read attachment
- Generate URL with HMAC signature encoding `{attachment_id, token_id, expires_at}`
- Download endpoint validates signature AND that presenter's token_id matches signed token_id → replay by another token fails

TTL ≤ 300 s. Stored in Redis for single-use enforcement (optional post-MVP).

[T:security]
- `test_signed_url_replay_with_different_token_rejected`
- `test_signed_url_expired_rejected`

### 4.4 Dashboard conditional blocks

`DashboardService.overview(ws_id, caps)`:
- Always include `workspace_health`
- Include `organizational`, `process`, `integrations` iff caller has `workspace:admin`
- Cache per `(ws_id, "admin"|"member")` for 30 s in Redis

[T:integration]
- Non-admin sees only `workspace_health`
- Admin sees all 4
- Cache invalidation on `workspace:admin:refresh_dashboard` event (future)

### 4.5 Inbox priority ordering

`InboxService.list_for_user(user_id)`:
- Collect candidates from review queue, returned items, blocking dep resolver, decision queue
- Stable-sort by priority rank: pending_reviews(1) < returned_items(2) < blocking_deps(3) < pending_decisions(4)
- Window: last 30 days
- Cursor over (priority_rank, happened_at, id)

[T:integration] `test_inbox_order_matches_spec_priority`.

### 4.6 Security (layered)

| Layer | Control |
|---|---|
| Puppet adapter | Workspace scoping; post-filter authz |
| Attachment service | Token-bound signed URLs; never return binary |
| Dashboard | Conditional fields, not error |
| Schema | HTML sanitization |
| Logs | Never log signed-URL secret portion |

---

## 5. Capability 5 — Resources & Live Subscriptions

Target spec: `specs/resources-subscriptions/spec.md`

### 5.1 Resource providers

`apps/mcp-server/src/mcp_server/resources/workitem.py`, `epic_tree.py`, `workspace_dashboard.py`, `user_inbox.py`.

Each exports:
- `uri_template: str`
- `subscribable: bool`
- `async def read(uri, session) -> ResourceContents`
- if subscribable: `bus_channels: tuple[str, ...]`, `async def matches(event, uri) -> bool`

Registered at startup in `ResourceRegistry`.

### 5.2 SSE bridge

`apps/mcp-server/src/mcp_server/bridge/sse_bridge.py`

Responsibilities:
- Subscribe via Redis pub/sub to EP-12 channels (`workitem.updated`, `inbox.changed`, `lock.*`, `review.*`, `version.*`, `comment.*`, `tag.*`, `dashboard.refresh`, `export.*`)
- For each event: filter by `workspace_id` (drop if not in any active session's workspace)
- For each active session subscribed to a matching URI:
  1. `AuthzGate.can_read(session, uri)` → if false, emit `notifications/resources/unsubscribed` with `reason: "forbidden"` and remove
  2. `Debouncer.record(uri, event)` → emit after 500 ms idle OR immediately if `event.security_relevant`
  3. Push `notifications/resources/updated`

Security-relevant kinds (bypass debounce): `lock.force_released`, `workitem.ownership_changed`, `workitem.visibility_changed`, `tag.archived_affecting_subscription` — list in `bridge/security_events.py`.

**Per-tree throttling**: `epic://<id>/tree` subscription → if > 100 change events/min on the tree, throttle to 1 notification per 10 s; flag next payload with `throttled: true`.

[T:integration]
- `test_bridge_filters_by_workspace_id_parallel_workspaces`
- `test_bridge_debounces_burst_within_500ms`
- `test_bridge_security_relevant_events_bypass_debounce`
- `test_bridge_reauthorizes_before_emit_and_unsubscribes_on_forbidden`
- `test_bridge_throttles_epic_tree_fanout`

[T:load] `mcp_sse_bridge_lag_ms` p95 under 2 s at 100 events/sec.

### 5.3 Subscription lifecycle

`SubscriptionManager`:
- Per-session `dict[uri, SubscriptionState]`
- Cap 50 subs/session → `RateLimitedError("SUBSCRIPTION_CAP")`
- On client disconnect: purge within 10 s (background sweep)
- On session idle > 30 min with no messages: force close

[T:unit] cap enforcement.
[T:integration] disconnect cleans up.

### 5.4 Epic-tree resource specifics

`read(epic_id)`:
- BFS descendants up to depth 4
- Nodes beyond depth 4: return `{id, type, title, has_more_descendants: true}`
- Total response cap: 1 MB; on overflow truncate and flag

[T:integration] epic with 5-level deep tree returns truncated leaves correctly.

### 5.5 Security (layered)

| Layer | Control |
|---|---|
| Bridge | Workspace filter before authz gate |
| Authz gate | Re-check on every emit |
| Subscription | Cap + idle timeout |
| URI parsing | Templates fixed; unknown URI → `-32602` |
| Security events | Bypass debounce to avoid hiding critical state |

---

## 6. Cross-cutting implementation order

Dependency-respecting execution plan:

1. **0. Pre-flight** — shared schemas, CI job, branch
2. **Cap 1 (Auth & Tokens)** — unblocks everything; REST admin endpoints first for FE parallelism
3. **Cap 2 (Bootstrap)** — server process + middleware + discovery + health/metrics
4. **Cap 3 (Workitem + Content)** — main surface; parallelizable once 2 is merged
5. **Cap 4 (Assistant + Search + Extras)** — in parallel with 3 if second engineer available
6. **Cap 5 (Resources + Subscriptions)** — requires 3+4 shapes stable
7. **Cross-cutting** — load tests, docs, tools-list snapshot finalize
8. **Review gates** — arch + sec + db + code-review + review-before-push

### Effort (backend only)

| Cap | TDD-paced |
|---|---|
| 1 | 3 d |
| 2 | 3 d |
| 3 | 4 d |
| 4 | 4 d |
| 5 | 3 d |
| Cross-cutting | 2 d |
| **Total** | **~19 d solo / ~11 d with 2 devs** |

---

## 7. Feature flags & rollout

- `MCP_SERVER_ENABLED` global kill switch (rejects all tokens `-32001`)
- `MCP_ENABLED_FOR_WORKSPACE` per-workspace gate (checked at verify time)
- Rollout: superadmin workspaces → 3 pilot workspaces (2-week soak) → GA via flag flip

Rollback: disable global flag; REST unaffected; revoke outstanding tokens optional.

---

## 8. Pre-merge checklist (each capability)

- [ ] All RED tests existed at least one commit before GREEN
- [ ] Per-tool cross-workspace forbidden test present
- [ ] No repository import inside `apps/mcp-server/src/mcp_server/tools/**` (lint enforced)
- [ ] No plaintext token in any log/response outside the issue/rotate endpoint
- [ ] Metrics registered
- [ ] Audit events emitted
- [ ] Shared schemas updated with `schema_version` bump if breaking
- [ ] Tools-list snapshot reviewed
- [ ] `code-reviewer` pass
- [ ] For Cap 1 and Cap 4: additional `security-scan` skill pass

---

## 9. Open items to confirm with `sw-architect` before coding

1. Shared DTO relocation into `packages/schemas/` — is the existing REST codebase OK with the move, or do we add proxies?
2. Argon2id cost tuning target — is 10–20 ms acceptable on our reference hardware given expected QPS, or should we fall back to sha256 + PBKDF2 for the verify path with separate hash on sensitive mutations (future write scope)?
3. Rate-limit keying — per-(token, tool) granularity vs per-token global? Spec says global; confirm adequate for high-fanout tools like `workitem.search`.
4. SSE bridge topology — one Redis pub/sub consumer per pod (current plan) vs shared consumer with in-process fanout. Current plan simpler; reconsider if > 20 pods.
5. Celery queue for audit — new queue `mcp_audit` with dedicated workers or reuse `audit` queue? Separate queue isolates MCP traffic spikes.
