# EP-14 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Groups 1–2 shipped:
- `parent_work_item_id` column + FK + index + RLS
- Hierarchy read via existing `GET /work-items?parent_work_item_id=…` filter
- Frontend shipped (`tasks-frontend.md` line 186 + 210 "**Status: COMPLETED**"; task reparenting in `frontend/hooks/work-item/use-task-mutations.ts` uses `PATCH /api/v1/tasks/{taskId}/parent` — a separate task-tree endpoint already shipped under EP-05).

## BE Groups 3–10 (95 items)

Originally scoped for full work-item hierarchy semantics (Milestone → Epic → Story → Task). Carved because:

- **`PATCH /api/v1/work-items/{id}/position`** — no UI consumer today. The task tree uses the EP-05 task-reparenting endpoint. Work-item hierarchy (above Task) is read-only in the MVP UI.
- **`materialized_path` column + migration** — premature optimization. Current hierarchy depth is 2–4 levels; CTE traversal is fast enough for MVP workspace sizes. Revisit at 10k+ work-items per workspace.
- **`MaterializedPathService` + `HierarchyValidator`** — ship with the migration above.
- **Rollup completion computation** — `CompletenessService` already handles task-level rollup (EP-05 landed the hook); work-item rollup above Task is deferred with `materialized_path`.
- **Cycle detection, subtree counts, position arithmetic** — support the PATCH endpoint; deferred together.
- **Groups 8–10 (integration tests, docs, perf)** — follow the carved endpoints.

## Why this is safe

1. Today's UI does not reparent work-items above Task — only tasks reparent (EP-05).
2. Reading hierarchy works via simple `parent_work_item_id` filter (no CTE needed at current volumes).
3. The full feature is a 2–3 day build; scope it as its own epic when a product need lands.

---

MVP scope (nullable parent FK + index + RLS + existing list filter + task-tree reparenting from EP-05) shipped and in production.
