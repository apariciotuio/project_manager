# Implementation Plan — Work Maturation Platform

Actionable plan for implementing the 18 épicas. Assumes planning is complete (see `progress.md`, `decisions_pending.md`, `assumptions.md`).

**Precedence:** when this file conflicts with `decisions_pending.md` or `assumptions.md`, those win. Update this doc; don't flip the source of truth.

---

## 0. Context recap

- **Product:** Work Maturation Platform, internal Tuio, VPN-only
- **Users:** Tuio employees via Google OAuth (<100 expected)
- **Scale:** <50 workspaces, <5GB/year Postgres
- **Stack:** FastAPI + SQLAlchemy async · Next.js 14 + Tailwind · Postgres 16 + RLS · Redis · Celery · Alembic
- **External deps:** Dundun (AI layer), Puppet (search/RAG). Both behind client abstractions + fakes
- **Non-goals:** MVP framing · CRDT co-edition · complex RBAC · email/push notifications · observability stack (beyond stdlib log)

---

## 1. Ground rules (non-negotiable)

1. **TDD**: RED → GREEN → REFACTOR. Every production line has a failing test first. Enforced by code-reviewer agent before merge.
2. **Security by Design**: every endpoint asks "how can this be exploited?" before implementation. RLS verified per table. Authorization on every request (not just login).
3. **English only** in code, schemas, commits, docs. Spanish only in UI i18n and user-facing narrative (project_overview.md, megadocumento).
4. **Fakes over mocks.** `DundunClient` → `FakeDundunClient` injected in tests. `PuppetClient` → `FakePuppetClient`. No `mock.patch` on internal collaborators.
5. **Triangulation**: every behavior tested with ≥3 input variants (happy + boundary + error).
6. **Small commits.** Conventional format. `Refs: EP-XX`. One logical step per commit.
7. **No push without review.** Two gates: external `code-reviewer` agent → `review-before-push` workflow.
8. **Plan-driven.** Each EP consumes its `design.md` + `specs/` + `tasks-*.md`. No re-planning at impl time.
9. **Feature flags:** every net-new capability behind a flag until reviewed end-to-end in staging.
10. **Migration order is law.** See `tasks/consistency_review.md` §"Migration Order (Revised)".

---

## 2. Repo bootstrap (M0 — ~1 week of infra work)

Before any EP starts.

### Monorepo layout

```
project-root/
├── backend/
│   ├── app/
│   │   ├── domain/            # Entities, value objects, repository interfaces
│   │   ├── application/       # Services, validators
│   │   ├── infrastructure/
│   │   │   ├── persistence/   # SQLAlchemy repos, mappers, models
│   │   │   ├── adapters/      # DundunClient, PuppetClient, JiraClient
│   │   │   └── cache/         # Redis wrappers
│   │   ├── presentation/
│   │   │   ├── controllers/   # FastAPI routers
│   │   │   └── middleware/    # CorrelationID, Auth, Capability, RateLimit, CORS, InputValidation
│   │   └── config/            # Settings (pydantic-settings), DI container
│   ├── migrations/            # Alembic
│   └── tests/
│       ├── unit/
│       ├── integration/       # Real Postgres + Redis (testcontainers or docker-compose)
│       ├── fakes/             # FakeDundunClient, FakePuppetClient, FakeJiraClient
│       └── conftest.py
├── frontend/
│   ├── app/                   # Next.js App Router
│   ├── components/
│   ├── lib/                   # API client, WS client, diff engine
│   ├── hooks/
│   ├── styles/
│   ├── locales/               # i18n (ES primary)
│   └── __tests__/             # Vitest + React Testing Library + Playwright e2e
├── docker-compose.yml
├── docker-compose.dev.yml     # Postgres, Redis, MinIO, optional MailHog
├── .github/workflows/         # CI: lint, type, test, build
└── docs/
```

### M0 deliverables

