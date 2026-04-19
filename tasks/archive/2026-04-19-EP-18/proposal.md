# EP-18 — MCP Server: Read & Query Interface

## Business Need

The Work Maturation Platform concentrates high-value context that today only lives behind the web UI and the internal REST API: work items in every state (`Borrador` → `Ready`), versioned specs with section-level structure, clarification threads with Dundun, validation checklists, reviews, anchored comments, version diffs, hierarchy (Workspace → Project → Milestone → Epic → Story → Task → Subtask) with completeness roll-up, tags, attachment metadata, inbox with priority ordering, semantic search results via Puppet, Jira export snapshots with divergence indicators, and audit events.

External agents (Claude Code, IDE copilots, CLIs, reporting scripts, other MCP-capable tools) need a uniform, low-friction way to ask questions like:

- "What is the current spec of work item X, and which sections are flagged as incomplete?"
- "List all stories under epic Y whose validations are pending."
- "Show me the review history of this work item, with who approved what version."
- "Semantic-search Puppet for 'price calculation edge cases' across my workspace."
- "What's in my inbox right now, ordered by priority?"
- "Has work item Z diverged from its Jira snapshot?"

Giving these agents the raw REST API is hostile (auth, shape, pagination, workspace resolution each time). Giving them DB access is worse. An **MCP server** exposes the platform's read surface as standard MCP `tools` and `resources`, so any MCP-capable client can introspect the platform without leaking DB credentials, duplicating business logic, or bypassing authorization.

This epic is **read-only first**. Write/mutation operations (create, transition, post comment, apply Dundun suggestion, export to Jira, force-unlock) are explicitly out of scope — a separate follow-up epic will add them under a stricter auth model. Keeping the initial surface read-only bounds the blast radius, simplifies the auth design, and lets us ship fast.

## Objectives

- Ship an MCP server (stdio + HTTP/SSE transports) in front of the existing REST API
- Expose every read endpoint as a typed MCP `tool` with uniform naming (`<resource>.<verb>`)
- Expose long-lived aggregates as MCP `resources` (e.g., `workitem://<id>`, `epic://<id>/tree`, `workspace://<id>/dashboard`, `user://me/inbox`) with subscribe support
- Authenticate MCP clients with scoped API tokens (reuse EP-00 identity model; new `mcp:read` scope; one-workspace binding)
- Enforce the **same** authorization rules as the REST API — no parallel authz implementation; call the application layer
- Respect strict **workspace isolation** (functional spec §3.15): a token bound to workspace W never sees data from workspace W'
- Log every MCP invocation to the audit trail (actor, workspace, tool, params hash, latency, result size, status) — shared with EP-12 observability
- Generate tool/resource schemas from the same source of truth as REST DTOs to prevent drift
- Ship auto-generated public tool catalog documentation

## Non-Goals (explicit)

