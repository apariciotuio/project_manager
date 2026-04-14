# Assumptions

Assumptions made during the technical planning of the product. These need product/business confirmation before implementation begins. Grouped by area.

> ⚠️ **Pending re-decisions**: several rows below were originally scoped as "MVP-only" shortcuts. The project is no longer framed as an MVP, so those shortcuts need to be re-decided. See `decisions_pending.md` for the consolidated list. Rows still marked ⚠️ below have NOT been re-decided yet — treat the stated value as provisional, not final.

---

## Tech Stack (not specified in PRD — assumed)

| Decision | Assumed | Rationale |
|----------|---------|-----------|
| Backend language | Python 3.12+ | Tuio ecosystem, LLM integration ergonomics |
| Backend framework | FastAPI (async) | Modern async support, OpenAPI auto-gen, dependency injection |
| ORM | SQLAlchemy 2.0 (async) | Mature, DDD-friendly, async sessions |
| Database | PostgreSQL 16+ | JSONB for snapshots, tsvector for FTS, mature ecosystem |
| Frontend framework | Next.js 14+ (App Router) | SSR/SSG, TypeScript, React ecosystem |
| Frontend language | TypeScript (strict mode) | Type safety, DDD alignment |
| Cache | Redis 7+ | Session store, cache, Celery broker, SSE state |
| Background jobs | Celery + Redis broker | Notification fan-out, LLM calls, export jobs, sync polling |
| Real-time delivery | SSE (Server-Sent Events) | Unidirectional push for notifications — simpler than WebSocket |
| CSS framework | Tailwind CSS | Mobile-first responsive, utility classes |
| Auth provider | Google OAuth 2.0 only (resolved 2026-04-14) | Internal product on Google Workspace. No fallback, no SAML. Final decision |
| Error tracking | None (deferred — see Observability row below) | Stdlib logs only |
| LLM provider | **Dundun (external agentic system)** (resolved 2026-04-14, revised after dundun context) | No LLM in our backend. `DundunClient` (HTTP) delegates chat, gap detection, spec generation, suggestions, breakdown to dundun. Dundun owns LiteLLM proxy, LangSmith prompts, model selection, token budget, evals. Our config has only `DUNDUN_BASE_URL` + service auth — no LLM keys |

## Architecture

| Assumption | Detail |
|------------|--------|
| Monorepo structure | `backend/` and `frontend/` in same repository |
| DDD layered architecture | Presentation → Application → Domain → Infrastructure |
| API versioning | REST with `/api/v1/` prefix |
| Multi-workspace per deployment | Multiple tenant organizations share the deployment. Resolution by slug/subdomain post-login |
| Multi-tenant | `workspace_id` scoping on every domain table. PostgreSQL Row-Level Security enforces isolation. User identity global (`google_sub`), membership per workspace |

## Authentication & Sessions

| Assumption | Detail |
|------------|--------|
| Hybrid JWT | 15-min access token (stateless) + 30-day refresh token (hashed in DB) |
| PKCE required | OAuth 2.1 compliance for browser-initiated flows |
| User identity | Resolved by `google_sub`, NOT email (email can change) |
| Workspace bootstrap (resolved 2026-04-14) | **No auto-create.** Login resolves active memberships: 0 → block with "contact admin"; 1 → land directly; N → workspace picker. Last choice persisted in session. Workspaces created by Superadmin only |
| Session scope | Refresh token scoped to `/api/v1/auth/refresh` path only |

## Domain Model

| Assumption | Detail |
|------------|--------|
| Single table for all types | `work_items` table with `type` column, no per-type tables |
| Custom FSM | 14-edge state machine, no external library. Transition graph as `frozenset` of tuples |
| Derived state computed, not stored | Computed from primary state + pending validations at read time |
| Override on work_item row | `has_override` + `override_justification` columns, not just in audit |
| Suspended owner → blocked | Items not auto-reassigned; admin must intervene |
| Content gate for review | Only non-empty title + description required to enter In Review |

## Versioning & History

| Assumption | Detail |
|------------|--------|
| Full snapshots over deltas | JSONB snapshot per version — O(1) read, PG TOAST handles compression |
| Timeline as dedicated table | `timeline_events` table with write-side fan-in, not UNION ALL query |
| Diff computed on demand | `difflib` stdlib, not persisted. Structured + text diff in <500ms |
| Anchor stability | By `section_id` (UUID, stable) + best-effort text offset re-computation |

## Dundun integration (resolved 2026-04-14)