- [ ] docker-compose.dev.yml with Postgres 16, Redis 7, MinIO (S3-compatible)
- [ ] FastAPI skeleton with health endpoint, correlation ID middleware, stdlib logging config
- [ ] Next.js skeleton with Tailwind, i18n, dark-mode toggle, dev proxy to backend
- [ ] Alembic initialized with empty baseline migration
- [ ] pydantic-settings config classes (`DundunSettings`, `PuppetSettings`, `JiraSettings`, `DatabaseSettings`, `RedisSettings`, `CelerySettings`, `AuthSettings`)
- [ ] Celery app with `default`, `dundun`, `puppet_sync` queues
- [ ] pre-commit hooks (black, ruff, mypy, eslint, prettier, tsc)
- [ ] CI pipeline: `lint → typecheck → test-backend → test-frontend → build`
- [ ] Integration test harness with `pytest-asyncio` + testcontainers (or equivalent)
- [ ] `FakeDundunClient` + `FakePuppetClient` skeletons with canned responses + record/replay
- [ ] `.env.example` with every env var documented

### M0 exit criteria

- `docker-compose up` brings the full stack
- `pytest` runs green (empty tests OK) with real Postgres
- `npm test` runs green (empty) with real API mock
- CI is green on main
- New developer can clone + run in <15 minutes with README

---

## 3. Milestones (18 EPs grouped)

Each milestone delivers end-to-end user value. Do NOT start M(N+1) without M(N) green in staging.

### M1 — Foundation (EP-00 + EP-01 + partial EP-08 + partial EP-10)

**Goal:** a user can log in, be in a workspace, and see an empty work-item list.

| EP | Scope | Deliverables |
|---|---|---|
| EP-00 | Auth + Bootstrap + Superadmin seed | Google OAuth flow, JWT HS256, `users` + `is_superadmin`, `workspaces`, `workspace_memberships`, session + active_workspace_id, workspace picker UI, `returnTo` deeplink, Superadmin seed from env (`SEED_SUPERADMIN_EMAILS`) |
| EP-01 | Core model + FSM | `work_items` (full canonical schema), FSM transition service with 14 edges, `timeline_events` skeleton, ownership + reassignment + override, basic CRUD API |
| EP-08 (partial) | Teams base | `teams` table with `deleted_at` soft-delete, team CRUD for Workspace Admin, team membership |
| EP-10 (partial) | Workspace admin skeleton | Members list + invite + profile assignment, capabilities + 5 profiles as code constants, audit_events table |

**Cross-cutting in M1:**
- PostgreSQL RLS policies on every domain table keyed by `workspace_id`
- `CapabilityMiddleware` enforcing `can_*` from `PROFILE_CAPABILITIES`
- `audit_events` writes on every profile change, FSM transition, override

**External dependencies used:** none (no Dundun, no Puppet, no Jira yet).

**Testing focus:**
- RLS: write tests with two tenants, attempt cross-tenant reads, confirm zero rows returned
- Auth: expired JWT, invalid signature, missing Google email, suspended membership
- FSM: every transition (legal + illegal), every invariant (last admin protection, suspended owner blocking)
- Multi-workspace: user with N memberships, switcher, active_workspace_id scoping

**Exit criteria:**
- Fresh deploy + seed supers can log in
- Superadmin creates a workspace, invites a user, user logs in, lands in workspace picker, selects, sees empty work_items list
- `workspace_id` leak tests all pass

---

### M2 — Capture & Chat (EP-02 + EP-03)

**Goal:** a user can create a work_item from a template, talk to the AI about it.

| EP | Scope | Deliverables |
|---|---|---|
| EP-02 | Capture + Drafts + Templates | JSON-schema typed templates (3 layers), template CRUD admin UI, draft auto-save, create from template, preserve `original_input` |
| EP-03 | Chat via Dundun proxy | `DundunClient` (HTTP + WebSocket), `conversation_threads` pointer table, WS proxy `/api/v1/ws/chat`, REST proxy for async tasks, callback endpoint `/api/v1/dundun/callback`, chat UI with progress frames, suggestion generation flow (agent invoke + callback + render via diff viewer when ready) |

**Cross-cutting in M2:**
- `DundunClient` protocol + `FakeDundunClient` for dev/test; integration harness records real Dundun responses in staging for replay
- Celery `dundun` queue wiring
- Split-view UX component (chat left, content right)
- Progress frame rendering in chat UI (italic transient lines)

