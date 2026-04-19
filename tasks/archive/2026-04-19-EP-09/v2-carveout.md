# EP-09 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Listings, Dashboards, Search & Workspace shipped:
- Backend: cursor-paginated work-item list with filter + sort, Puppet-backed search, `kanban_controller`, `person_dashboard_service`, `team_dashboard_service`, `saved_search_controller` + service
- Frontend: list page + filters + search + workspace dashboard (51/108 FE items shipped per the old status line, rest is stale sub-task state)
- Cross-epic: DashboardService cache-aside TTL bumped to 120s (EP-12 follow-up commit b0bca06)

## Missing endpoint (no UI consumer today)

- **`GET /api/v1/work-items/{id}/summary`** (per execution plan line 93) — no controller today; originally intended for `QuickViewPanel` hover preview. `QuickViewPanel` itself is deferred. When the panel ships, add a small projection controller + 3 tests (~1h).

## Test-harness gaps (nice-to-have)

- **N+1 audit fixtures** — `QueryCounterMiddleware` emits WARNING when per-request query count exceeds budget in dev/staging (EP-12 line 244). Dedicated assertion-style tests that pin specific counts are brittle; defer until we hit a regression.

## Naming drift

- **`saved-searches` vs `saved-filters` reconciliation** — DB tables + service use `saved_search`; spec doc uses both in different places. Choose one and rename; cosmetic but visible in URL.

## Search polish (Puppet dependency)

- **SQL fallback search** — design originally contemplated a degraded path if Puppet is down. Puppet has `use_fake=True` in tests and `DundunClient.search` error path returns an empty `SearchResult` today; users see an empty list, not a 5xx. Proper fallback needs a keyset query on `work_items.title` + ILIKE — low priority.
- **Search cursor pagination** — already carved in EP-12 (`search:{workspace_id}:{hash(query)}` cache + keyset pagination v2 for Puppet).

## Pipeline / Kanban polish

- **Pipeline board endpoints** (beyond `kanban_controller.py`) — distinct-from-dashboard visualization. Defer until a UI surface requires per-state swim-lane columns outside the current kanban view.

---

MVP scope (paginated listings, filters, sort, Puppet search, workspace + person + team dashboards, saved searches, kanban) shipped and in production.
