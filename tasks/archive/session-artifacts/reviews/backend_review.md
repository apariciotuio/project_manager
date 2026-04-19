# Backend Review

**Date**: 2026-04-13
**Scope**: EP-01, EP-03, EP-04, EP-05, EP-06, EP-07, EP-08, EP-10, EP-11
**Reviewer**: backend-developer agent

---

## Algorithm Issues (correctness bugs)

### ALG-1. EP-05 Cycle Detector Has Incorrect DFS Termination and Recursion

`design.md` section 3 shows a recursive `dfs(node)` function in the cycle detector. The tasks file (phase 3.7) correctly mandates iterative DFS, but the design sample code is recursive and has a logic bug: the `target` and `start` variables are swapped in the DFS setup.

The design sets `target = new_edge[1]` (the predecessor) and `start = new_edge[0]` (the dependent) — then calls `dfs(start)` which traverses successor edges looking for `target`. This is correct directionally, but the termination condition `if node == target` fires before `visited.add(node)`, so the path does not include `target` in the returned cycle path. Result: the cycle path is incomplete and the API returns a path that does not form a valid cycle.

**Fix**: Add `target` to `path` before returning `True`. Also, the tasks file must mandate iterative DFS — the design code must not be used verbatim.

---

### ALG-2. EP-07 Version Number Assignment Under Concurrency

`design.md` section 1 specifies:
```sql
SELECT COALESCE(MAX(version_number), 0) + 1 FROM work_item_versions WHERE work_item_id = $1
```
inside a "serializable transaction."

This works, but only if the isolation level is `SERIALIZABLE`. The tasks file (phase 3.1) says "serializable transaction prevents duplicates" — correct. However, if the application defaults to `READ COMMITTED` (SQLAlchemy async default), developers will forget to set `SERIALIZABLE` on this specific session. Two concurrent `MAX+1` reads on the same `work_item_id` under `READ COMMITTED` return the same number, producing a UNIQUE constraint violation at commit that bubbles up as an unhandled DB error.

**Fix**: The `VersioningService.create_version()` implementation must explicitly set `isolation_level='SERIALIZABLE'` on the session. Document this in the tasks file — not just "serializable transaction" but the exact SQLAlchemy pattern:
```python
async with session.begin():
    await session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
```

---

### ALG-3. EP-06 ReadyGate Allows Waived Required Rules

`design.md` section "Ready Gate Logic":
```python
blocking = [vs for vs in required_statuses if vs.status not in ('passed', 'waived')]
```

The comment says "waived is only reachable for recommended rules; service layer prevents waiving required rules outside override flow." But the query `WHERE required = true AND ? = ANY(applies_to)` pulls all required rule statuses. If a required rule somehow reaches `waived` status (DB-level corruption, migration error, direct SQL edit), the gate passes silently. The domain invariant exists only in comments, not in code.

**Fix**: `ReadyGateService.check()` must assert `vs.status != 'waived'` for required rules. Add an explicit branch: if a required rule has `status = 'waived'`, treat it as `blocking` and log a warning. Belt and suspenders — the domain already blocks this, but the gate should not trust it.

---

### ALG-4. EP-04 ScoreCalculator Renormalization Edge Case

`score_calculator.py` renormalizes weights of applicable dimensions to sum to 1.0. If ALL dimensions are inapplicable for a given `WorkItemType` (edge case: misconfigured SECTION_CATALOG), `total = 0.0` and division by zero occurs.

The tasks file has no test for this case. The "ScoreCalculator.compute()" acceptance criteria test only the happy path.

**Fix**: Add guard: if `total == 0.0`, return `CompletenessResult(score=0, level='low', dimensions=[])`. Add a RED test: "WHEN all dimensions are inapplicable THEN score=0 and no ZeroDivisionError."

---

### ALG-5. EP-08 Inbox Tier 2 References `state = 'returned'`

`design.md` inbox UNION query Tier 2:
```sql
WHERE owner_id = :user_id AND state = 'returned'
```