**External dependencies used:** Dundun (fake in dev, real in staging).

**Testing focus:**
- Templates: schema validation (every primitive type), required field enforcement at Ready gate, merge of universal sections
- DundunClient contract: 202 + callback pattern, WS proxy forwarding, caller_role propagation, workspace_id scoping in fake
- Conversation thread: one `dundun_conversation_id` per user-thread, optional work_item link, last_message_preview cache

**Exit criteria:**
- User creates a Bug from template, fields enforce required
- User opens chat on the bug, has conversation via fake Dundun, sees progress frames
- Suggestion agent returns structured response, UI renders with diff placeholder (full diff viewer lands in M5)
- Staging run against real Dundun passes end-to-end

---

### M3 — Specification & Breakdown (EP-04 + EP-05)

**Goal:** a spec grows from draft to structured sections with tasks.

| EP | Scope | Deliverables |
|---|---|---|
| EP-04 | Completeness + Spec generation | `work_item_sections` table, granular 0-100% completeness score (weighted), `validation_rules` DB-backed, section archive Celery job, spec-gen via Dundun agent `wm_spec_gen_agent` (Celery + callback), gaps API |
| EP-05 | Breakdown + Hierarchy + Dependencies | `task_nodes` tree (adjacency + materialized path), `task_dependencies` with cross-work-item allowed, split/merge, breakdown via Dundun agent `wm_breakdown_agent` (Celery + callback), `dnd-kit` drag-drop UI, unmark-done action (explicit, no reverse FSM) |

**Cross-cutting in M3:**
- Celery callback pattern matures: shared `DundunTask` base class + timeout handling + retry
- `validation_rules` admin UI (scope preview for EP-06)

**External dependencies used:** Dundun (spec-gen + breakdown agents).