- **No write/mutation tools** — create, update, delete, state transitions, comments, Dundun apply, Jira export, force-unlock, admin actions. Tracked as a follow-up epic.
- **No new business logic** — MCP is a transport adapter. If a question cannot be answered by existing services, the answer is "add the service method first, then expose."
- **No GraphQL or gRPC surface** — MCP only.
- **No bulk export / offline snapshots** — use EP-11 Jira export path.
- **No cross-workspace queries** — one token, one workspace, hard boundary.
- **No superadmin tools in this epic** — superadmin cross-workspace audit reads via MCP land in a separate follow-up with stricter review.
- **No Dundun write/chat** — reading conversation history is in scope, sending messages to Dundun is not.

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-180 | As an external agent, I list available MCP tools and resources with their JSON schemas | Must |
| US-181 | As an external agent, I authenticate with an API token bound to one workspace and receive session metadata (actor id, workspace id, capabilities, context tags) | Must |
| US-182 | As an external agent, I query a work item by id and receive full detail (type, state, owner, spec sections, completeness score, gaps, next-step recommendation, hierarchy path, tags, attachment count, lock state, Jira reference, divergence flag) | Must |
| US-183 | As an external agent, I search work items with free text + filters (state, type, owner, team, tags AND/OR, archived, parent id, project) and cursor-based pagination | Must |
| US-184 | As an external agent, I navigate the hierarchy (project → milestone → epic → story → task → subtask) from any node, one hop up and down | Must |
| US-185 | As an external agent, I read the comment tree of a work item including anchored comments, anchor text, orphan flag, reactions, mentions, edited flag | Must |
| US-186 | As an external agent, I read the version history of a work item, plus a diff between any two versions | Must |
| US-187 | As an external agent, I read reviews and validation checklist status for a work item, including override justifications if any | Must |
| US-188 | As an external agent, I read the timeline for a work item (creation, state changes, versions, reviews, validations, comments, exports) with actor kind (human/assistant/system) | Must |
| US-189 | As an external agent, I read Dundun clarification-thread messages for a work item, with proposed sections and acceptance status per segment | Must |
| US-190 | As an external agent, I run semantic search via Puppet (keyword + semantic combined) scoped to my workspace, with snippets, facets, and source (internal vs external Tuio docs) | Must |
| US-191 | As an external agent, I list the current user's inbox with priority ordering (pending reviews > returned items > blocking deps > pending decisions) | Must |
| US-192 | As an external agent, I list tags (active + archived) and fetch work items by tag with AND/OR logic | Must |
| US-193 | As an external agent, I read attachment metadata (name, type, size, uploader, thumbnails, gallery order) — NOT the binary | Must |
| US-194 | As an external agent, I read workspace dashboards (global by state, by owner, by team, pipeline, admin health in 4 blocks) | Should |
| US-195 | As an external agent, I read Jira export snapshot + current divergence for a work item | Should |
| US-196 | As an external agent, I subscribe to `workitem://<id>` and receive resource-updated notifications within 2s of changes (SSE) | Should |
| US-197 | As an external agent, I subscribe to `user://me/inbox` and receive live inbox updates | Should |
| US-198 | As a workspace admin, I issue, rotate, revoke, and audit MCP tokens per user with `mcp:read` scope and a single-workspace binding | Must |
| US-199 | As a workspace admin, I see every MCP invocation in the audit log (actor, workspace, tool, params hash, duration, outcome, client identity) | Must |

## Acceptance Criteria

### Discovery & Protocol

- WHEN a client connects with a valid MCP token THEN `initialize` returns server info, protocol version, capabilities (tools, resources, subscribe, logging)
- WHEN a client connects without a token OR with an expired/revoked/wrong-scope token THEN the server rejects with MCP error `-32001` (unauthorized) and no tool is listed in a subsequent `tools/list`
- WHEN a client calls `tools/list` THEN the response includes every registered tool with full JSON schema for input AND output, plus description and deprecation metadata
- WHEN a client calls `resources/list` THEN the response includes every registered resource URI template with description
- AND `tools/list` output is stable enough that schema changes bump tool version (`v2.workitem.get` coexists with `workitem.get` during deprecation window ≥ 30 days)

### Auth & Session

- WHEN a workspace admin issues an MCP token with `mcp:read` scope THEN the token carries `{ actor_id, workspace_id, scopes, expires_at, created_by }` and is stored hashed (argon2id) — plaintext shown **once** at creation
- WHEN a token is used THEN `last_used_at` and `last_used_ip` are updated (asynchronously, at-least-once)
- WHEN an admin revokes a token THEN the next request using it is rejected within 5 seconds (cache TTL)
- WHEN a token expires THEN the server rejects with `-32001` and the client MUST NOT retry
- AND tokens default to **30-day TTL**, max 90 days
- AND tokens are bound to **exactly one workspace** — no multi-workspace tokens
- AND a user can hold at most **10 active MCP tokens** per workspace (configurable by admin, hard cap 50)

### Authorization & Workspace Isolation

- WHEN any tool is called THEN the handler MUST pass `{ actor_id, workspace_id }` from the token into the application service — never trust params
- WHEN a tool receives a `workspace_id` param that differs from the token's workspace THEN the server returns `-32003` (forbidden) without touching the service
- WHEN the caller lacks permission on a resource THEN the server returns `-32003` (forbidden) — NEVER `-32002` (not found), to avoid existence leaks
- WHEN the caller's context tags or capabilities restrict visibility (e.g., some admin-only fields) THEN the response omits those fields and includes them in a `redacted_fields` array
- AND every tool handler has at least one integration test that asserts `-32003` for a cross-workspace id

### Core Read Tools — Work Items

