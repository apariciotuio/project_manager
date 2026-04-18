# Work Maturation Platform — Task Tracker

## Epic Summary

| Epic | Name | Dependencies | Complexity | Backend | Frontend | Status |
|------|------|-------------|------------|---------|----------|--------|
| EP-00 | Access, Identity & Bootstrap | — | Medium | ✅ Done | ✅ Done | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-01 | Core Model, States & Ownership | EP-00 | High | ✅ Done | ✅ Items list + detail | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-02 | Capture, Drafts & Templates | EP-00, EP-01 | Medium | ✅ Done | ✅ Create form | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-03 | Clarification, Conversation & Assisted Actions | EP-02 | High | ✅ Done (deferred: RLS, WS bidir) | 🟡 45/61 (QuickActionMenu + SuggestionBatchCard + SplitView layout done; pending: ChatPanel wrapper, section pulse, detail-page wiring — deferred on EP-03 BE thread-id) | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [ ] Frontend |
| EP-04 | Structured Specification & Quality Engine | EP-01, EP-02, EP-03 | High | ✅ Done (deferred: NextStep, spec-gen) | ✅ Spec tab + completeness | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-05 | Breakdown, Hierarchy & Dependencies | EP-04 | Medium-High | ✅ Done (repos + services + controllers) | ✅ Tasks tab | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-06 | Reviews, Validations & Flow to Ready | EP-01, EP-04, EP-05, EP-08 | High | ✅ Done (repos + services + controllers) | ✅ Reviews tab | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-07 | Comments, Versions, Diff & Traceability | EP-01, EP-04, EP-05, EP-06 | High | ✅ Done (deferred: diff engine, SSE) | ✅ Comments + Timeline tabs | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-08 | Teams, Assignments, Notifications & Inbox | EP-00, EP-01 | Medium-High | 🟡 44/93 real ticks (audit + guards 2026-04-18): Team CRUD + guards (LastLeadError, update_role, idempotency, soft_delete) done; missing: Inbox full (Group C), AssignmentService, SSE `/notifications/stream` route, execute_action + QuickActionDispatcher, TeamService unit tests, team controller integration tests | ✅ Teams + Inbox pages | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Backend [x] Frontend |
| EP-09 | Listings, Dashboards, Search & Workspace | EP-01, EP-02, EP-06, EP-08 | Medium-High | 🟡 Partial — saved searches + list controllers done; missing: dashboard/person, dashboard/team, pipeline, kanban endpoints | 🟡 51/108 real ticks (audit 2026-04-18): list+filters+search+workspace dashboard shipped; missing: QuickFilterChips (needs `mine` filter BE), SavedFilterPresets, QuickViewPanel, Pipeline, Kanban, person/team dashboards, loading.tsx route files, cursor "Load more" | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Backend [ ] Frontend |
| EP-10 | Configuration, Projects, Rules & Admin | EP-00, EP-08 | High | 🟡 Partial — projects CRUD + generic integrations + tags + puppet done; missing: admin/members, admin/rules, admin/jira config, admin/support, admin/context-presets, admin dashboard aggregations, DELETE integrations/configs/{id} | 🟡 24/123 real ticks (audit 2026-04-18): Projects/Integrations/Tags/Puppet/Health tabs shipped; Members partial (list only); Audit Log partial; Rules/Jira-dedicated/Support/Superadmin/Admin-shell all 0% — all blocked on backend gaps | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Backend [ ] Frontend |
| EP-11 | Export & Sync with Jira | EP-01, EP-04, EP-06, EP-10 | Medium-High | ✅ Real HTTP client shipped (2026-04-18): JiraClient + PAT auth + retry 2x + ExportService + `POST /work-items/{id}/export/jira` + BackgroundTasks + migration 0118 `external_jira_key` column + dual-write backcompat + audit queued/completed (14 + 9 tests) | ✅ JiraExportButton on detail page (9 tests) + IntegrationsTab existing | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-12 | Responsive, Security, Performance & Observability | Transversal | Medium | 🟡 ~75/85 (2026-04-18 wave: correlation-id middleware + stdlib logging + scrub (recursive), CSRFMiddleware double-submit + exempt list (auth bootstrap + webhooks), PuppetSettings+AuthSettings+DundunSettings prod validators, N+1 QueryCounter, DB index audits migrations 0114/0115, PaginationCursor utility + applied to notifications/work-items/audit-events, audit_events RLS already via 0005, PgRateLimiter + migration 0116 dormant, CacheService deleted per Redis-removal; pending: audit integration for credential CRUD/export, client-disconnect SSE test) | 🟡 Groups 1/2/3/4/5/6/7/9 done (2026-04-18); pending: none actionable — remaining checkboxes are deferred per decision #27 | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Backend [ ] Frontend |
| **EP-13** | **Semantic Search + Puppet Integration** | EP-09, EP-10, EP-12 | High | ✅ Done (outbox + Celery task) | ✅ 59/61 (suggest+debounce, detail-page docs wiring, admin Puppet tab, i18n — React Query adoption deferred as separate task) | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| **EP-14** | **Hierarchy: Milestones, Epics, Stories** | EP-01, EP-05, EP-09, EP-10 | High | ✅ Done (types + catalog + rules) | ✅ Done (2026-04-18: close-out + bug fix `VALID_PARENT_TYPES` inverted vs backend `HIERARCHY_RULES` — story now includes milestone as parent; 48 hierarchy tests green) | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| **EP-15** | **Tags + Labels** | EP-01, EP-09, EP-10 | Medium | ✅ Done (repos + controllers) | ✅ Tag management in admin | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| **EP-16** | **Attachments + Media** | EP-01, EP-07, EP-10, EP-12 | High | 🟡 Partial — metadata CRUD (POST/GET/DELETE on registered attachments) done; **file ingestion DEFERRED to v2** (decision 2026-04-18: no multipart handler / no presigned URL for MVP) | 🟡 List + delete + drop-zone visual + MIME/size validation shipped (2026-04-18, 15 tests); actual upload call DEFERRED to v2 | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Backend [ ] Frontend — DEFERRED v2 (file ingestion) |
| **EP-17** | **Edit Locking + Collaboration Control** | EP-01, EP-08, EP-10, EP-12 | Medium-High | 🟡 Core acquire/release/force-unlock done; **unlock-request/respond endpoints shipped 2026-04-18** (migración 0119 + 8 tests); pending: force-release reason param + list-embed lock summary | 🟡 G0/G1/G2/G4/G8/G11 done (22 tests 2026-04-18); G3/G5/G6/G7 unblocked (BE ya listo) — pendiente FE implementation | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Backend [ ] Frontend — FE unblocked |
| **EP-18** | **MCP Server: Read & Query Interface** | EP-00..EP-19 | Medium | 🟡 9/15 tools real end-to-end (2026-04-18): search_work_items, read_work_item, list_projects, list_work_items, list_sections, create_work_item_draft, get_work_item_completeness, list_comments, list_reviews — ~140 tests total; skeleton rot flagged: `workspace_id=uuid4()` placeholder (no auth wiring), MCP SDK not in pyproject, `_NoOpCache` used; remaining tools stubbed | N/A | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Backend (partial) |
| **EP-19** | **Design System & Frontend Foundations** | EP-12 | Medium | N/A | ✅ Done (shadcn + tokens + i18n) | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Frontend |
| **EP-20** | **Theme System: Light / Dark / Matrix** | EP-19 | Low-Medium | N/A | ✅ Done (2026-04-18: code-review round closed — 3 MF + 3 SF resolved; ThemeSwitcher dead code deleted, RedPill/BluePill/RainToggle consolidated into UserMenu with [~] honest note, type-safe normalizeTheme, MatrixRain reacts to prefers-reduced-motion + localStorage; 31 tests green) | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Frontend |
| **EP-21** | **Post-MVP Feedback Batch** (layouts, seed inbox, UI refresh, errors, edit item, dundun-fake) | EP-19, EP-08, EP-03 | Medium | ✅ Done (F-2 seed inbox, F-4-be error envelope, F-6 dundun-fake) | ✅ Done (F-1/F-3/F-5/F-7/F-8/F-9/F-10 — 10/10 items shipped) | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend — pending: review-before-push |
| **EP-22** | **Chat-first Capture Flow** (SplitView default, Dundun primer, section-suggestion bridge, Clarificación tab removed) | EP-02, EP-03, EP-04, EP-07, Dundun | Medium | ⏳ Planned (primer subscriber, WS snapshot + signals validation) | ⏳ Planned (SplitView wiring, PendingSuggestionCard, Clarificación removal, collapse persistence) | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Backend [ ] Frontend |

