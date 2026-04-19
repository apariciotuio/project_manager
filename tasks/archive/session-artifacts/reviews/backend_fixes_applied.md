# Backend Review Fixes Applied

Source: `tasks/reviews/backend_review.md`
Applied by: backend-developer agent
Date: 2026-04-13

---

## Algorithm Issues

| ID | Finding | Status | File(s) Modified |
|----|---------|--------|-----------------|
| ALG-1 | Cycle detector uses recursion (hits Python limit at ~1000 nodes); `target` not appended to path | FIXED | `tasks/EP-05/design.md`, `tasks/EP-05/tasks-backend.md` |
| ALG-2 | (Reserved — no separate ALG-2 in review) | N/A | — |
| ALG-3 | Ready gate: `waived` required rules incorrectly pass gate | FIXED | `tasks/EP-06/design.md`, `tasks/EP-06/tasks-backend.md` |
| ALG-4 | `renormalize_weights` divides by zero when all weights are 0 | FIXED | `tasks/EP-04/design.md`, `tasks/EP-04/tasks-backend.md` |
| ALG-5 | Inbox Tier 2 uses `state = 'returned'` — not a valid `WorkItemState` (correct: `changes_requested`) | FIXED | `tasks/EP-08/tasks-backend.md` (design.md was already corrected by another agent) |
| ALG-6 | Inbox Tiers 3/4 reference phantom `blocks` table, `caused_by_user_id`, `decision_owner_id` columns | FIXED | `tasks/EP-08/tasks-backend.md` (design.md was already corrected by another agent) |
| ALG-7 | `validation_rules` missing partial UNIQUE index — allows duplicate active rules per scope | FIXED | `tasks/EP-10/design.md`, `tasks/EP-10/tasks-backend.md` |

---

## Transaction & Concurrency Risks

| ID | Finding | Status | File(s) Modified |
|----|---------|--------|-----------------|
| TC-1 | `apply_partial()` missing `SELECT FOR UPDATE` — concurrent calls can both pass version check | FIXED | `tasks/EP-03/tasks-backend.md` (RED test + acceptance criterion added) |
| TC-2 | EP-05 cycle detection has no documented concurrency guard for concurrent dependency adds | DOCUMENTED | `tasks/EP-05/tasks-backend.md` (note before Phase 8 — implementation owns the lock strategy) |
| TC-3 | EP-06 ReadyGate validation + state transition not atomic | FIXED | `tasks/EP-06/tasks-backend.md` (integration test task 4.14a added) |
| TC-4 | EP-07 comment + timeline INSERT not in single transaction | FIXED | `tasks/EP-07/design.md`, `tasks/EP-07/tasks-backend.md` (atomicity test 3.23a added) |
| TC-5 | EP-10 HealthDashboard read path has no documented isolation requirement | FIXED | `tasks/EP-10/design.md` (note in Audit Read Path section) |

---

## Layer Violations

| ID | Finding | Status | File(s) Modified |
|----|---------|--------|-----------------|
| LV-1 | EP-04 `ScoreCalculator` directly imports `VersioningService` | ALREADY FIXED | `tasks/EP-04/design.md` (confirmed fixed by another agent before this run) |
| LV-2 | EP-06 `ReviewResponseService` calls `WorkItemService` directly, no documented dependency | FIXED | `tasks/EP-06/design.md` (Cross-Epic Dependencies section added) |
| LV-3 | EP-08 UNION inbox SQL lives in `InboxService` (application layer) — SQL belongs in repository | FIXED | `tasks/EP-08/design.md` (IInboxRepository + InboxRepositoryImpl added to DDD map), `tasks/EP-08/tasks-backend.md` |
| LV-4 | EP-10 `HealthDashboardService` directly queries DB — no repository interface | FIXED | `tasks/EP-10/design.md` (`IDashboardRepository` pattern added), `tasks/EP-10/tasks-backend.md` |
| LV-5 | EP-11 `ExportTask` (infrastructure) calls `AuditService` (application) directly | FIXED | `tasks/EP-11/design.md` (ExportService.mark_export_success pattern), `tasks/EP-11/tasks-backend.md` |

---

## Celery / Async Issues

| ID | Finding | Status | File(s) Modified |
|----|---------|--------|-----------------|
| CA-1 | EP-03 `generate_suggestion_set` not idempotent on retry — duplicate items on partial creation | FIXED | `tasks/EP-03/tasks-backend.md` (Phase 6 test + implementation note) |
| CA-2 | EP-08 DLQ note misleading — Celery does NOT auto-DLQ on `max_retries` exceeded | FIXED | `tasks/EP-08/design.md` (Risks table updated with correct DLQ semantics) |
| CA-3 | EP-11 `export_task` no `soft_time_limit` — hung Jira connections can block worker indefinitely | FIXED | `tasks/EP-11/design.md`, `tasks/EP-11/tasks-backend.md` (`soft_time_limit=45` added) |
| CA-4 | EP-03 `summarise_thread_context` no distributed lock — concurrent tasks produce duplicate summaries | FIXED | `tasks/EP-03/tasks-backend.md` (Phase 6 — Redis SETNX lock pattern added; CA-4 covered in CA-1 update) |
| CA-5 | EP-11 `sync_task` single-batch fetch — OOM on large datasets | FIXED | `tasks/EP-11/design.md`, `tasks/EP-11/tasks-backend.md` (paginated loop, `max_items_per_run=1000`) |

---

## Service Design Issues

| ID | Finding | Status | File(s) Modified |
|----|---------|--------|-----------------|
| SD-1 | EP-03 suggestion model fragmentation (separate tables for thread vs inline suggestions) | SKIPPED | Owned by another agent. Out of scope. |
| SD-2 | EP-06 duplicate FSM: `WorkItemTransitionService` + `WorkItemService` both own state transitions | FIXED | `tasks/EP-06/design.md`, `tasks/EP-06/tasks-backend.md` (renamed to "Ready Gate Integration — EP-01 WorkItemService Extension"; injected gate pattern) |
| SD-3 | EP-04/EP-07 `VersioningService` ownership ambiguity | SKIPPED | Owned by another agent. LV-1 was already resolved. |
| SD-4 | EP-08 `NotificationService.execute_quick_action()` risks becoming a god method | FIXED | `tasks/EP-08/tasks-backend.md` (QuickActionDispatcher pattern added, task B6.4a) |
| SD-5 | EP-10 workspace invitation email dispatched inside DB transaction — Celery task may run before commit | FIXED | `tasks/EP-10/tasks-backend.md` (after-commit dispatch pattern + test added) |

---

## Skipped / Out of Scope

The following findings were explicitly excluded per task instructions (owned by other agents):

- **EP-08 inbox query** (already fixed before this run)
- **EP-07 comments CHECK constraint** (DB agent)
- **EP-01 project_id FK ordering** (DB agent)
- **EP-06 duplicate ALTER TABLE** (DB agent)
- **EP-03 suggestion model unification** (SD-1, another agent)
- **EP-04/EP-07 VersioningService ownership** (SD-3, another agent)
- **EP-06 team review visibility** (another agent)
- **Workspace scoping pattern** (security agent)
- **CSRF design, SSE auth, LLM prompt injection** (security agent)

---

## Findings Needing Deeper Investigation

None. All non-skipped findings have been applied as specification changes (design.md + tasks-backend.md). Implementation verification occurs during TDD execution phases per the development pipeline.