- WHEN `workitem.get(id)` is called on a readable id THEN response contains `{ id, type, title, state, owner: { id, display_name }, project: { id, name }, parent_path: [{id, type, title}], children_count, spec: { sections: [...], completeness: { score, level, gaps, next_step }}, tags, attachment_count, lock: { held_by?, expires_at? }, jira: { issue_key?, exported_at?, diverged? }, created_at, updated_at, version: { id, number } }`
- WHEN `workitem.get(id, { include_spec_body: false })` is called THEN the `spec.sections[].body` field is omitted (caller opts in for heavy payloads)
- WHEN `workitem.search({ q?, filters, limit, cursor })` is called THEN the response is `{ items: [...], next_cursor?, total_estimate? }` with `limit` clamped to 100 and cursor opaque (base64)
- WHEN `workitem.children(parent_id, { limit, cursor })` is called THEN only **direct children** are returned with `has_more_children` flag per child (no implicit tree expansion)
- WHEN `workitem.hierarchy(id)` is called THEN response contains `{ ancestors: [...], node: {...}, direct_children: [...], roll_up: { completeness, descendant_ready_ratio } }`
- WHEN `workitem.listByEpic(epic_id, { group_by? })` is called THEN response is flat or grouped by direct child type (milestone | story | task)

### Core Read Tools — Content

- WHEN `comments.list(work_item_id, { anchored_only?, cursor })` is called THEN response includes `{ id, author, body, anchor: { section_id, range?, orphan }?, parent_id?, thread_children_count, reactions, mentions, edited_at?, created_at }`
- WHEN `versions.list(work_item_id, { cursor })` is called THEN response returns versions in reverse chronological order with `{ id, number, author_kind: human|assistant|system, author_id?, tag?, created_at, change_summary }`
- WHEN `versions.diff(work_item_id, from_version, to_version)` is called THEN response returns section-level diff with `{ section_id, change: added|removed|modified, old?, new? }` — server-computed, no raw SQL row exposure
- WHEN `reviews.list(work_item_id)` is called THEN response includes every review request with `{ id, version_id, target_kind: user|team, target_id, state: pending|approved|rejected|changes_requested, responder_id?, responded_at?, comments_count }`
- WHEN `validations.list(work_item_id)` is called THEN response returns the checklist with `{ rule_id, label, required: bool, satisfied_by_review_id?, overridden: bool, override_reason?, override_by?, override_at? }`
- WHEN `timeline.list(work_item_id, { event_types?, cursor })` is called THEN response merges version, state, review, validation, comment, export, and lock events with uniform `{ kind, actor_kind, actor_id?, payload, happened_at }` ordering

### Dundun (Assistant) & Puppet (Semantic Search)

- WHEN `assistant.threads.get(work_item_id)` is called THEN response returns the clarification thread `{ messages: [{ id, role: user|assistant|system, content, proposed_sections?: [...], segments?: [{ id, accepted: bool, applied_at? }] }], last_activity_at }`
- WHEN `assistant.threads.workspace()` is called THEN response returns the workspace-general chat threads readable by the caller
- WHEN `semantic.search({ q, filters?, include_external?, limit, cursor })` is called THEN the server calls Puppet with the caller's workspace scope and returns `{ results: [{ kind: workitem|section|comment|external_doc, id, title, snippet_html, score, source }], facets: { state, type, owner, team, tags, archived } }`
- WHEN Puppet is unreachable THEN the server returns `-32010` (upstream unavailable) with `{ upstream: "puppet", retriable: true }` — no silent fallback
- AND `semantic.search` results strictly respect workspace isolation (§3.15)
- AND external-doc results are clearly labeled `source: "tuio-docs"` and never mixed with workspace content in ranking without a visual separator flag

### Hierarchy, Tags, Attachments

- WHEN `tags.list({ include_archived? })` is called THEN response returns tags with `{ id, name, color, icon?, archived, usage_count }`
- WHEN `tags.workitems(tag_ids, { mode: and|or, cursor })` is called THEN filter semantics match functional spec §3.10 (AND/OR)
- WHEN `labels.list()` is called THEN response returns workspace labels (separate from tags per product vocabulary)
- WHEN `attachments.list(work_item_id)` is called THEN response returns metadata only `{ id, name, mime, size_bytes, uploader_id, created_at, thumbnail_url?, is_pdf_first_page: bool }` — **never the binary**
- AND `attachments.list` does NOT expose any download URL unless caller has `attachment:read` on that work item; when allowed, returns a short-lived (≤5 min) signed URL

### Inbox, Dashboards, Jira

