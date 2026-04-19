# EP-04 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Structured Specification & Quality Engine shipped: 8 element-type catalog + 8 dimension checkers + completeness scorer + gap service + NextStep decision tree (9 rules) + spec-gen callback handler + all read endpoints (GET specification, PATCH section, GET completeness, GET gaps, GET next-step). Canonical state in `tasks-backend.md` Phases 4+5+6+7+8 LANDED and `tasks-frontend.md` **Status: COMPLETED 2026-04-17**.

## Dispatch endpoint (needs redesign)

- **POST `/api/v1/work-items/{id}/specification/generate`** (`tasks-backend.md` line 334) — the callback path and Dundun `invoke_agent` are both shipped; only the trigger controller is missing. The acceptance criteria at line 361 references a **Redis lock for concurrency** and design.md line 367 says the controller **enqueues a Celery task** — both Redis and Celery were ripped out (see EP-12 design note). A correct implementation needs:
  - A PG-native lock or a `spec_gen_requests` pending-row pattern (replaces Redis lock)
  - Direct async call to `DundunClient.invoke_agent` (replaces Celery)
  - Fresh acceptance tests matching the current stack
  - Re-worked spec in design.md to reflect the PG-native + in-memory stack
  Estimated: 4–6h including design + tests. No consumer in the current UI, so the MVP path is manual trigger via admin tool or direct client call.

## Incremental endpoints (low priority)

- **PATCH `/api/v1/work-items/{id}/sections` (bulk)** (`tasks-backend.md` line 334) — single-section PATCH is sufficient for current UI; add when bulk-edit UX ships.
- **GET `/api/v1/work-items/{id}/sections/{section_id}/versions`** (`tasks-backend.md` line 334) — version history is a nice-to-have; single-section view suffices for MVP.

## Design-decision deferrals

- **`ValidatorSuggestionEngine`** (`tasks-backend.md` lines 277–278) — complex role-config mapping; wait for validator assign/revoke CRUD to ship.
- **`gap_messages.py` static dict consolidation** (`tasks-backend.md` line 255) — messages currently inline in dimension_checkers; consolidate when a second epic reuses them.
- **`workspace_id` param refactor** (`tasks-backend.md` line 119) — defense-in-depth follow-up; RLS is already enforced via migrations 0033 + 0112.
- **`check_next_step_clarity()`** (`tasks-backend.md` line 189) — only fires when next_step is undefined, a rare case in practice; skip.
- **`WorkItemService` cache-invalidation hooks** (`tasks-backend.md` lines 262–264) — completeness recomputes on section edit already; full hook coverage is per-epic work like the EP-12 inbox invalidation carveout.

---

MVP scope (8-type catalog, dimension checkers, completeness + cache, gap service, NextStep tree, spec-gen callback, all read/write section endpoints) shipped and in production.

Re-open the dispatch endpoint when a UI consumer lands, or when we need programmatic spec generation for import flows.