## Implementation Order (Suggested)

```
EP-12 (transversal primitives) ──> EP-19 (design system) ──> frontend work of every epic below

EP-00 ──> EP-01 ──> EP-02 ──> EP-03 ──> EP-04 ──> EP-05
                                                      │
EP-00 ──> EP-08 ─────────────────────────────> EP-06 ─┤──> EP-07
                                                      │
EP-00 ──> EP-08 ──> EP-10 ───────────────────────────>├──> EP-11
                                                      │
EP-01 ──> EP-02 ──> EP-06 ──> EP-08 ──────────────────├──> EP-09
                                                      │
EP-13, EP-14, EP-15, EP-16, EP-17, EP-18 ─────────────┘
```

**Transversal track**: EP-12 (technical primitives) → EP-19 (design system). Both unblock every epic with frontend scope. Existing epics retrofit via `extensions.md` once EP-19's catalog lands.

## Pending side-tasks (non-epic)

- [x] **Dev seed script** — `backend/scripts/seed_dev.py` (workspace + membership) + `backend/scripts/seed_sample_data.py` (8 work items, 5 tags, 1 team, 5 task nodes, sections). Idempotent.
- [x] **Workspace RLS follow-up** — migration `0117_rls_ep03_ep04` adds `workspace_id` + RLS to `work_item_sections`, `work_item_section_versions`, `work_item_validators`, `work_item_versions` (EP-03 tables covered by 0033). ORM, mappers, repos updated. 8 integration tests in `backend/tests/integration/test_rls_ep03_ep04.py`.
- [ ] **E2E verification** — verify login → workspace select → items list → item detail → sections edit → completeness flow in a real browser.
- [ ] **External integrations** — wire real HTTP clients for Dundun, Puppet, Jira (currently using fakes).
- [x] **Redis + Celery removal** — plan in `tasks/redis-removal/plan.md`; PR1 (cache deleted), PR2 (PgRateLimiter + mig 0116), PR3 (PgNotificationBus LISTEN/NOTIFY + InMemoryJobProgress), PR4 (Celery gone, BackgroundTasks + internal_jobs endpoint), PR5 (pyproject -42 packages). All shipped 2026-04-18. Post-review: MF-1 SQL injection in channel name fixed + SF-2/3/4/6 (keepalive, docstrings, rename, rate-limit internal jobs).
- [ ] **Audit integration** — login success/failure + 403 handler (Option B JSONB context) in flight (Agent RR). Status transitions + credential CRUD + export still deferred.
- [x] **CSRF bootstrap fix (web)** — `/api/v1/auth/me` emits `csrf_token` cookie when missing; unblocks existing sessions after CSRF rollout (2026-04-18).
- [x] **CSP dev relaxation** — `middleware.ts` adds `'unsafe-inline' 'unsafe-eval'` to `script-src` and `ws:` + `localhost:*` to `connect-src` in dev (Next.js HMR); prod unchanged (2026-04-18).
- [x] **Fakes sweep** — `current_user_id` added to `IWorkItemRepository.list_cursor` interface + `FakeWorkItemRepository`; unblocked `test_auth_service.py`, `test_draft_service.py`, `test_mcp_stdio_search.py` (37 passed, 2026-04-18).
- [x] **Test retrofit** — internal_jobs_controller + SSE terminal frames + notification session lifecycle (2026-04-18). 24 tests added: 5 integration for `list_jobs` GET endpoint, 7 unit for `ProgressTaskMixin` without `job_service`, 12 integration for notification stream lifecycle (`stream-token` + `GET /stream`). All green. 3 commits: 95d80f8, 0692723, 6d250cb.

