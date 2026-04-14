# DB Review — Round 2 Fixes Applied

**Date**: 2026-04-13
**Scope**: Findings from `tasks/reviews/db_review.md` not addressed in round 1.

---

## Findings Addressed

| ID | Area | File(s) | Change |
|----|------|---------|--------|
| SD-3 | Audit table merge | `tasks/EP-00/design.md`, `tasks/EP-10/design.md` | Replaced `audit_logs` with unified `audit_events` table (category='auth'|'admin'|'domain'). Immutability RULEs moved to EP-00 (single source). EP-10 consumes, does not CREATE TABLE. |
| SD-8 | sessions vs refresh_tokens | `tasks/EP-12/design.md` | Canonicalized to `sessions` (EP-00). Fixed dangling `refresh_tokens` reference in EP-12 workspace-scoping exceptions list. |
| DI-5 | `integration_exports.version_id` FK | `tasks/EP-11/design.md` | Added `REFERENCES work_item_versions(id) ON DELETE RESTRICT`. |
| DI-6 | CASCADE review | `tasks/EP-07/design.md`, `tasks/EP-08/design.md` | `timeline_events.work_item_id` changed from CASCADE to RESTRICT (timeline is audit-like). Added denormalized `workspace_id` with `ON DELETE CASCADE`. `team_memberships.team_id` / `user_id` now `ON DELETE CASCADE`. |
| DI-7 | notifications FKs | `tasks/EP-08/design.md` | `notifications.workspace_id` and `recipient_id` now `ON DELETE CASCADE`. |
| MS-2 | GIN index `CONCURRENTLY` (search_vector) | `tasks/EP-09/design.md` | Changed `CREATE INDEX` to `CREATE INDEX CONCURRENTLY` with migration-transaction note. |
| MS-3 | GIN index `CONCURRENTLY` (capabilities) | `tasks/EP-10/design.md` | Same treatment on `idx_workspace_memberships_capabilities`. |
| IDX-1 | work_items composite for workspace-scoped listing | `tasks/EP-01/design.md` | Added `idx_work_items_ws_state_updated(workspace_id, state, updated_at DESC) WHERE deleted_at IS NULL`. |
| IDX-2 | review_requests reviewer + pending | `tasks/EP-06/design.md` | Added `idx_review_requests_reviewer_pending` and `idx_review_requests_team_pending` (partial, status='pending'). |
| IDX-3 | notifications unread count | `tasks/EP-08/design.md` | Added `idx_notifications_unread_count(recipient_id, workspace_id) WHERE state='unread'`. |
| IDX-4 | work_item_versions version listing | `tasks/EP-07/design.md` | Added `idx_wiv_work_item_version(work_item_id, version_number DESC) WHERE archived=false`. |
| IDX-5 | timeline cursor pagination | `tasks/EP-07/design.md` | Added `idx_timeline_cursor(work_item_id, occurred_at DESC, id DESC)` and `idx_timeline_workspace_occurred`. |
| IDX-6 | work_item_sections completeness | `tasks/EP-04/design.md` | Added `idx_wis_completeness(work_item_id, is_required, section_type)`. |
| IDX-7 | validation_statuses ready gate | `tasks/EP-06/design.md` | Added `idx_validation_statuses_gate(work_item_id, status) WHERE status NOT IN ('passed','obsolete')`. |
| IDX-8 | tsvector trigger | `tasks/EP-09/design.md` | Added `work_items_search_update()` trigger function + `trg_work_items_search` BEFORE INSERT/UPDATE trigger. |
| IDX-9 | validation_rules partial UNIQUE | `tasks/EP-10/design.md` | Already present as `uq_validation_rules_workspace_scope` — no change needed. Confirmed. |
| IDX-10 | Over-indexing on users/workspaces/sessions | `tasks/EP-00/design.md` | Removed redundant explicit indexes: `idx_users_google_sub`, `idx_users_email`, `idx_workspaces_slug`, `idx_sessions_token_hash`. UNIQUE constraints already create these. |

---

## Not Addressed (out of this round's scope)

Findings that require code/migration work outside of design.md edits, or that were explicitly marked as addressed in round 1, were skipped. Confirm with round 1 report:
- SD-1, SD-2, SD-4, SD-5, SD-6, SD-7, SD-9, SD-10 — schema design issues (round 1 territory)
- DI-1, DI-2, DI-3, DI-4 — data integrity (round 1)
- MS-1, MS-4, MS-5 — migration safety (round 1)
- Q1-Q10 — query shape issues (services/application layer, not schema)
- GP-1..GP-5, CP-1 — growth/partitioning/pool sizing (operational, not schema)

---

## Files Touched

- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-00/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-01/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-04/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-06/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-07/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-08/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-09/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-10/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-11/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-12/design.md`

---

## Notes for Migration Authors

1. **CONCURRENTLY requires non-transactional migration** — Alembic default is `transactional_ddl=True`. Split the GIN index creations (MS-2, MS-3) into their own revision files with `transactional_ddl = False` at the top, or execute via `op.get_bind().execution_options(isolation_level="AUTOCOMMIT")`.

2. **`audit_events` category backfill** — if any environment already has rows in the old `audit_logs`, the migration must copy them into `audit_events` with `category='auth'`, mapping `details` -> `context`, `event_type` -> `action`. Drop `audit_logs` only after copy succeeds.

3. **Timeline workspace_id backfill** — existing `timeline_events` rows must backfill `workspace_id` from `work_items` in a single UPDATE before the NOT NULL constraint takes effect. Add as a data migration step before the ALTER.

4. **work_item_versions search trigger + backfill** — after creating the trigger (IDX-8), existing rows still have NULL `search_vector`. Run MS-5's batched backfill or a one-shot `UPDATE work_items SET title = title` to fire the trigger (cheap at MVP scale; batched at 10x).