- WHEN `inbox.list({ cursor })` is called THEN response is ordered: pending_reviews > returned_items > blocking_dependencies > pending_decisions, each with context link and allowed quick actions (read-only, just indicate what's available)
- WHEN `workspace.dashboard()` is called THEN response returns the four admin blocks from §3.13: workspace health (states, blockers, time-to-Ready, aged reviews), organizational (members w/o team, overloaded owners), process (missed validations, %overrides, blocked backlog), integrations (Jira status, Puppet status, failed exports)
- WHEN caller lacks admin capability THEN `workspace.dashboard()` returns only blocks they can see (workspace + own items) — admin blocks are omitted, not errored
- WHEN `jira.snapshot(work_item_id)` is called on an exported item THEN response returns `{ issue_key, exported_version_id, exported_at, current_version_id, diverged: bool, divergence_summary? }`
- WHEN called on a non-exported item THEN response is `{ exported: false }` — not an error

### Resources

- WHEN a client reads `workitem://<id>` THEN it gets the same payload as `workitem.get` as an MCP resource
- WHEN a client subscribes to `workitem://<id>` AND any event changes the item (version, state, lock, review, comment, tag) THEN server emits `notifications/resources/updated` within 2s
- WHEN a client subscribes to `user://me/inbox` AND any inbox-affecting event occurs THEN notification is emitted within 2s
- AND the SSE bus reuses EP-12 infrastructure; MCP subscribes as a consumer, not a peer publisher

### Audit & Observability

- AND every MCP call emits an audit event: `{ actor_id, workspace_id, tool_or_resource, params_hash (sha256 of normalized params), duration_ms, result_bytes, status, error_code?, client_name?, client_version? }` — event body bounded to 4 KB, params never logged in clear
- AND audit events go to the same pipeline as REST audit (EP-12)
- AND `/metrics` exposes per-tool latency histogram (p50/p95/p99), error rate by code, active SSE sessions, tokens issued/revoked counters, Puppet upstream error rate
- AND server logs redact token values, never log full request bodies, and sample successful trace logs at ≤10%

### Rate Limiting & Resilience

- AND per-token and per-IP token buckets are enforced, shared with REST (EP-12) — same 429/`-32005` semantics
- AND tool timeouts: p95 under 1s for `*.get` / `*.list`, under 3s for search; hard timeout 10s; on timeout return `-32011` (timeout)
- AND when the underlying service is degraded, the MCP server returns `-32010` (upstream unavailable) — no silent caching

## Technical Notes

### Stack

- Node 20+ or Python 3.12+ — **pick the same language/runtime as the existing REST API** so the MCP server reuses the application service layer directly (no HTTP hop-to-self, no duplicated DTOs)
- Official **Model Context Protocol SDK**. Transports: `stdio` for local agents, `HTTP + SSE` for remote clients. Both shipped from day one.
- Schema validation: Zod (TS) / Pydantic (Python). Tool input/output schemas derived from the same definitions used by REST DTOs.

### Architecture

MCP server is a **thin adapter** over the existing application layer. No direct DB. No duplicated business logic.

```
apps/mcp-server/
  src/
    presentation/
      mcp/
        tools/           # one file per tool — parse input → call service → format output
          workitem/
            get.ts
            search.ts
            children.ts
            hierarchy.ts
            list-by-epic.ts
          comments/list.ts
          versions/{list,diff}.ts
          reviews/list.ts
          validations/list.ts
          timeline/list.ts
          assistant/{thread-get,threads-workspace}.ts
          semantic/search.ts
          tags/{list,workitems}.ts
          labels/list.ts
          attachments/list.ts
          inbox/list.ts
          workspace/dashboard.ts
          jira/snapshot.ts
          user/me.ts
        resources/       # URI template → resolver
          workitem.ts
          epic-tree.ts
          workspace-dashboard.ts
          user-inbox.ts
        auth.ts          # token verification middleware
        audit.ts         # emit audit events
        errors.ts        # service exception → JSON-RPC error mapping
        rate-limit.ts    # reuse EP-12 limiter
        server.ts        # MCP server bootstrap
    config.ts
  Dockerfile
  helm/
```

Each tool handler is ≤30 lines: validate → authorize (token-injected actor) → service → format.

### Auth Model (EP-00 extension)

- New token kind `mcp_token` in the identity model:
  - Columns: `id, user_id, workspace_id, scopes[], name, hashed_secret, created_at, expires_at, last_used_at, last_used_ip, created_by, revoked_at?`
  - Scope: `mcp:read` (single scope for MVP — YAGNI on fine-grained)
  - Stored hashed (argon2id). Plaintext shown **once** on creation.
- New capability `mcp:issue` for workspace admins (workspace-scoped). Superadmin implicitly has it.
- Token verification cache: 5s TTL on `revoked_at` lookup to keep auth cheap without losing revocation responsiveness.

### Authz

- **Reuse existing service-layer guards**. MCP layer passes `{ actor_id, workspace_id }` into services; services decide.
- Every tool handler MUST go through the service layer — direct repository calls in MCP code is an automatic code-review block.
- Integration test per tool asserts `-32003` for cross-workspace id.

### Tool Naming Convention

- `<resource>.<verb>` — predictable, autocomplete-friendly
- `workitem.get`, `workitem.search`, `comments.list`, `versions.diff`, `semantic.search`
- Plural resources use plural form in the left segment: `comments.list`, not `comment.list`
- Never `x.getAll` — always `x.list` with pagination

### Error Mapping

| Service exception | MCP error code | MCP error name |
|---|---|---|
| `UnauthenticatedError` | `-32001` | unauthorized |
| `NotFoundError` | `-32002` | not_found (ONLY when caller can confirm non-existence) |
| `ForbiddenError` | `-32003` | forbidden |
| `ValidationError` | `-32602` | invalid_params |
| `RateLimitedError` | `-32005` | rate_limited |
| `UpstreamUnavailableError` (Puppet, Jira) | `-32010` | upstream_unavailable |
| `TimeoutError` | `-32011` | timeout |
| `ConflictError` (future writes) | `-32009` | conflict |
| generic `Error` | `-32603` | internal (NEVER leak stack traces or SQL) |

### Pagination

- Opaque base64-encoded cursor — same format as REST
- Never expose DB offsets or raw row ids inside the cursor
- Default `limit` 20, max 100

### Versioning

- Tool schemas follow semver. Breaking change ⇒ publish `v2.<tool>` alongside `<tool>` for ≥ 30 days.
- `tools/list` includes deprecation metadata (`deprecated: true, replaced_by: "v2.workitem.get", sunset_at: "..."`)

### Deployment

- Separate process from the REST API. Scales independently. Same secrets/config store.
- Docker image under `apps/mcp-server/`. Helm chart entry.
- Same CI pipeline as API. New `e2e-mcp` job (stdio + HTTP smoke) gated on merge to main.

## Tool Catalog (initial, ≤20)

| Tool | Purpose |
|---|---|
| `user.me` | Authenticated actor info (id, workspace, capabilities, context tags) |
| `workitem.get` | Full detail for one work item |
| `workitem.search` | Free-text + filters, paginated |
| `workitem.children` | Direct children (one hop) |
| `workitem.hierarchy` | Ancestors + direct children + roll-up |
| `workitem.listByEpic` | All items under an epic, flat or grouped |
| `comments.list` | Comments (anchored + general) for a work item |
| `versions.list` | Version history |
| `versions.diff` | Section-level diff between two versions |
| `reviews.list` | Review requests + states |
| `validations.list` | Validation checklist + overrides |
| `timeline.list` | Merged timeline events |
| `assistant.threads.get` | Dundun clarification thread for a work item |
| `assistant.threads.workspace` | Workspace-general Dundun threads |
| `semantic.search` | Puppet keyword + semantic search |
| `tags.list` / `tags.workitems` | Tag catalog + lookup |
| `labels.list` | Workspace labels |
| `attachments.list` | Attachment metadata (+ signed URL on demand) |
| `inbox.list` | Current user's inbox with priority ordering |
| `workspace.dashboard` | Admin 4-block dashboard |
| `jira.snapshot` | Exported snapshot + divergence state |

## Resource Catalog (initial)

| URI template | Description | Subscribe |
|---|---|---|
| `workitem://<id>` | Live work-item detail | Yes |
| `epic://<id>/tree` | Epic + full descendant tree | Yes |
| `workspace://<id>/dashboard` | Aggregated dashboard state | No (poll) |
| `user://me/inbox` | Current user's inbox | Yes |

## API Endpoints (HTTP transport)

- `POST /mcp` — JSON-RPC over HTTP (single request/response)
- `GET /mcp/sse` — SSE stream for notifications + resource updates
- `GET /mcp/health` — liveness/readiness
- `GET /metrics` — Prometheus

## Dependencies

- **EP-00** — identity model, token issuance, capability system (new `mcp:read` scope, `mcp:issue` capability)
- **EP-01** — work-item read services + authz
- **EP-03** — Dundun thread read access
- **EP-04, EP-05** — spec sections, completeness engine, hierarchy
- **EP-06** — reviews + validations + override reads
- **EP-07** — comments, versions, diff, timeline
- **EP-08** — inbox + notifications + SSE bus
- **EP-09** — listings, dashboards, search endpoints
- **EP-10** — admin capability `mcp:issue`, admin support tools
- **EP-11** — Jira export snapshots + divergence reads
- **EP-12** — rate limiting, observability, SSE infra, audit pipeline
- **EP-13 (Puppet)** — semantic search upstream
- **EP-19 (Design System)** — shared frontend catalog (shadcn-based), semantic tokens, i18n ES tuteo, a11y gate — consumed by the MCP admin UI (token management, audit viewer, self-service)
- **EP-14, EP-15, EP-16, EP-17** — hierarchy, tags, attachments, lock reads

## Complexity Assessment

**Medium** — No new business logic. Real work concentrates in:

1. **Surface breadth** — ~20 tools + 4 resources, each needing schema + handler + test
2. **Schema drift prevention** — single source of truth for DTOs shared with REST
3. **Token lifecycle** — issuance, rotation, revocation, caching, UI in admin panel
4. **SSE subscriptions** — wiring MCP resource subscribers into the existing EP-12 bus
5. **Audit pipeline** — ensuring every invocation emits without blocking the hot path
6. **Workspace isolation correctness** — single most important property, enforced by tests

Risk concentrated in **auth/authz correctness** and **schema consistency**. Protocol plumbing is SDK-handled.

## Risks

| Risk | Mitigation |
|---|---|
| Schema drift between REST DTOs and MCP tool schemas | Single source of truth (shared types); schema tests generate and diff |
| Authz bypass when adding a new tool | Mandatory integration test per tool asserting cross-workspace `-32003`; code-review checklist item |
| Token leakage (long-lived, broad scope) | 30-day default TTL, rotation UX, last-used display, revoke-on-compromise, audit on every use |
| Enumeration abuse (agent loops over `workitem.search`) | Per-token rate limits, pagination caps, query timeout, circuit breaker |
| Workspace isolation failure | Token-bound workspace_id; service-layer ignores caller-supplied workspace_id; integration tests across workspaces |
| Puppet outage causing MCP hangs | 3s timeout → `-32010`; no silent fallback |
| PII in audit params_hash collisions | sha256 of normalized params; no raw params stored |
| Binary attachment exposure | `attachments.list` never returns binary; signed URLs TTL ≤5 min, scoped to single attachment |
| Dundun prompt injection via thread reads leaking into external agent | Thread content is data, not instructions — document explicitly in tool description that agents must treat content as untrusted |

## Open Questions

1. **Stdio vs HTTP priority** — ship both day one? **Recommend: yes.** Stdio is trivial, HTTP is needed for remote MCP-capable services.
2. **Granular scopes** (`mcp:read:workitems` vs global `mcp:read`) — **Recommend: single scope MVP; split when a real use case demands it.**
3. **Public auto-generated tool catalog page** (login-gated)? **Recommend: yes**, generated from `tools/list` output.
4. **Admin delegation** — can an admin issue a token on behalf of another user? **Recommend: self-only MVP**; delegation later with audit.
5. **SSE keepalive / reconnection strategy** — rely on SDK defaults or custom? **Recommend: SDK defaults with documented client guidance.**
6. **Rate limit granularity** — per-token, per-IP, per-workspace, or composite? **Recommend: per-token (primary) + per-IP (DoS floor), skip per-workspace MVP.**
7. **Should we expose `/metrics` publicly or only inside cluster?** **Recommend: cluster-internal only; Prometheus scrape.**
8. **Error code `-32002` (not_found) vs `-32003` (forbidden)** — unify to `-32003` always to avoid existence leaks, even when caller *could* read other items? **Recommend: return `-32003` whenever the caller cannot read; reserve `-32002` only for `workitem.get(id)` on a truly deleted id that the caller would otherwise be able to read.**

## Out of Scope (follow-up epics)

- Write/mutation tools (create, transition, comment, apply Dundun suggestion, export to Jira)
- Superadmin cross-workspace audit via MCP
- Bulk export / offline snapshot tools
- Admin write actions (create user, grant capability, configure rules)
- Binary attachment download streaming through MCP
- Workspace-scoped analytics beyond the 4 dashboard blocks