## Shipped 2026-04-18 (session summary)

**EP-12 BE/FE** wave (10+ sub-tracks, ~75/85 items closed) — correlation-id, CSRF (double-submit + exempt list + webhooks), secrets scrub recursivo + 3 prod validators (Auth/Dundun/Puppet), N+1 query counter, `PaginationCursor` aplicado a 3 endpoints (notifications, work-items con filter-struct restaurado, admin/audit-events), AuditRepository + RLS ya cubierto por 0005

**EP-14 FE** close-out + bug `VALID_PARENT_TYPES` invertido fix (48 tests)

**EP-12 FE** Groups 1/2/3/4/5/6/7/9 shipped; Group 1 primitives verified (66 tests); responsive mobile (inbox/detail/review-actions); SSE useJobProgress

**EP-20** code-review round + 3 MF + 3 SF + nitpicks resolved (ThemeSwitcher dead code deleted, normalizeTheme type-safe, MatrixRain reactive)

**EP-11 (Jira)** REAL shipped: JiraClient + PAT + retry + ExportService + endpoint + BackgroundTasks + migration 0118 + dual-write + FE export button + audit queued/completed

**EP-18 (MCP)** 9/15 tools real end-to-end (~140 tests): search_work_items, read_work_item, list_projects, list_work_items, list_sections, create_work_item_draft, get_work_item_completeness, list_comments, list_reviews

