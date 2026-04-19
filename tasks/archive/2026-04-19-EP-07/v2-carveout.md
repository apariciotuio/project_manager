# EP-07 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Comments, Versions, Diff & Traceability shipped:
- Backend: `DiffService` (`backend/app/application/services/diff_service.py`, pure `difflib` 2-pass structural+content, `SectionChangeType` enum — no external library needed); version + timeline services; version + timeline controllers with `workspace_id` scoping
- Frontend: version history tab, timeline tab, comment thread with edit/delete + authorship (AI vs user)

**Diff-engine decision (per Execution Plan line 80):** Chose **pure stdlib `difflib`** — zero deps, battle-tested, covers MVP needs. `diff-match-patch` evaluated, rejected as over-spec for our payload sizes.

## Cross-epic integration (per-epic adoption pattern, same as EP-12 capability)

- **3.7 — EP-01 state-transition integration** (`tasks-backend.md` line 315): `timeline_subscriber` already handles `state_changed` events via EventBus fire-and-forget. Formal hook wiring is per-EP work.
- **3.8 — EP-06 review-response integration** (`tasks-backend.md` line 316): EP-06 scope.
- **3.9 — EP-05 breakdown save integration** (`tasks-backend.md` line 317): EP-05 scope.

## Redis/Celery redesign (same pattern as EP-04 spec-gen dispatch)

- **3.25–3.28 — `AnchorRecompute` Celery task + wiring** (`tasks-backend.md` lines 343–346): Celery was ripped out; anchor-recompute needs a PG-native replacement (e.g., `LISTEN/NOTIFY` via `PgNotificationBus`). Re-design required.
- **6.4 — Archival batch job** (`tasks-backend.md` line 451): Celery cron replaced by either a DB trigger or manual sweep; revisit with ops.

## Pagination + event emission gaps

- **3.22 — Comment list cursor pagination** (`tasks-backend.md` line 336): current API returns the full list (bounded by work-item comments, not a scalability issue at MVP volume). Add when volume justifies.
- **3.30 — `item_created` event emission** (`tasks-backend.md` line 351): timeline renders from the DB state, not the event stream today.

## Observability + perf gates (matches EP-12 CI-gate carveout)

- **6.1 — Structured logging on version/diff/anchor/timeline paths** (`tasks-backend.md` line 448): covered by `CorrelationIDMiddleware` + `RequestLoggingMiddleware` at the HTTP level.
- **6.2 — EXPLAIN ANALYZE on timeline index** (`tasks-backend.md` line 449): index exists (`idx_timeline_work_item_occurred`); p95 well under budget in staging.
- **6.3 — p95 < 2s perf test** (`tasks-backend.md` line 450): v2 CI gate (matches Lighthouse / size-limit pattern).

## Frontend — anchored comment polish (already tagged v2)

- **4.7–4.10 — Anchored comment popover + section editor wiring** (`tasks-frontend.md` lines 343–346): explicitly marked `[DEFERRED v2]` in the original plan; depends on `SpecificationSectionsEditor` (EP-04 follow-up).
- **3.10 — Dedicated `/history` page** (`tasks-frontend.md` line 246): tab sufficient for MVP.
- **4.3a — Paste-image upload via EP-16** (`tasks-frontend.md` line 319): EP-16 is carved to v2; current UI shows disabled placeholder.
- **7.5 — Mobile anchored-comment UX** (`tasks-frontend.md` line 440): depends on §4 anchored-comment v2.
- **4.12 — GET /sections/{id}/comments integration test** (`tasks-backend.md` line 426): section-anchored query ships with §4 v2.

---

MVP scope (comments CRUD + edit/delete + AI authorship, version snapshots, diff computation, timeline filtering, workspace scoping on version/timeline) shipped and in production.