| Aspect | Detail |
|--------|--------|
| Client | `DundunClient` in our backend. **HTTP sync** (`POST /api/v1/dundun/chat`) for short turns, **HTTP async with callback** (`POST /api/v1/webhooks/dundun/chat` + our callback URL) for longer flows. **No WebSocket** to Dundun (earlier assumption corrected after reviewing Dundun's OpenAPI). No LLM SDKs in our deps |
| Auth to Dundun | Service-to-service key (env var). Our BE sets `caller_role=employee` + `user_id` on every call. All our users are Tuio employees (VPN-only product) |
| Search integration | **NOT via Dundun.** Our BE calls Puppet `POST /api/v1/retrieval/semantic/` directly. Workspace isolation is enforced via **category naming convention** `tuio-wmp:ws:<workspace_id>:workitem|section|comment` (Puppet has no native workspace concept). External Tuio docs live under `tuio-docs:*`. Server-side post-filter re-checks platform permissions on every returned `Source` |
| Puppet ingestion | **Our BE pushes.** Platform-content ingestion endpoints in Puppet are **pending** (tracked as a forthcoming deliverable on the Puppet side). Until they ship, MCP `semantic.search` and web-search over workspace content return empty for `source: workspace`; external Tuio docs already work via Puppet's Notion ingestion. Planned: Celery sync pipeline on every write (work_item, section, comment) → Puppet with category + `page_id = "<entity_kind>:<uuid>"` + tags. Eventual consistency <3s accepted |
| Chat (sync interactive) | FE WS → Our BE WS proxy → Dundun `/ws/chat`. Our BE enforces auth + work_item membership before forwarding. Progress frames forwarded transparently |
| AI async tasks (gap detection, spec gen, suggestion, breakdown) | Our BE Celery job: POST Dundun `/chat` with `callback_url`. Dundun returns 202, POSTs back to our `/api/v1/dundun/callback`. Job finalizes and updates work_item |
| Conversation state | Dundun owns (Temporal workflows). We store `conversation_threads(dundun_conversation_id, ...)` as pointers + `last_message_preview` cache for listing UX |
| End-conversation | Our BE sends `POST /api/v1/webhooks/dundun/end-conversation` on logout / explicit close |
| Prompts | In Dundun's LangSmith. Not in our repo. Zero prompt maintenance on our side |
| Agent catalog | Dundun team designs and owns YAMLs. Our side: knows agent names to invoke (clarification, spec-gen, gap-detection, breakdown, suggestion) |
| Observability | Dundun handles via LangSmith + OpenTelemetry (dundun-side). Our only visibility is request/response logs through `DundunClient` |
| Failure mode | If Dundun down: chat unavailable, async AI tasks queued with retry. Core CRUD + search + workflows unaffected |

## Conversations & AI (our side — thin layer)

| Assumption | Detail |
|------------|--------|
| Gap detection: rule-based first | Deterministic, runs synchronously. LLM-enhanced is async and opt-in |
| Context window managed server-side | Oldest messages summarized; LLM gets summary + recent messages |
| Celery for dundun async | Single `dundun` queue. Celery job POSTs to dundun `/chat` with `callback_url`, receives 202, waits for dundun's callback (webhook) on our `/api/v1/dundun/callback`. No local LLM execution |
| WebSocket chat proxy | FE WS → Our BE WS → Dundun WS `/ws/chat` (proxy enforces JWT + membership + sets `caller_role=employee` + `user_id`). Progress frames forwarded transparently |

## Teams & Notifications

| Assumption | Detail |
|------------|--------|
| SSE over WebSocket | Unidirectional push. Revisit only if collaborative editing lands |
| Inbox is computed, not materialized | UNION query with partial indexes — acceptable up to ~1k items/user |
| Notification idempotency | `sha256(recipient_id + domain_event_id)` as dedup key |
| Team review race condition | `SELECT FOR UPDATE` on review row at DB level |

## Search & Dashboards

| Assumption | Detail |
|------------|--------|
| Search delegated to Puppet RAG (resolved 2026-04-14) | Full-text + semantic + prefix + saved searches all served by Puppet. SQL local only for filters, listings, ID access, dashboards. Push-on-write sync pipeline, <3s eventual consistency accepted. No PG FTS (`tsvector`/GIN dropped), no Elasticsearch. If Puppet unavailable → search UI shows unavailable; CRUD + filter flows unaffected |
| Cursor-based pagination everywhere | Offset pagination banned — degrades under concurrent writes |
| Dashboard: on-demand SQL + Redis cache | 60s TTL, event-driven invalidation on state transitions |
| No denormalized search columns (resolved 2026-04-14) | Dropped `aggregated_comment_text` / `aggregated_task_text`. All search goes to Puppet, where the full document is indexed by the sync pipeline |

## Permissions

| Assumption | Detail |
|------------|--------|
| Capability array + 5 workspace profiles as code constants + Superadmin platform flag (resolved 2026-04-14) | `capabilities: text[]` on `workspace_memberships`. `PROFILE_CAPABILITIES` dict with 5 workspace profiles: Member, Team Lead, Project Admin, Integration Admin, Workspace Admin. Superadmin is a separate `users.is_superadmin` boolean (platform-level, cross-workspace), seeded via config. No roles table, no UI editor, no custom roles. Invariants: (1) last Workspace Admin can't be demoted, (2) no user can assign a profile wider than their own, (3) all profile/flag changes audited |
| `require_capabilities` FastAPI dependency | Middleware-level enforcement, not per-controller |
| Context labels separate from permissions | Labels (product, dev, QA, business) are tags, never grant operational access |

## Jira Integration

| Assumption | Detail |
|------------|--------|
| Re-export = UPDATE of same Jira issue (resolved 2026-04-14) | Upsert by stored `jira_issue_key`. Before overwrite, check Jira `updated_at` against last-export snapshot timestamp; if Jira was touched externally → warning + user confirmation required |
| Retry reuses original snapshot | Never rebuilds — snapshot is the contract |
| No automatic inbound sync (resolved 2026-04-14) | No polling, no webhooks, no `sync_logs` table. Inbound data only via user-initiated `POST /work-items/import-from-jira` action |
| Import from Jira (resolved 2026-04-14) | Creates a new `work_item` in `draft` from a Jira issue. Stores `imported_from_jira: true` + `jira_source_key`. Exporting a previously-imported item upserts the original issue (closes the loop). Cannot re-import an issue already linked to an unresolved work_item |
| Fernet-encrypted credentials | With rotation path. Never in audit log or API response |

## Security & Performance

| Assumption | Detail |
|------------|--------|
| Middleware chain order | Correlation ID → Rate limit → CORS → Auth → Capability check → Input validation |
| CSRF via SameSite=Strict | Explicit CSRF tokens only for cross-subdomain scenarios |
| Response time targets | List APIs <200ms, Detail <300ms, Search <300ms, Dashboard <500ms |
| Observability deferred (resolved 2026-04-14) | No Prometheus/Grafana/Loki/OpenTelemetry/Sentry. No `product_events` table. Only stdlib `logging` to stdout + `CorrelationIDMiddleware`. Debugging is ssh + `docker logs` |

## Open Product Questions (Need Confirmation)

| # | Question | Default Assumed | Impact if Wrong |
|---|----------|----------------|-----------------|
| 1 | New user hits system — auto-create personal workspace or join existing? | **No auto-create (resolved 2026-04-14).** Login → pick from active memberships (or block if 0). Workspaces created by Superadmin only | — |
| 2 | Who can export to Jira? | **Any user with `can_export` capability (resolved 2026-04-14).** Default profiles with it: Project Admin, Workspace Admin, Integration Admin, Superadmin. Not Member, not Team Lead | — |
| 3 | Post-export element changes — notify team of divergence? | **Visual indicator only, no notification (resolved 2026-04-14).** Banner on detail view shows "Has unexported changes since YYYY-MM-DD" with per-field diff (reuses EP-07 diff engine). Re-export action shows preview of diff before confirming upsert to Jira | — |
| 4 | Multiple workspaces per user? | **Yes (resolved 2026-04-14).** N workspaces per user via `workspace_memberships` n:m. Session stores `active_workspace_id`. UI has workspace switcher | — |
| 5 | Target scale | **Small — internal Tuio product (resolved 2026-04-14).** Realistic expectation: <100 total users, <50 workspaces, <5GB Postgres/year. No partitioning anywhere, no read replicas, no aggressive caching, SQLAlchemy default pool (5-10), 2 Celery workers per queue, 256MB Redis, 7-day PITR. Full product scope regardless — features are not gated by scale | — |
| 6 | LLM provider preference? | **Delegated to Dundun (resolved 2026-04-14, revised).** Our product has no LLM — all AI goes through `DundunClient`. Dundun handles provider, model, prompts (LangSmith), cost tracking, evals | — |
| 7 | Email notifications? | **No, in-app only (resolved 2026-04-14).** Final decision. No SMTP/SES, no digest, no templates | — |
| 8 | File attachments on elements? | **Yes (EP-16).** Images + PDFs. S3-compatible storage. Virus-scanned via ClamAV. | Object storage required; ClamAV integration required |
| 9 | Superadmin bootstrap? | **Config seed, no CLI (resolved 2026-04-14).** `SEED_SUPERADMIN_EMAILS` env var (or initial migration fixture): `david.aparicio@tuio.com`, `asis@tuio.com`. On first Google OAuth login, if email matches seed list → create user with `is_superadmin = true` and pin to `google_sub` thereafter. Once seeded, existing superadmins can promote other users via `POST /admin/users/:id/grant-superadmin` (audited). No CLI. All capabilities exposed as API + web | — |