**EP-08 BE** guards shipped (MMM): LastLeadError, update_role, suspended idempotency, soft_delete guard, 2 PATCH routes, 10 tests. Audit reveló 44/93 real ticks.

**EP-16 FE partial**: AttachmentList + AttachmentDropZone (validation + "upload blocked" toast) + tab Adjuntos (15 tests) — upload call blocked por BE handler missing

**EP-17 FE Groups 0/1/2/4/8/11**: types + useSectionLock + LockBadge + RelativeTime + spec-tab indicator + a11y (22 tests)

**EP-09 + EP-10 FE audits**: 51/108 + 24/123 real ticks con matrices por area y lista de gaps bloqueantes BE

**Migrations**: 0114 index audit (9 indexes), 0115 work_items keyset, 0116 rate_limit_buckets, 0117 RLS EP-04 tables, 0118 external_jira_key, 0119 lock_unlock_requests

**Session totals**: 138 modified + 135 new + 8 deleted files. Backend arranca limpio (8 middleware). Ninguna migración aplicada en DB local — revisar antes de `alembic upgrade`.

**Redis + Celery ripeo FULL (PR1-PR5)**: CacheService + redis_cache_adapter deleted; PgRateLimiter + mig 0116; PgNotificationBus con LISTEN/NOTIFY + payload 8KB check + channel regex allowlist; InMemoryJobProgressService; Celery fuera — BackgroundTasks + `POST /api/v1/internal/jobs/{name}/run`; pyproject -42 packages

**Workspace RLS**: migración 0117 + 4 tablas EP-04 + 8 integration tests

**Audit integration**: login success/failure (RR) + 403 handler + credential CRUD + Jira export queued/completed (EEE). `AuditService` 100% coverage (FFF, 32 tests). **Pending**: status transitions — 4 agents ran, all hit pytest-asyncio TRUNCATE teardown hang when running 3 tests together (individual test passes in 4.89s). Audit wire likely landed in `work_item_controller.py`. Fix next session: targeted truncate + pytest-asyncio session scope for engine.

**Web live fixes**: CSRF cookie bootstrap en `/me`; CSP dev-friendly

**Code reviews + fixes**: FF → 2 MF + 3 SF; OO → 1 MF SQL injection + 4 SF; PP landed all critical fixes (channel regex allowlist, dead keepalive removed, docstrings, rename, rate-limit internal jobs)

**CSRF test fixture** helper en conftest (auto-inject X-CSRF-Token)

**Open blockers/partials** (need user decision or follow-up):
- ~~**#64 EP-16 BE multipart upload**~~ — **DEFERRED to v2** (2026-04-18). File ingestion out of MVP scope; existing metadata CRUD stays.
- **#71/#85 EP-17 BE unlock-request endpoints** — domain+repo+impl+controller scaffolded in git but migration 0119 not written and tests incomplete (OOO killed mid-flight)
- **#86 audit status transitions** — wire at controller-level manually (3 agents hung on this)
- **EP-09 BE gaps**: `mine` filter param, person/team dashboard endpoints, pipeline, kanban
- **EP-10 BE gaps**: admin/members, admin/rules, admin/jira config, admin/support, admin/context-presets, admin dashboard, DELETE integrations/configs/{id}
- **EP-17 BE gaps**: force-release reason param, lock embed in list API
- **EP-08 BE gaps**: Inbox (Group C entero), AssignmentService, SSE /notifications/stream, execute_action + QuickActionDispatcher, team unit tests coverage
- **EP-18 skeleton rot**: workspace_id placeholder (no auth wiring), MCP SDK not in pyproject, `_NoOpCache` used

