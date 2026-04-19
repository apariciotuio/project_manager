# EP-05 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Backend shipped 2026-04-17 (`tasks-backend.md` line 47 "**Status: COMPLETED**") and frontend shipped under `frontend/components/work-item/task-tree*` + `hooks/work-item/use-task-{tree,mutations}.ts` + `lib/api/{hierarchy,tasks}.ts`. Cross-EP cache-invalidation landed: `CompletenessService` consumes `ITaskNodeRepository.count_by_work_item()`; `TaskService` invalidates `completeness:{work_item_id}` on create/delete/split/merge.

## Scope-excluded endpoints (intentional per plan)

- **`TaskService.update_section_links(task_id, section_ids)`** — task ↔ section link mutation. Not required by the current spec-gen → task generation flow; tasks are created with their `section_ids` at generation time. Adds bulk-relink UX later (`tasks-backend.md` Group 5.13–5.14, line 382).
- **Service controller wiring for update_section_links** (`tasks-backend.md` Group 6.9–6.10).
- **`GET /api/v1/work-items/{id}/sections/{section_id}/tasks`** — per-section task listing. Current read model returns the full task tree with `section_ids` on each node; callers filter client-side. Add when a section-scoped view lands in the UI (`tasks-backend.md` Group 6.11–6.12, lines 454 / 493–494).

Both were explicitly carved in the original plan ("not required by current scope; deferred") and remain deferred.

## Why this is safe

1. Frontend does not currently consume either endpoint.
2. Existing `GET /work-items/{id}/tree` returns enough shape for any section filter to be computed client-side.
3. Reopening requires only a thin service method + controller + 3–4 tests (~2–3h total).

---

MVP scope (migrations, domain models, Task + Dependency repos + services, split/merge mutations, cycle detection, tree assembly, breadcrumb, workspace_id guards, task-tree UI + hooks + API client, cache invalidation) shipped and in production.

Re-open when a UI surface demands per-section task listing or bulk section-relink.