`returned` is not a valid `WorkItemState` in EP-01. Valid states are: `draft`, `in_clarification`, `in_review`, `changes_requested`, `partially_validated`, `ready`, `exported`. The architect_review (C1) flagged this but the design.md query is still wrong in this implementation detail.

**Fix**: Tier 2 should be `state = 'changes_requested'` — items returned to owner for changes. This is confirmed by the EP-06 flow where reviewer decision `changes_requested` transitions the work item to that state.

---

### ALG-6. EP-08 Inbox Tiers 3 and 4 Reference Non-Existent Tables/Columns

The architect_review flagged these (C1). Confirming from code review perspective:

- Tier 3: `blocks` table does not exist in any epic schema. `caused_by_user_id` is a phantom column.
- Tier 4: `decision_owner_id` column does not exist on `work_items`. `awaiting_decision` is not a valid state.

Additionally, the tasks file (Group C, C1.1) describes these tiers in service test acceptance criteria — meaning tests will be written for behavior that cannot work. The tests will never pass on a real DB.

**Fix**: Remove Tiers 3 and 4 from InboxService. The inbox is Tier 1 (pending reviews) + Tier 2 (changes_requested items). Document the removal in EP-08 design.md. Tiers 3/4 require a `blocks` domain concept that is not designed. ⚠️ originally MVP-scoped — see decisions_pending.md

---

### ALG-7. EP-10 Rule Precedence: Duplicate `validation_type` in workspace rules Not Handled

`RulePrecedenceService.resolve_validation_rules()` builds `ws_by_type` as a dict keyed on `validation_type`. If two active workspace rules exist for the same `(workspace_id, validation_type, work_item_type)` combination (possible if the UNIQUE constraint only covers `(workspace_id, project_id, element_type, validation_type)` and `project_id IS NULL` is not unique-enforced), the later rule silently overwrites the earlier one.

**Fix**: Add a DB UNIQUE constraint on `validation_rules(workspace_id, work_item_type, validation_type)` WHERE `project_id IS NULL`. The tasks file migration does not specify this partial unique index.

---

## Layer Violations (DDD breaches)

### LV-1. EP-04 `SpecificationService.save_section()` Dual-Writes to `work_item_versions`

`design.md` section "Versioning Integration" states: EP-04's `SectionService.save()` appends a row to `work_item_versions` in the same DB transaction. This is the architect_review C3 finding: two services writing to the same table.

From a DDD perspective, `work_item_versions` is owned by EP-07's `VersioningService`. EP-04's service directly inserting into this table without going through `VersioningService` is a layer violation — two application services writing to the same table without a shared interface.

**Fix (confirming architect_review recommendation)**: EP-04's `SectionService.save()` must call `VersioningService.create_version(work_item_id, trigger=CONTENT_EDIT, actor=...)` instead of directly inserting. `VersioningService` is the single writer. This requires `VersioningService` to be injected into `SectionService` — valid DI.

---

### LV-2. EP-06 `ReviewResponseService` Calls FSM Transition Directly

`tasks-backend.md` phase 4.7: "Test submit: rejected → closes request, calls FSM transition to `changes_requested`."

`ReviewResponseService` is an EP-06 application service calling `WorkItemService.transition_state()` from EP-01. This cross-epic service call is fine architecturally, but the tasks file does not show it going through the domain event bus. The sequence diagram shows `ReviewService → update FSM if needed → (Changes Requested)` as a direct call, not as a domain event.

Direct service-to-service calls across epics create tight coupling. If `WorkItemService.transition_state()` is refactored (e.g., to add a reason field), EP-06 is silently broken.

**Fix**: `ReviewResponseService` should emit a `review.responded` domain event with `decision=changes_requested`. An event handler in EP-01 subscribes and calls `WorkItemService.transition_state()`. This preserves domain autonomy. If direct call is kept for simplicity, it must be explicitly documented as a cross-epic dependency and added to EP-06's dependency list.

---

### LV-3. EP-08 `InboxService` Contains Direct SQL UNION Logic

`tasks-backend.md` C1.4: "Implement `application/services/inbox_service.py` — UNION query with de-duplication at application layer."