**Testing focus:**
- Completeness: weight math, partial sections, required-field gating
- Task tree: split preserves children, merge preserves dependencies, acyclic global validation
- Cross-item dependencies: cycle across work_items correctly rejected
- Dundun callback: idempotency (duplicate callbacks don't double-process), timeout fallback

**Exit criteria:**
- User triggers spec-gen, async job completes, sections appear with proposed content
- Completeness score shown live, advances as sections fill
- Breakdown generates task tree, user can drag-reorder, split a task, add cross-item dependency

---

### M4 — Reviews & Ready (finish EP-06, EP-08 full, EP-10 full)

**Goal:** work_items go through review and reach Ready.

| EP | Scope | Deliverables |
|---|---|---|
| EP-06 | Reviews + Validations + Ready | `review_requests` + `review_responses` + `validation_requirements`, editable validation_rules via API+UI, Ready gate with event emission, override with justification, last-admin protection |
| EP-08 (full) | Notifications + Inbox | `notifications` + idempotency dedup, SSE channel for in-app delivery, inbox UNION query, `AbstractEventBus` + `InProcessEventBus` impl, team assignments + routing hints |
| EP-10 (full) | Admin surface | Full admin UI (members, teams, validation rules, routing rules, templates, Jira config skeleton), audit log viewer, Superadmin surface (create workspace, cross-workspace user list, grant-superadmin, global audit, global health) |

**Cross-cutting in M4:**
- Event bus abstraction stabilized
- SSE client infrastructure (used by M5 timeline, M8 presence)
- Admin role separation (Workspace Admin vs Superadmin)

**External dependencies used:** Dundun (for suggestion agents within review flow).

**Testing focus:**
- Review fan-out: user vs team review, idempotent notifications
- Ready gate: every blocking validator blocks transition, override creates audit + timeline
- Event bus: in-process publish+subscribe, handler failure isolation, DI swap to Redis impl
- Admin invariants: last Workspace Admin can't demote self, no user assigns wider profile, seed superadmin bootstraps correctly
- SSE reconnect, stale connection cleanup

**Exit criteria:**
- Owner requests review → reviewer sees in inbox → approves → validation satisfies → owner sets Ready
- Admin configures a validation rule, new work_items apply it
- Superadmin creates workspace, assigns Workspace Admin, flow end-to-end

---

### M5 — Traceability (EP-07)

**Goal:** every change is audited, comparable, searchable, commentable.

| EP | Scope | Deliverables |
|---|---|---|
| EP-07 | Versions + Diff + Timeline + Comments | `work_item_versions` (full JSONB snapshot + TOAST), Markdown-aware diff engine (`remark` AST + `diff-match-patch`), full diff viewer UI (granular accept/reject, side-by-side, minimap, keyboard nav, LLM reasoning sidebar), outbox pattern for `timeline_events`, SSE real-time timeline push, per-user timeline, timeline JSON/CSV export, `comments` + reactions + mentions + edit history + version tags |

**Cross-cutting in M5:**
- Diff viewer is THE core interaction — 1-2 weeks of frontend effort
- Outbox pattern: `outbox` table + Celery worker + idempotency keys
- Timeline search delegates to Puppet (requires M6 sync pipeline — flag this dependency)

**External dependencies used:** none new (Puppet comes in M6).

**Testing focus:**
- Diff viewer: word-level + section-level diff correctness, partial accept, round-trip undo
- Outbox: transaction semantics, crash recovery (kill worker mid-drain), event loss zero
- Versions: permanent delete audit trail, user-authored with commit message, tagging
- Comments: mention notification fires, reaction idempotency, edit history preserves prior state

**Exit criteria:**
- User sees full version history with diffs, can partially accept a suggestion
- Timeline real-time pushes on team member activity
- Comments with mentions trigger notifications; reactions toggle idempotently
- Outbox recovers from simulated crash (no lost timeline events)

---

### M6 — Workspace visibility (EP-09 + EP-13 + EP-12)

**Goal:** searchable workspace with dashboards; Puppet in place.

| EP | Scope | Deliverables |
|---|---|---|
| EP-13 | Puppet integration | `PuppetClient` (HTTP), push-on-write sync pipeline (Celery `puppet_sync` queue, triggered by domain events), tag scheme `wm_<workspace_id>` + sub-tags, health check + lag monitor, degraded-mode UI ("search unavailable") |
| EP-09 | Listings + Dashboards + Search | Cursor-pagination listings with filters (state, owner, type, team, tag, date), dashboards (global/owner/team/pipeline) with Redis 60s cache, `saved_searches` + CRUD, searchbar UI calls backend → Puppet, prefix type-ahead, Kanban drag-drop with state transition validation, quick filters "My Items" |
| EP-12 | Responsive + Security + Performance | Response time targets documented, rate limiting (token bucket per user/IP), CORS config, CSRF (SameSite=Strict), responsive layout audit, accessibility basics (ARIA), `CorrelationIDMiddleware` (already from M0 — verify), stdlib logging config polished |

**Cross-cutting in M6:**
- Puppet sync pipeline is risky — outbox-backed to prevent event loss
- EP-12 is transversal: verify across all prior EPs (not a separate feature slice)

**External dependencies used:** Puppet (fake in dev, real in staging).

**Testing focus:**
- Puppet sync: push-on-write, 3s lag target measured in integration test
- Degraded mode: Puppet down → searchbar shows unavailable; CRUD continues
- Dashboards: cache invalidation on state transitions, correct counts at 10x expected data
- Rate limiting: per-user/IP enforcement, test burst + sustained
- Listings: RLS verified again with tenant isolation under concurrent writes

**Exit criteria:**
- Creating a work_item → searchable in <3s via Puppet
- Dashboards match reality across 500+ work_items load-test
- Search degrades gracefully when Puppet down

---

### M7 — Jira integration (EP-11)

**Goal:** exportable and importable between the platform and Jira.

| EP | Scope | Deliverables |
|---|---|---|
| EP-11 | Jira export + import | `JiraClient` (HTTP), `integration_configs` (project-scoped), `integration_exports` (snapshots, upsert-by-key), export endpoint with `updated_at` divergence check, import endpoint `POST /api/v1/work-items/import-from-jira`, type mapping config, divergence banner + diff preview pre-reexport |

**Cross-cutting in M7:**
- Fernet credential encryption (established in M1, exercised here)
- No `sync_logs`, no polling, no webhooks (explicit)

**External dependencies used:** Jira API.

**Testing focus:**
- Export: upsert with preserved external edit → warning + require confirm
- Import: creates work_item in `draft` state with `jira_source_key`, can't re-import linked issue
- Round-trip: import → mature → export → same issue updated (closes the loop)
- Auth failure, rate limit response, retry with original snapshot
- Permission: `can_export` gates the endpoint; audit logs every export/import

**Exit criteria:**
- Export a Ready work_item to a test Jira instance, verify upsert
- Import an existing Jira issue, mature it, re-export, verify same issue updated
- Admin configures per-project mapping via UI

---

### M8 — Polish features (EP-14 + EP-15 + EP-16 + EP-17)

**Goal:** hierarchy, tags, attachments, collaboration features.

| EP | Scope | Deliverables |
|---|---|---|
| EP-14 | Hierarchy: Milestones + Stories | Types added (`milestone`, `story`), parent-child rules, tree view API + UI, completeness roll-up from children to parent |
| EP-15 | Tags + Labels | `tags` + `work_item_tags`, admin UI (rename/merge/archive), autocomplete + AND/OR filters, tag propagation to Puppet sync pipeline |
| EP-16 | Attachments (VPN-simplified) | `attachments` table, object storage (MinIO) integration, authenticated streaming endpoint `GET /api/v1/attachments/:id/download`, PDF thumbnails via `pdf2image` + Pillow (Celery), inline images in comments (paste/drag), admin quota dashboard, size + rate limits |
| EP-17 | Edit locking + Presence | Section-level locks (`locks` table), lock-holder heartbeat, 5-min auto-release, force-unlock with audit, unlock request notification, presence service (SSE events `user.viewing` / `user.editing_started` / `user.typing`), "N viewing" + "X editing" UI indicators |

**Cross-cutting in M8:**
- SSE channel from M4 + M5 reused for presence
- Locks interact with Ready gate: transition blocked while required sections are locked

**External dependencies used:** MinIO (object storage).

**Testing focus:**
- Hierarchy: parent-child type compatibility, cycle prevention, roll-up math
- Tags: merge preserves references, archived tag hidden but queryable
- Attachments: authenticated streaming access control, PDF thumbnail generation job, inline image paste in comment
- Locks: expiry cleanup, force-unlock audit, concurrent edit detection
- Presence: ephemeral vs transactional semantics

**Exit criteria:**
- Create a Milestone, add Stories under it, see roll-up completeness
- Tag multiple work_items, filter with AND/OR, admin merges two tags
- Upload PDF, thumbnail generates async, download via authenticated endpoint
- Two users editing different sections concurrently, see presence + own locks

---

## 4. External dependency strategy

| Dep | Dev | Staging | Prod | Fake strategy |
|---|---|---|---|---|
| Dundun | `FakeDundunClient` | Real Dundun (staging Temporal) | Real Dundun | `FakeDundunClient` implements `DundunClient` protocol, returns canned responses per agent, supports recording real responses for replay |
| Puppet | `FakePuppetClient` | Real Puppet (dev instance at `puppet.internal.dev.tuio.com`) | Real Puppet | `FakePuppetClient` stores docs in-memory dict, supports tag filter, returns ranked results by string match |
| Jira | Jira sandbox | Jira staging | Jira prod | Real Jira always; use throw-away test instance in unit/integration |
| Object Storage (MinIO) | Local MinIO container | Staging MinIO | MinIO or S3 | Real MinIO in all envs; trivial setup |

**Rules:**
- Every external integration has a protocol/interface in `domain/ports/` and an impl in `infrastructure/adapters/`
- Fakes live in `tests/fakes/` and are shared across unit + integration tests
- Contract tests run against real deps in staging only — confirm fake behavior matches real responses
- Never hit production deps from dev or CI

---

## 5. Cross-cutting concerns

### Multi-tenancy enforcement

Every domain table has `workspace_id UUID NOT NULL REFERENCES workspaces(id)`. PostgreSQL Row-Level Security policies:

```sql
CREATE POLICY tenant_isolation ON work_items
  USING (workspace_id = current_setting('app.workspace_id')::uuid);
```

Backend sets `SET LOCAL app.workspace_id = ...` per request inside transaction. Every SELECT/UPDATE/DELETE scoped automatically. Integration tests verify isolation with a two-tenant fixture.

### Authorization

- `require_capability(capability: str)` FastAPI dependency
- `PROFILE_CAPABILITIES` dict in code constants (5 profiles); `users.is_superadmin` flag separate
- Capability check after auth but before business logic
- Invariants: last Workspace Admin protection, no-wider-profile-than-own, all changes audited

### Event bus

- `AbstractEventBus` interface
- Default `InProcessEventBus` (in-memory dict of subscribers)
- DI-swappable to `RedisEventBus` if multi-service emerges
- Outbox pattern for `timeline_events` only (reliability-critical)

### Correlation IDs

- `CorrelationIDMiddleware` generates UUID per request, adds to log context
- Propagates through Celery tasks via headers
- Dundun callback carries correlation ID of original request
- All logs include `correlation_id`; debug via `docker logs | grep <id>`

### Caching

- Redis 256MB target (small scale)
- Dashboards: 60s TTL, invalidated on state transition events
- Templates: 300s TTL, invalidated on template CRUD
- OAuth state: single-use, delete after validation

### Secrets

- Env vars only; never committed
- `.env.example` documents every var
- Jira credentials Fernet-encrypted with rotation path
- `SEED_SUPERADMIN_EMAILS` env var for bootstrap

---

## 6. Testing strategy

### Unit tests (per EP)

- TDD-first. RED → GREEN → REFACTOR.
- Pure domain logic: services, entities, transition rules, template validators
- Target: 100% natural coverage (exclude `__init__.py`, migrations, TYPE_CHECKING, abstractmethod)
- Triangulation enforced: every behavior tested with ≥3 input variants

### Integration tests

- Real Postgres in docker/testcontainers
- Real Redis in docker
- RLS policies exercised with two-tenant fixtures
- Fakes for Dundun + Puppet + Jira
- Celery eager mode (`CELERY_TASK_ALWAYS_EAGER=True`) for sync execution in tests

### Contract tests

- Run in staging against real deps
- Compare fake behavior to real responses; fail if divergent
- Gated behind env flag; CI runs on staging deploys only

### E2E

- Playwright on staging
- Critical flows: login → workspace pick → create work_item → chat → spec gen → review → Ready → export
- Smoke tests on prod after deploy

### Coverage + quality gates

- CI fails if backend coverage <90% on new lines
- Type check (mypy strict) mandatory
- Ruff + black + eslint + prettier + tsc on pre-commit
- Security lint: `bandit` for Python, `eslint-plugin-security` for TS

---

## 7. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Dundun integration delays | Medium | Blocks M2/M3/M4 | `FakeDundunClient` unblocks dev; staging integration tested early (during M2) |
| Puppet sync pipeline lag | Medium | Degraded search UX | Outbox-backed push; health monitor; degraded-mode UI planned |
| RLS policy gap leaks data across tenants | Low | Critical | Two-tenant integration tests per table; security review before M2 exit |
| Outbox worker drift | Low | Lost timeline events | Idempotency keys; dead-letter queue; restart-recovery test |
| Diff viewer complexity | Medium | Delays M5 | Isolate as standalone component with own tests; Monaco fallback plan B |
| Migration order mistake | Medium | Deploy broken | Alembic migration order enforced per consistency_review.md §"Migration Order"; rehearsal on staging before prod |
| Jira rate limits | Low | Export fails under load | Retry with backoff + original snapshot; admin notified on repeated failure |
| Google OAuth misconfig | Low | Auth broken | Tested in dev + staging before prod cutover |
| Seed superadmin leak (email matched incorrectly) | Low | Privilege escalation | Email matched only on first login + pinned to `google_sub`; subsequent logins check sub, not email |

---

## 8. Deployment plan

### Environments

- **Dev**: local `docker-compose.dev.yml`
- **Staging**: mirror of prod on internal infrastructure, behind VPN
- **Prod**: internal Tuio VPN, single tenant deployment

### Rollout

1. Staging deploy on every merge to `main`
2. Smoke tests + E2E run automatically
3. Manual QA approval via admin dashboard
4. Prod deploy via controlled release (backend first, frontend second)
5. Feature flags default off on prod until reviewed live

### Migrations

- Alembic with order from `consistency_review.md` §"Migration Order"
- Dry-run on staging before prod
- Backward-compatible migrations (add nullable col → backfill → make NOT NULL in two releases)
- No destructive migrations without dual-run period

### Observability (scoped)

- stdlib `logging` to stdout, captured by `docker logs`
- `CorrelationIDMiddleware` for request tracing
- Health endpoint `/api/v1/health` with DB + Redis + Dundun + Puppet checks
- Debug via ssh + `docker logs | grep <correlation_id>` (explicitly accepted — decision #27)

---

## 9. Milestone calendar (indicative)

Rough shape, not a commitment. Single-developer estimate with AI assistance.

| Milestone | Indicative duration |
|---|---|
| M0 | 3-5 days |
| M1 | 2-3 weeks |
| M2 | 2-3 weeks (+Dundun integration risk) |
| M3 | 2-3 weeks |
| M4 | 2-3 weeks |
| M5 | 3-4 weeks (diff viewer is the long pole) |
| M6 | 2-3 weeks (+Puppet integration) |
| M7 | 1-2 weeks |
| M8 | 2-3 weeks |

**Total:** ~18-27 weeks of focused work. Paralelizable partially on the frontend/backend split per EP.

---

## 10. Kick-off checklist

When you start implementation, in this order:

1. [ ] Read `progress.md` top section, `decisions_pending.md`, `assumptions.md`
2. [ ] Decide infrastructure target (bare VM / Docker / k8s) — not a blocker for M0
3. [ ] Set up `SEED_SUPERADMIN_EMAILS` + LLM-related Dundun env vars in a secrets manager
4. [ ] Bootstrap the monorepo per §2 (this is M0)
5. [ ] Verify CI green on an empty commit
6. [ ] Start M1 EP-00 with `tasks/EP-00/design.md` + `specs/` + `tasks-backend.md` as the source
7. [ ] Pipeline per EP: `plan-backend-task` → `develop-backend` → `plan-frontend-task` → `develop-frontend` → `code-reviewer` → `review-before-push`
8. [ ] After each EP: update `progress.md` (mark impl status, note surprises, flag new risks)

---

## 11. What is explicitly NOT in scope

- CRDT / Operational Transform (no simultaneous co-edition)
- Complex RBAC (capability array + 5 profiles + superadmin flag)
- Email/push notifications
- External APM (Sentry, Datadog, New Relic, PostHog)
- ClamAV virus scanning (VPN product)
- Signed URLs for attachments (VPN product)
- Elasticsearch (Puppet is the single search backend)
- Cross-workspace UI for non-superadmin roles
- Role templates / custom roles / bulk CSV import
- Workspace suspension UI (deferred)
- Impersonate capability (deferred; security risk)
- Webhook delivery for Jira (only user-initiated import)
- Real-time Jira sync (none; polling also dropped)

---

## Revision history

- 2026-04-14: initial draft after full planning round (32 resolved decisions + 18 EPs enriched)
- 2026-04-16: EP-03 Phase 7 verified + Phase 8 security review; EP-04 Phase 1-5 + controllers
- 2026-04-16: EP-05..EP-17 baseline backend (migrations + domain + repos + services + controllers)
- 2026-04-17: EP-05..EP-17 full service layer (parallel agents); all ORM models; 1052 backend tests
- 2026-04-17: Frontend complete (workspace layout, items list, item detail 5-tab, create, inbox, teams, admin); 298 frontend tests
- 2026-04-17: EP-18 MCP server skeleton (15 tools, stdio+SSE)
- 2026-04-17: Workspace flow fix (GET /workspaces/mine endpoint, JWT refresh, middleware, hydration)
- 2026-04-17: Dev seed script (8 work items + tags + team + tasks)
