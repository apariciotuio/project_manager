# Session resume — 2026-04-16 (late session)

This session extended the previous 2026-04-16 snapshot. Picking up with
`fa84b2e` the agent closed EP-03 Phase 7+8, then landed baseline
implementations for EP-04..EP-17 backend. Frontend untouched.

## Running totals

- 30 Alembic migrations (0001..0030, all within the alembic_version VARCHAR(32) cap).
- Full regression: **994 passed, 1 skipped** (WS bidirectional proxy test skips itself, see EP-03 Phase 8 finding #2). Ruff + mypy --strict clean on every file the session touched.

## Commit timeline (this session only)

```
6045de0  feat(ep-03): Phase 7 verified + Phase 8 security review
0b65df3  feat(ep-04): Phase 1 + Phase 2 — schema + domain layer
8b80b78  feat(ep-04): Phase 3 — repositories for sections, versions, validators
fa84b2e  feat(ep-04): Phases 4+5 + read-only Phase 8 controllers
a22ebfc  feat(ep-05): baseline — task_nodes schema + TaskNode FSM + cycle DFS
5facf09  feat(ep-06): baseline — review + validation schema and domain
3faf19c  feat(ep-07): baseline — versions extension + comments + timeline
1fab4aa  feat(ep-08): baseline — teams, notifications, inbox schema
ef68bcc  feat(ep-09..17): backend migrations + domain skeletons for remaining epics
```

## Per-epic status at session close

| Epic | Backend status | Key gaps to resume |
|------|----------------|--------------------|
| EP-00 | ✅ | — |
| EP-01 | ✅ | Cache invalidation hook wiring when EP-04 CompletenessService is fully online |
| EP-02 | ✅ | — |
| EP-03 | ✅ Phase 1-7 green; Phase 8 partially closed | Must-fix #1 (workspace_id + RLS on 3 EP-03 tables + IDOR follow-up on suggestions), Must-fix #2 (WS client→upstream direction). See `tasks/EP-03/phase_8_security_findings.md` + `decisions.log.md` 2026-04-16 |
| EP-04 | ✅ Phases 1+2+3+4+5 + GET/PATCH controllers | Phase 6 NextStep, Phase 7 spec-gen (Dundun wm_spec_gen_agent dispatch + Celery), bulk PATCH, GET /sections/:id/versions, cache invalidation hooks, VersioningService wiring (from EP-07) |
| EP-05 | 🟡 migrations + TaskNode FSM + cycle detection | ORM + repos, TaskService (split/merge/reorder + mat-path maintenance), DependencyService, tree API via WITH RECURSIVE CTE, Dundun wm_breakdown_agent, unmark-done endpoint |
| EP-06 | 🟡 migrations + ReviewRequest/Response/ValidationStatus domain | ORM + repos, ReviewService (owner-only-request, fan-out), ValidationService (mark passed/waived + re-eval), Ready-gate extension in WorkItemService, controllers |
| EP-07 | 🟡 migrations extending work_item_versions + comments + timeline_events; VersioningService with SERIALIZABLE guard | ORM + repos, CommentService (nesting check, anchor-section-belongs-to-item), outbox-backed timeline write + SSE push, diff engine (remark + diff-match-patch), diff viewer UI |
| EP-08 | 🟡 migrations + Team/TeamMembership/Notification domain | ORM + repos, TeamService + NotificationService with outbox idempotency, SSE inbox channel, inbox UNION query, hook wiring with EP-06 (review.assigned) + EP-07 (timeline) |
| EP-09 | 🟡 saved_searches migration + entity | Listing queries + dashboards service + Puppet integration (depends on EP-13 outbox drainer) |
| EP-10 | 🟡 projects + routing_rules + integration_configs migrations | Admin UI + services + audit viewer + superadmin surface |
| EP-11 | 🟡 integration_exports migration + JiraClient port | JiraClient impl, ExportService, divergence detection, controllers, Fernet credential service |
| EP-12 | ❌ | Transversal: rate limiting (already partial via slowapi), security review across all boundaries, observability polish, CSRF/SameSite tightening |
| EP-13 | 🟡 puppet_sync_outbox migration + PuppetClient port (pre-existing) | PuppetClient HTTP impl + Celery drainer + health monitor + degraded-mode UI |
| EP-14 | 🟡 hierarchy types noted | WorkItemType enum extension (milestone, story), parent-child compat rules, tree view API, completeness roll-up |
| EP-15 | 🟡 tags + work_item_tags migrations | TagService (create/rename/merge/archive), controllers, Puppet tag sync |
| EP-16 | 🟡 attachments migration + single-anchor CHECK | MinIO adapter, upload + authenticated streaming endpoint, PDF thumbnail Celery job, inline-image paste flow |
| EP-17 | 🟡 section_locks migration | LockService (acquire/heartbeat/release/force-unlock), presence SSE, inline UI indicators |
| EP-18 | ❌ | MCP server proposal fully documented in tasks/EP-18; no code yet |
| EP-19 | ✅ Phase A+B+C-for-EP-00 landed in prior session (frontend) | Retrofits of EP-01..EP-18 to the design system catalog |

## What to pick up first on resume

1. **EP-03 Phase 8 Must Fix #1** (workspace_id + RLS on `conversation_threads`, `assistant_suggestions`, `gap_findings`). This is mechanical work: new migration 0031, mapper/repo updates, `WorkspaceRepositoryImpl.get` lookup on callback to set workspace_id, two-tenant integration tests. Estimated 2-3 h.
2. **EP-03 Phase 8 Must Fix #2** (`DundunClient.chat_ws` refactor to a duplex context manager so the FE→Dundun frame path actually sends). Requires a stub WS server for E2E testing.
3. **EP-04 deferred** (NextStep + spec-gen + validators CRUD). Unblocks EP-06 Ready gate.
4. **EP-07 VersioningService wire-up**: `SectionService.update_section` should call it, and `WorkItemService.transition_state` should emit a `state_transition` version.
5. **EP-08 services + outbox worker** to flow review.assigned / mention / inbox events end-to-end.

## Untouched surface (big)

- Frontend beyond EP-19 Phase C (EP-00 surface). The 30+ untracked files in
  `frontend/` from the earlier session are EP-00 auth scaffolding that was
  never committed — picking them up still makes sense as the first frontend
  block.
- All integration tests for the new baseline layers (EP-05..EP-17). The
  domain layer has unit coverage; the DB side has not been exercised end-to-end.

## Resource / infra notes

- `tests/conftest.py` now forces `broker_url="memory://"` and
  `result_backend="cache+memory://"` on `CelerySettings` so the eager Celery
  path doesn't reach for the dev Postgres at 127.0.0.1:17000.
- `get_thread_repo_for_ws` is an `async def` generator (yields the repo) —
  previously it opened + closed the session before the repo was used.
  Anywhere else this pattern appears, audit that the session stays alive for
  the duration of the returned collaborator.
- Alembic revision IDs must stay ≤32 chars (`alembic_version.version_num` is
  VARCHAR(32)). Bit by this once, fixed in 0024.

## Reminder files still load-bearing

`/home/david/.claude/projects/.../memory/`:
- `feedback_execution_style.md` — user wants breadth over depth this pass,
  "asume lo que necesites, revisaré al final".
- `feedback_task_tracking.md` — update `tasks/<EP>/tasks-*.md` after every
  step; resumes happen from those files.
- `project_settings_lru_cache_trap.md` — still relevant anywhere you add a
  module-level `from app.config.settings import get_settings`.
- `reference_dundun_api.md` — authoritative on Dundun v0.1.1 surface.