A UNION SQL query in an application service is a layer violation. The application layer must not contain SQL. The query should be in a repository implementation (`InboxQueryRepository`) and the service orchestrates it.

**Fix**: Define `domain/repositories/inbox_repository.py` interface with `get_inbox(user_id, workspace_id) -> list[InboxItem]`. Implement the UNION in `infrastructure/persistence/inbox_repository_impl.py`. `InboxService` calls the repo. The de-duplication logic (application-layer concern) stays in the service.

---

### LV-4. EP-10 `DashboardService` Runs Aggregation Queries in Application Service

`design.md` section 5: `HealthDashboardService` methods contain direct SQL aggregations (GROUP BY, COUNT, CASE WHEN). These are infrastructure concerns — the application service should call repository methods.

**Fix**: Each aggregation (`get_workspace_health`, `get_org_health`, etc.) becomes a method on `DashboardRepository` in the infrastructure layer. `DashboardService` calls these methods and assembles the result. This also makes the queries testable in isolation.

---

### LV-5. EP-11 `ExportTask` Calls `AuditService.record()` Directly

The Celery task `ExportTask` calls `AuditService.record()`. Celery tasks run in the infrastructure layer (they are infrastructure adapters for async execution). The application layer's `AuditService` should not be called from infrastructure.

**Fix**: The audit record should be written by `ExportService` (application layer) as a post-success callback, not from the Celery task. The Celery task calls `ExportService.mark_export_success(export_id, jira_ref)` and the service handles both the DB update and audit in one application-layer transaction.

---

## Service Design Issues

### SD-1. EP-01 `WorkItemService` Has Dual Responsibility for Completeness

`design.md` section 3.3: "completeness_score is computed synchronously on every save" by a strategy per `WorkItemType`. The tasks file (3.3 REFACTOR) says "Extract completeness computation into `domain/services/completeness_service.py` — pure function." But EP-04 builds a full `CompletenessService` with caching and dimension checkers.

Result: two completeness computations exist at creation time. EP-01 computes it synchronously on create (domain-level, limited data). EP-04 computes it on GET (full dimensions, cache). They will diverge.

**Fix (confirming architect_review S1)**: Remove `compute_completeness()` from EP-01's `WorkItem` entity. On creation, `completeness_score = 0` (or null). EP-04's `CompletenessService` owns the score. EP-01 stores it as a denormalized cache column updated by EP-04 events.

---

### SD-2. EP-06 `WorkItemTransitionService` vs EP-01 `WorkItemService` — Overlapping FSM Ownership

EP-06 tasks-backend.md phase 4.22-4.26 implements a `WorkItemTransitionService` for the `ready` transition. EP-01 owns `WorkItemService.transition_state()`. The result is two services that both handle FSM transitions — one for generic transitions, one for the ready gate.

The ready gate check is a pre-condition for the `→ ready` transition, not a separate service concern. `WorkItemTransitionService` should not exist as a standalone service.

**Fix**: Extend EP-01's `WorkItemService.transition_state()` to accept an optional `validator` callable (or call `ReadyGateService.check()` inline when `target_state == READY`). The gate logic stays in EP-06 (`ReadyGateService`), but transition execution stays in EP-01. EP-06 exports `ReadyGateService` as a domain service that EP-01 injects. No duplicate transition service.

---

### SD-3. EP-03 `ConversationService.build_context()` Token Count Accuracy

`tasks-backend.md` phase 5: "build_context(thread_id): returns messages within 80k token budget, prepends summary message if older messages archived."