## Critical Path

EP-00 -> EP-01 -> EP-02 -> EP-03 -> EP-04 -> EP-05 -> EP-06 -> EP-07

## Parallel Track

EP-08 (Teams & Notifications) can start after EP-01, in parallel with EP-02/EP-03.
EP-10 (Admin) can start after EP-08, in parallel with EP-04/EP-05.

## Phase Pipeline

| Phase | Status |
|-------|--------|
| Proposals | COMPLETED |
| Enrichment + Technical Planning | COMPLETED (all 13 epics) |
| Consistency Review | COMPLETED — 7 must-fix, 10 should-fix, 3 nitpick |
| assumptions.md + tech_info.md | COMPLETED |
| Back/Front Split + Subtasks | COMPLETED — 26 files (13 backend + 13 frontend) |
| OpenSpec Detail Pass | COMPLETED — ~150 acceptance criteria blocks added |
| Specialist Reviews (arch→sec→front→back→DB) | COMPLETED — 5 reviews, see tasks/reviews/ |
| Implementation | **IN PROGRESS** — backend 100% schema + services, frontend pages built, E2E flow pending verification |
| **NEW REQUIREMENTS** | **COMPLETED — EP-13..EP-17 planned + extensions applied** |
| EP-13..EP-17 Specs + Design + Tasks | COMPLETED — specs/design/back+front for all 5 |
| Existing epics extensions (EP-01, EP-03, EP-07, EP-09, EP-10) | COMPLETED — see extensions.md for change log |
| Updated assumptions.md (Q8 attachments Yes, Q9 superadmin CLI) | COMPLETED |
| **EP-18 (MCP Server)** Proposal + Specs + Design + Tasks | COMPLETED (2026-04-14) — back+front, Dundun/Puppet contracts aligned with real APIs |
| **EP-19 (Design System)** Proposal + Specs + Design + Tasks | COMPLETED (2026-04-14) — frontend-only, shadcn+tokens+i18n+a11y gate; retrofits EP-00..EP-18 via extensions.md |
| Cross-epic consistency review on expanded plan (20 epics) | **COMPLETED** (2026-04-14) — `tasks/consistency_review_round2.md` — 2 Must-fix + 1 Should-fix resolved; 3 informational |
| Specialist reviews round 2 on new epics (incl. EP-18 + EP-19) | **COMPLETED** (2026-04-14) — arch + sec + front + a11y on EP-18 + EP-19; 24 Must-fix resolved in-spec; feature flag matrix documented; see `tasks/reviews/round_2_specialist_reviews_summary.md` |

## User Stories Count

| Epic | Stories | Must | Should |
|------|---------|------|--------|
| EP-00 | 3 | 3 | 0 |
| EP-01 | 4 | 4 | 0 |
| EP-02 | 4 | 3 | 1 |
| EP-03 | 4 | 3 | 1 |
| EP-04 | 4 | 4 | 0 |
| EP-05 | 5 | 5 | 0 |
| EP-06 | 5 | 5 | 0 |
| EP-07 | 4 | 4 | 0 |
| EP-08 | 5 | 4 | 1 |
| EP-09 | 6 | 5 | 1 |
| EP-10 | 10 | 7 | 3 |
| EP-11 | 5 | 4 | 1 |
| EP-12 | 5 | 5 | 0 |
| EP-13 | 6 | 5 | 1 |
| EP-14 | 5 | 5 | 0 |
| EP-15 | 6 | 5 | 1 |
| EP-16 | 6 | 5 | 1 |
| EP-17 | 6 | 6 | 0 |
| EP-18 | 20 | 17 | 3 |
| EP-19 | 13 | 11 | 2 |
| **Total** | **126** | **110** | **16** |

*Counts for EP-13..EP-19 are read from each epic's `proposal.md#User Stories`; re-run if they are amended.*