The method queries messages up to the token budget. But `conversation_messages.token_count` is populated asynchronously (after LLM response persists). If a message row exists but `token_count = 0` (race condition: user sent message, Celery hasn't processed it yet), `build_context()` undercounts tokens and may exceed the budget on the LLM call.

**Fix**: `build_context()` must use `tiktoken` to recount tokens on the actual content when `token_count = 0`, rather than trusting the stored value. Add a test: "WHEN message has `token_count = 0` THEN actual token count is computed from content."

---

### SD-4. EP-08 `NotificationService.execute_action()` Contains Business Logic

`tasks-backend.md` B6.4: "validates action type; calls downstream service; transitions notification to `actioned`."

`execute_action` dispatches to downstream services (e.g., approving a review by calling `ReviewResponseService`). This means `NotificationService` has a dependency on `ReviewResponseService`, `WorkItemService`, etc. `NotificationService` becomes a god object with tentacles into every epic.

**Fix**: Quick actions should be an enum mapped to a dedicated `QuickActionDispatcher` (application service) that handles the routing. `NotificationService` calls `dispatcher.dispatch(action_type, subject_id, actor_id)` and marks the notification. The dispatcher owns the downstream service dependencies, not `NotificationService`. This aligns with security review HIGH-6.

---

### SD-5. EP-10 `MemberService.invite()` — Invitation Email Dispatched Before Transaction Commits

`tasks-backend.md` Group 4: "Celery task: send invitation email" — no ordering constraint specified.

If the Celery task is dispatched synchronously inside the `invite()` transaction (before commit), a rollback leaves a sent email with no DB invitation record. The recipient cannot accept an invitation that doesn't exist.

**Fix**: Celery task dispatch must happen after the DB transaction commits. Use the transactional outbox pattern or, at minimum, call `apply_async()` in a `after_commit` hook. Document this ordering requirement in the tasks file.

---

## Transaction & Concurrency Risks

### TC-1. EP-03 `SuggestionService.apply_partial()` Missing Explicit Lock

`design.md` section 3.1 shows:
```sql
SELECT id, version_number FROM work_items WHERE id = ? FOR UPDATE;
```

The Python service layer uses `FOR UPDATE` lock. This is correct. However, if `apply_partial()` is called concurrently (two users accepting different suggestion sets for the same work item simultaneously), the second caller blocks on the lock and then gets a `VersionConflictError` because the first caller incremented `version_number`. This is correct behavior but it must be tested — the tasks file has no concurrency test.

**Fix**: Add a RED test: "WHEN two concurrent `apply_partial()` calls run for the same work_item THEN one succeeds and the other raises `VersionConflictError`."

---

### TC-2. EP-05 `TaskService.split()` — Sibling Reorder and New Node Creation Not Atomic

`design.md` section 4, step 3c: "Shift all sibling nodes with `order >= source.order + 1` by +1."

This UPDATE runs in the same transaction as the INSERTs for nodes A and B. If the sibling UPDATE affects a large number of rows and another concurrent transaction reads siblings between the INSERT and the UPDATE, it sees inconsistent `display_order` values. This is a phantom read issue.

Under `READ COMMITTED` (SQLAlchemy default), this race is possible. The transaction is atomic but other transactions can see intermediate states.

**Fix**: This is acceptable under current concurrency assumptions. Document that `task tree operations require READ COMMITTED isolation and callers must not cache display_order between mutations`. If edit contention becomes an issue, add a `SELECT FOR UPDATE` on the parent node before any child reorder. ⚠️ originally MVP-scoped — see decisions_pending.md

---

### TC-3. EP-06 `ReviewResponseService.submit()` — Validation Update Not Explicitly In-Transaction

`tasks-backend.md` phase 4.14 (REFACTOR): "Ensure `ValidationService.on_review_closed()` runs in same DB transaction as response INSERT."

This is the right intent, but the current design shows it as a service method call from `ReviewResponseService`. If `ValidationService` uses a separate session (common in async SQLAlchemy patterns), the two operations are in separate transactions.

**Fix**: `ReviewResponseService.submit()` must explicitly pass the active session/transaction to `ValidationService.on_review_closed()`, or both services must share the same unit of work. Add integration test: "WHEN DB error occurs between review_response INSERT and validation_status UPDATE THEN neither is committed."

---

### TC-4. EP-07 `CommentService.create_comment()` — Timeline Event in Same Transaction

`tasks-backend.md` phase 3.23: "`create_comment` appends `comment_added` to `timeline_events`; `soft_delete` appends `comment_deleted`."

If the timeline INSERT fails (e.g., `summary` exceeds 255 chars for a long comment body), the transaction rolls back and the comment is not created. This is correct. However, if the implementation inserts the timeline event in a separate try/except (fire-and-forget pattern), the comment persists without a timeline entry — silent inconsistency.

**Fix**: Timeline INSERT must be in the same transaction, not wrapped in a separate try/except. Add a test: "WHEN timeline INSERT raises THEN comment INSERT is also rolled back."

---

### TC-5. EP-10 `AuditService.record()` — Synchronous Write Can Block Caller Transaction

`design.md` section 4: "Every mutation in admin services calls `AuditService.record()`. Direct DB insert within the same transaction."

Under high audit write volume, the audit INSERT is on the critical path of every mutation. If `audit_events` table has I/O contention (large dataset, slow disk), every mutation slows proportionally.

This is by design (synchronous audit = consistent with action). The risk is acceptable at current scale. But the `audit_events` indexes (`actor`, `entity`, `action`) add write overhead on every INSERT.

**Fix**: No change needed at current scale. Document in performance notes: "At >1M audit rows, consider partitioning `audit_events` by month. The three indexes on audit_events add ~3ms per write at 100k rows — acceptable." ⚠️ originally MVP-scoped — see decisions_pending.md

---

## Celery/Async Issues

### CA-1. EP-03 LLM Tasks Missing Idempotency on `generate_suggestion_set`

`tasks-backend.md` phase 6: "All tasks idempotent (safe to retry); `max_retries=3`."

The `generate_suggestion_set` task creates `SuggestionItem` rows. If the task retries after partial item creation (network error after 2 of 5 items inserted), the retry re-runs the LLM and creates a duplicate set or duplicate items.

**Fix**: The Celery task must check on start whether `suggestion_set.status == 'pending'` and whether items already exist. If items exist, skip LLM call and proceed to status update. Add a test for this retry path.

---

### CA-2. EP-08 Fan-out Task — Dead Letter Queue Not Wired

`tasks-backend.md` B3.3: "Test: dead-letter logging on 3 consecutive failures."

The design mentions "event is logged to dead-letter queue with full payload." But no epic defines a dead-letter queue configuration. Celery's default behavior on max_retries exceeded is to raise `MaxRetriesExceededError` — the task goes to the `failed` state in the results backend but there is no persistent dead-letter queue unless configured.

**Fix**: Define DLQ configuration in the Celery config (EP-12 infrastructure concern). Add to `tech_info.md` section 5 (Celery queues): a `dead_letter` queue receiving tasks that exceeded retries. Wire `on_failure` handler in fan-out task to publish to this queue.

---

### CA-3. EP-11 `ExportTask` — `acks_late=True` Without Visibility Timeout Alignment

`design.md` section 10: `acks_late=True, reject_on_worker_lost=True`. Jira export can take up to 30s on a slow Jira instance. Redis visibility timeout (broker transport's `visibility_timeout`) defaults to 1 hour in Celery+Redis. This is fine.

However, if `max_retries=3` with backoff `60s, 120s, 240s`, the total task lifetime can be `30s + 60s + 30s + 120s + 30s + 240s ≈ 530s`. With `acks_late=True`, the message stays unacked for 530s. Celery's default `CELERYD_TASK_SOFT_TIME_LIMIT` is not set — the task can run indefinitely if Jira hangs.

**Fix**: Set `soft_time_limit=45` (seconds) on `export_task` to raise `SoftTimeLimitExceeded` if Jira hangs. The task catches this, marks the export `failed`, and does not retry (prevent infinite loops on hung connections). Document in EP-11 tasks file.

---

### CA-4. EP-03 `summarise_and_archive` Task — No Guard Against Concurrent Execution

Multiple SSE connections from the same user can trigger `send_message()` which checks the token budget and dispatches `summarise_and_archive` if over budget. If two messages arrive in quick succession, two summarisation tasks fire for the same thread. Both read the same messages as "oldest," both archive them, and both insert a summary — resulting in duplicate summary messages.

**Fix**: Use a Redis distributed lock (`SETNX summarise:{thread_id}`) with TTL 120s before the Celery task proceeds. If lock acquisition fails, the task exits early. Add a test: "WHEN two concurrent summarise tasks run for the same thread THEN only one summary is created."

---

### CA-5. EP-11 `sync_task` — Unbounded `get_syncable()` Query

`tasks-backend.md` Group 5: `SyncService.sync_all_active_exports()` calls `get_syncable(batch_size=100)`. The `sync_task` is a Celery Beat periodic task every 15 minutes.

If the `integration_exports` table has 10k syncable records (large workspace), the task runs 100 records per invocation. At 15-minute intervals, clearing 10k records takes 25 hours. The backlog grows unbounded.

**Fix**: Change from a single batch to a paginated loop within the task: process batches of 100 in a loop until no records remain or a configurable `max_items_per_run` (default: 1000) is reached. This keeps the task bounded but clears backlog faster.

---

## Recommendations by Epic

### EP-01
- Remove `compute_completeness()` from `WorkItem` entity — EP-04 owns this (ALG resolution of S1).
- `WorkItemService.transition_state()` should accept an optional `ready_gate_checker` callable injection for the `→ ready` path. Keeps FSM clean, avoids WorkItemTransitionService duplication (SD-2).
- Add `workspace_id` to all repository `get()` and `list()` calls per security review CRIT-2.

### EP-03
- Token count race condition in `build_context()` must be fixed before implementing (SD-3).
- `generate_suggestion_set` task needs idempotency guard on retry (CA-1).
- `summarise_and_archive` needs distributed lock (CA-4).
- Suggestion schema: resolve the `SuggestionSet/SuggestionItem` vs flat `assistant_suggestions` conflict (architect_review C4) before implementing — the tasks file references both.

### EP-04
- Remove direct `work_item_versions` INSERT from `SectionService.save()` — call `VersioningService.create_version()` (LV-1).
- Fix `ScoreCalculator` zero-division edge case (ALG-4).
- `SpecificationService.generate()` is synchronous for an LLM call — the design notes this as acceptable but the tasks file has a Redis lock for concurrent calls. The lock TTL is unspecified. Add `TTL=120s` explicitly or the lock can be orphaned on LLM timeout.

### EP-05
- Fix cycle detector path return (ALG-1). Add integration test for the API `cycle_path` response field.
- `TaskService.split()` / `merge()` need tests for concurrent execution (TC-2 documentation).
- The LLM breakdown generation is currently synchronous. Add the 5-second P95 gate explicitly to the tasks file with a plan to promote to Celery if exceeded. ⚠️ originally MVP-scoped — see decisions_pending.md

### EP-06
- `ReadyGateService.check()` must block on `required + waived` combination (ALG-3).
- `ValidationService.on_review_closed()` must share the session/transaction with `ReviewResponseService.submit()` (TC-3).
- Eliminate `WorkItemTransitionService` — merge into EP-01 service with injected gate (SD-2).
- `review_requests` migration in design.md still contains the duplicate `ALTER TABLE work_items` — remove it (architect_review C2 — still present in tasks-backend.md phase 1.10).

### EP-07
- `VersioningService.create_version()` must set `SERIALIZABLE` isolation explicitly (ALG-2).
- Timeline event INSERT must be in the same transaction as the triggering action — add explicit integration test (TC-4).
- `DiffService` is pure and has no state. It should be a module of functions, not a class. A class with no `__init__` state is pointless overhead.
- Anchor recompute Celery task: no test for the concurrent section save case — two saves to the same section could enqueue two anchor recompute tasks. Add deduplication (Redis key per section).

### EP-08
- Fix inbox Tier 2 state value (`changes_requested` not `returned`) (ALG-5).
- Remove Tiers 3 and 4 — they reference non-existent schema (ALG-6).
- Move UNION SQL from `InboxService` to `InboxRepository` implementation (LV-3).
- `execute_action` — replace with `QuickActionDispatcher` to prevent `NotificationService` becoming a god object (SD-4).
- DLQ must be configured at infrastructure level — add to EP-12 Celery config (CA-2).
- Add `workspace_id` to `review_requests` indexes in the inbox query (security review CRIT-2 requirement).

### EP-10
- Add partial UNIQUE constraint on `validation_rules` for workspace-scoped rules (ALG-7).
- `MemberService.invite()` — Celery task dispatch must happen after transaction commit (SD-5).
- Move `DashboardService` aggregation SQL to repository layer (LV-4).
- `AuditService.record()` in same transaction is correct. No change needed, but document the performance risk at scale (TC-5).
- `CredentialsStore.rotate()` design is insufficient — see security review HIGH-3.

### EP-11
- `ExportTask` — move `AuditService.record()` call to `ExportService` application layer (LV-5).
- Set `soft_time_limit=45` on `export_task` to guard against hung Jira connections (CA-3).
- `sync_task` — add paginated loop to handle backlog (CA-5).
- Snapshot PII (`assignee.email`) — address security review MED-4.

---

## Strengths (validated patterns)

1. **Custom FSM (EP-01)** — `frozenset` of tuples, pure function, no callbacks. Correct. The decision to keep business rules (validation gate) out of the FSM and in the service layer is the right separation.

2. **Adapter pattern for LLM (EP-03)** — Domain never imports provider SDK. `LLMProvider` Protocol with `FakeLLMAdapter` for tests. Clean isolation. Correct.

3. **Two-layer idempotency in ExportTask (EP-11)** — Pre-dispatch guard (Layer 1) and pre-call guard (Layer 2) together make `acks_late=True` safe. Correct pattern for at-least-once Celery delivery.

4. **Audit as synchronous in-transaction write (EP-10)** — Correct choice. Async audit risks losing events on crash. The `no_update_audit` / `no_delete_audit` PostgreSQL rules as a backstop to the interface-level enforcement is good defense-in-depth.

5. **Iterative cycle detection with full path return (EP-05)** — Correct algorithm choice. Iterative DFS avoids Python's recursion limit on large graphs. The path return for the 422 response is good UX. Fix the implementation bug (ALG-1), keep the design.

6. **Pure dimension checkers (EP-04)** — `(WorkItem, list[Section], list[Validator]) -> DimensionResult` pure functions. No I/O, no side effects. Trivially testable with parametrized inputs. Correct approach.

7. **Capability array over RBAC (EP-10)** — With 10 static capabilities and no role inheritance, `text[]` + GIN index is simpler and more direct than RBAC tables. The "can only grant what you hold" constraint is clean and covers the main escalation path. ⚠️ originally MVP-scoped — see decisions_pending.md

8. **`timeline_events` table over UNION ALL (EP-07)** — Fan-in on write is the correct call. UNION ALL across 5 tables with cursor pagination would be unmaintainable. Single append-only table with indexed cursor pagination is the right primitive.

9. **Snapshot reuse on retry (EP-11)** — `retry_export()` reuses `snapshot_data` instead of rebuilding. Correct — rebuild would create different payload, violating the semantic of "retry" and breaking idempotency.

10. **Repository interfaces in domain layer (all epics)** — Every epic defines `IXxxRepository` interfaces in `domain/repositories/` with implementations in `infrastructure/persistence/`. Dependency direction is consistently inward. DIP is honored throughout.

---

## Summary

| Category | Count | Severity |
|----------|-------|----------|
| Algorithm bugs (correctness) | 7 | Must fix before implementation |
| Layer violations | 5 | Must fix before implementation |
| Service design issues | 5 | Should fix |
| Transaction/concurrency risks | 5 | Should fix (3 must, 2 document) |
| Celery/async issues | 5 | Must fix (3), should fix (2) |
| Strengths | 10 | Preserve |

**Priority order**:
1. ALG-5, ALG-6 (inbox schema phantoms — will fail at runtime)
2. ALG-1 (cycle detector path bug — API returns wrong data)
3. ALG-2 (version number concurrency — DB errors in production)
4. LV-1 (dual versioning ownership — data inconsistency)
5. TC-3 (review + validation transaction boundary — data inconsistency)
6. CA-1 (suggestion task idempotency — duplicate LLM output)
7. CA-4 (summarisation concurrency — duplicate summaries)
8. Rest in order of SD/LV findings
