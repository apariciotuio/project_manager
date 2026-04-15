# EP-01 Backend Tasks — Work Item Lifecycle & State Machine

Branch: `feature/ep-01-backend`
Refs: EP-01
Depends on: EP-00 (users, workspaces, auth middleware)

---

## API Contract (Frontend Dependency)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/work-items` | JWT | Create work item |
| GET | `/api/v1/work-items/{id}` | JWT | Get single work item |
| GET | `/api/v1/projects/{project_id}/work-items` | JWT | List paginated |
| PATCH | `/api/v1/work-items/{id}` | JWT | Update fields |
| DELETE | `/api/v1/work-items/{id}` | JWT (owner) | Soft delete (draft only) |
| POST | `/api/v1/work-items/{id}/transitions` | JWT | State transition |
| POST | `/api/v1/work-items/{id}/force-ready` | JWT (owner) | Override to ready |
| PATCH | `/api/v1/work-items/{id}/owner` | JWT (owner or admin) | Reassign owner |
| GET | `/api/v1/work-items/{id}/transitions` | JWT | Audit trail |
| GET | `/api/v1/work-items/{id}/ownership-history` | JWT | Ownership audit |

**POST /work-items/{id}/transitions** request:
```json
{ "target_state": "in_review", "reason": "optional context" }
```

**POST /work-items/{id}/force-ready** request:
```json
{ "justification": "reason text", "confirmed": true }
```

Success envelope: `{ "data": {...work_item...}, "message": "..." }`
Error envelope: `{ "error": { "code": "INVALID_TRANSITION", "message": "...", "details": { "from_state": "draft", "to_state": "in_review" } } }`

---

## Phase 1 — Domain Layer

### 1.1 Enums and Value Objects

- [x] [RED] Write parametrized unit tests covering all 7 `WorkItemState` values, all 8 `WorkItemType` values, all 3 `DerivedState` values — tests/unit/domain/test_work_item_enums.py (2026-04-15)
- [x] [GREEN] Implement `domain/value_objects/work_item_state.py` — `WorkItemState(StrEnum)` with all 7 states (2026-04-15)
- [x] [GREEN] Implement `domain/value_objects/work_item_type.py` — `WorkItemType(StrEnum)` with all 8 types (2026-04-15)
- [x] [GREEN] Implement `domain/value_objects/derived_state.py` — `DerivedState(StrEnum)` (2026-04-15)
- [x] [GREEN] Implement `domain/value_objects/state_transition.py` — frozen dataclass: `work_item_id`, `from_state`, `to_state`, `actor_id`, `triggered_at`, `reason`, `is_override`, `override_justification` (2026-04-15)
- [x] [GREEN] Implement `domain/value_objects/ownership_record.py` — frozen dataclass: `work_item_id`, `previous_owner_id`, `new_owner_id`, `changed_by`, `changed_at`, `reason` (2026-04-15)
- [x] [GREEN] Implement `domain/value_objects/priority.py` — `Priority(StrEnum)` with 4 ordered values (2026-04-15)
- [x] [REFACTOR] All value objects are immutable frozen dataclasses with no external dependencies; enums use `StrEnum` per ruff UP042 (2026-04-15)

### 1.2 State Machine

- [x] [RED] Write parametrized tests for all 14 valid transitions in `VALID_TRANSITIONS` — each should return `True` from `is_valid_transition()` (2026-04-15)
- [x] [RED] Write parametrized tests for 14 invalid transitions (exported→* 6 cases + 8 explicit rejects) — each should return `False` (2026-04-15)
- [x] [GREEN] Implement `domain/state_machine.py` — `VALID_TRANSITIONS: frozenset[tuple[WorkItemState, WorkItemState]]` (exactly 14 edges) and `is_valid_transition(from_state, to_state) -> bool` (2026-04-15)
- [x] [REFACTOR] Zero logic beyond frozenset membership check; 100% branch coverage trivially achieved (2026-04-15)

### Acceptance Criteria — State Machine

See also: specs/state-machine/spec.md

WHEN `is_valid_transition(WorkItemState.DRAFT, WorkItemState.IN_CLARIFICATION)` is called
THEN it returns `True`

WHEN `is_valid_transition(WorkItemState.DRAFT, WorkItemState.READY)` is called
THEN it returns `False`

WHEN `is_valid_transition(WorkItemState.EXPORTED, WorkItemState.DRAFT)` is called
THEN it returns `False` (exported is terminal — no outbound transitions)

WHEN `is_valid_transition(WorkItemState.CHANGES_REQUESTED, WorkItemState.READY)` is called
THEN it returns `False` (must address changes before ready)

### 1.3 WorkItem Entity

- [x] [RED] Write tests: construction defaults, `state=DRAFT`, `completeness_score=0`, `has_override=False`, `tags=[]`, `deleted_at=None` — tests/unit/domain/test_work_item.py (2026-04-15)
- [x] [RED] Write tests: title validation — 2 chars raises, 3 chars passes, 255 chars passes, 256 chars raises (2026-04-15)
- [x] [RED] Write tests: `can_transition_to()` — valid/invalid transitions and non-owner → `(False, "not_owner")` (2026-04-15)
- [x] [RED] Write tests: `apply_transition()` — returns `StateTransition` with correct `triggered_at`, raises on invalid/non-owner (2026-04-15)
- [x] [RED] Write tests: `force_ready()` — `has_override=True`, `is_override=True`, non-owner raises, short justification raises (2026-04-15)
- [x] [RED] Write tests: `reassign_owner()` — `OwnershipRecord` returned, same-owner raises, `owner_id` updated (2026-04-15)
- [x] [RED] Write tests: `compute_completeness()` — stub returns 0 consistently (2026-04-15)
- [x] [RED] Write tests: `derived_state` — BLOCKED when suspended, IN_PROGRESS when active, READY when state=ready, None when EXPORTED (2026-04-15)
- [x] [GREEN] Implement `domain/models/work_item.py` — `WorkItem` dataclass with all fields from design.md and domain methods (2026-04-15)
- [x] [GREEN] Implement `domain/exceptions.py` — `InvalidTransitionError`, `NotOwnerError`, `InvalidOverrideError`, `MandatoryValidationsPendingError`, `OwnerSuspendedError`, `TargetUserNotInWorkspaceError`, `WorkItemNotFoundError`, `CannotDeleteNonDraftError` (2026-04-15)
- [x] [REFACTOR] Zero infrastructure imports in `work_item.py`; `compute_completeness` stub with `# TODO(EP-04)` comment (2026-04-15)

### Acceptance Criteria — WorkItem Entity

See also: specs/work-item-model/spec.md, specs/ownership/spec.md, specs/state-machine/spec.md

WHEN a `WorkItem` is constructed with only required fields (`title`, `type`, `owner_id`, `creator_id`, `project_id`)
THEN `state = DRAFT`, `completeness_score = 0`, `has_override = False`, `tags = []`, `deleted_at = None`

WHEN a `WorkItem` is constructed with `title = "ab"` (2 chars)
THEN a `ValueError` is raised mentioning title length

WHEN a `WorkItem` is constructed with `title = "abc"` (3 chars)
THEN no exception is raised

WHEN `WorkItem.apply_transition(target_state=READY, actor_id=owner_id)` is called
THEN it returns a `StateTransition` with `from_state=current`, `to_state=READY`, `actor_id=owner_id`, `triggered_at` within 1s of now()

WHEN `WorkItem.apply_transition(target_state=READY, actor_id=non_owner_id)` is called
THEN it raises `NotOwnerError`

WHEN `WorkItem.force_ready(justification="reason text", actor_id=owner_id)` is called
THEN `work_item.has_override = True`
AND the returned `StateTransition.is_override = True`
AND `StateTransition.override_justification = "reason text"`

WHEN `WorkItem.reassign_owner(new_owner_id, changed_by)` is called
THEN it returns an `OwnershipRecord` with `previous_owner_id = old owner`, `new_owner_id`, `changed_by`
AND `work_item.owner_id` is updated to `new_owner_id`

WHEN `work_item.owner_suspended_flag = True`
THEN `work_item.derived_state = DerivedState.BLOCKED`
AND `work_item.blocked_reason` contains `"owner_suspended"`

WHEN `work_item.state = EXPORTED`
THEN `work_item.derived_state = None`

### Acceptance Criteria — Hierarchy + Attachments (EP-14 / EP-16 extensions)

WHEN a work item is created with `parent_work_item_id` set
THEN `HierarchyValidator.validate_parent(child_type, parent_type)` is called before persistence (implementation in EP-14)
AND if validation fails, `HierarchyValidationError` is raised and no work item is persisted

WHEN `attachment_count` is read from a work item in a list response
THEN no JOIN to the `attachments` table is required (value is denormalized)
AND the count reflects the current number of non-soft-deleted attachments (maintained by EP-16's `AttachmentService`)

### 1.4 Domain Exceptions

- [x] [GREEN] Implement `domain/exceptions.py` with all typed exceptions: `InvalidTransitionError`, `NotOwnerError`, `InvalidOverrideError`, `MandatoryValidationsPendingError`, `OwnerSuspendedError`, `TargetUserNotInWorkspaceError`, `WorkItemNotFoundError`, `CannotDeleteNonDraftError` (2026-04-15)

**Status: COMPLETED** (2026-04-15)

---

## Phase 2 — Infrastructure: Persistence

### 2.1 Database Migrations

- [x] Write Alembic migration `0009_create_work_items` (single migration): `work_items`, `state_transitions`, `ownership_history` tables with all columns, CHECK constraints, indexes, RLS policies, append-only triggers (2026-04-15)
- [x] Verify downgrade path: `alembic downgrade -1 && alembic upgrade head` — clean roundtrip (2026-04-15)

### 2.2 ORM Models

- [x] Implement `WorkItemORM`, `StateTransitionORM`, `OwnershipHistoryORM` in `infrastructure/persistence/models/orm.py` — all columns, constraints, indexes matching migration schema (2026-04-15)

### 2.3 Mappers

- [x] [RED] Write unit tests for mapper round-trips in `tests/unit/infrastructure/test_work_item_mappers.py` — `WorkItem → WorkItemORM → WorkItem` preserves all fields, enum string values, null handling (2026-04-15)
- [x] [GREEN] Implement `infrastructure/persistence/mappers/work_item_mapper.py`, `state_transition_mapper.py`, `ownership_record_mapper.py` (2026-04-15)

### 2.4 Repository Interface

- [x] Implement `domain/repositories/work_item_repository.py` — `IWorkItemRepository` ABC with all methods accepting `workspace_id`; returns `None` on workspace mismatch (existence disclosure prevention CRIT-2); return types use `Sequence` to avoid mypy method-name shadowing with builtin `list` (2026-04-15)
- [x] Implement `domain/queries/work_item_filters.py` — `WorkItemFilters` frozen dataclass with state/type/owner_id/has_override/include_deleted/page/page_size (2026-04-15)
- [x] Implement `domain/queries/page.py` — `Page[T]` generic dataclass (2026-04-15)

### 2.5 Repository Implementation

- [x] Implement `infrastructure/persistence/work_item_repository_impl.py` — UPSERT via `ON CONFLICT(id) DO UPDATE RETURNING *`, single-query COUNT using `func.count().over()` window function, explicit `workspace_id` filter on all queries (defense in depth + RLS), `IntegrityError` → `UserNotFoundError`/`InvalidWorkItemError` mapping (2026-04-15)
- [x] Implement `infrastructure/persistence/session_context.py` — `with_workspace()` using `set_config('app.current_workspace', wid, true)` (SET LOCAL, transaction-scoped) (2026-04-15)

### 2.6 Integration Tests

- [x] [RED→GREEN] Write `tests/integration/infrastructure/test_work_item_repository.py` — 20 tests covering: save+get round-trip (all fields, null priority, empty tags, null parent), list filter combos (state/type/has_override), pagination math (3 pages), soft-delete exclusion/inclusion, record_transition+get_transitions DESC ordering, record_ownership_change+get_ownership_history DESC ordering, cross-workspace isolation (get with wrong workspace_id returns None), append-only trigger raises on UPDATE (state_transitions + ownership_history), FK violation → UserNotFoundError, RLS default-deny without set_config (2026-04-15)
- [x] Add `wmp_app` non-superuser role fixture + `rls_session` fixture to `tests/conftest.py` — proves RLS enforced for non-superusers; db_session TRUNCATE extended to include work_items/state_transitions/ownership_history (2026-04-15)

### 2.7 Type Safety

- [x] Fix pre-existing mypy errors in `work_item_repository_impl.py`, `domain/repositories/work_item_repository.py`, `infrastructure/persistence/models/orm.py` — `Sequence` return types, `dict[str, object]` annotations (0 new mypy errors introduced) (2026-04-15)

**Status: COMPLETED** (2026-04-15)

---

## Phase 3 — Application Layer

### 3.1 Commands and Filters

- [x] Implement `application/commands/create_work_item_command.py` — frozen dataclass with `title`, `type`, `workspace_id`, `project_id`, `creator_id`, `owner_id?`, `description?`, `priority?`, `due_date?`, `tags: tuple` (2026-04-15)
- [x] Implement `application/commands/update_work_item_command.py` — all optional fields except `state` (excluded with comment); no `owner_id`/`workspace_id`/`project_id` (2026-04-15)
- [x] Implement `application/commands/transition_state_command.py` — `item_id`, `workspace_id`, `target_state`, `actor_id`, `reason?` (2026-04-15)
- [x] Implement `application/commands/force_ready_command.py` — `item_id`, `workspace_id`, `actor_id`, `justification`, `confirmed: bool` (2026-04-15)
- [x] Implement `application/commands/reassign_owner_command.py` — `item_id`, `workspace_id`, `actor_id`, `new_owner_id`, `reason?` (2026-04-15)
- [x] Implement `application/commands/delete_work_item_command.py` — `item_id`, `workspace_id`, `actor_id` (2026-04-15)
- [x] `application/queries/work_item_filters.py` — already satisfied by `domain/queries/work_item_filters.py` (Phase 2); no duplication needed (2026-04-15)

### 3.2 Event Bus

- [x] Implement `application/events/event_bus.py` — async event bus: `subscribe(event_type, handler)`, `emit(event)` (fire-and-forget, handler exceptions logged, never re-raised) (2026-04-15)
- [x] Implement typed event dataclasses for all 8 events in `application/events/events.py`: `WorkItemCreatedEvent`, `WorkItemStateChangedEvent`, `WorkItemReadyOverrideEvent`, `WorkItemRevertedFromReadyEvent`, `WorkItemOwnerChangedEvent`, `WorkItemChangesRequestedEvent`, `WorkItemContentChangedAfterReadyEvent`, `WorkspaceMemberSuspendedWithActiveItemsEvent` (2026-04-15)

### 3.3 WorkItemService

- [x] [RED] Write unit tests using `FakeWorkItemRepository` (not real DB) — 30 tests across `TestCreate`, `TestTransition`, `TestForceReady`, `TestReassign`, `TestDelete`, `TestUpdate` covering all acceptance criteria (2026-04-15)
- [x] [GREEN] Implement `application/services/work_item_service.py` — all 10 methods, DIP constructor injection, `OwnerSuspendedError`/`CreatorNotMemberError`/`MandatoryValidationsPendingError`/`ConfirmationRequiredError`/`TargetUserSuspendedError`/`CannotDeleteNonDraftError` raised correctly; auto-revert on content change; system actor (None) for system transitions (2026-04-15)
- [x] [REFACTOR] `domain/services/completeness_service.py` — pure function stub with `# TODO(EP-04)` comment; `WorkItem.compute_completeness()` left as-is (domain keeps its own stub, service calls the domain-services version) (2026-04-15)
- [x] Migration `0010_system_actor` — drops FK on `state_transitions.actor_id` + makes column nullable; `StateTransitionORM.actor_id` updated to `Mapped[UUID | None]`; `StateTransition.actor_id` updated to `UUID | None`; mapper updated (2026-04-15)
- [x] `domain/constants.py` — `SYSTEM_ACTOR_ID = None`, `COMPLETENESS_READY_THRESHOLD = 80` (2026-04-15)
- [x] Added `TargetUserSuspendedError`, `CreatorNotMemberError`, `ConfirmationRequiredError` to `domain/exceptions.py`; updated `MandatoryValidationsPendingError` to `pending_ids: tuple` (2026-04-15)
- [x] `FakeWorkItemRepository` added to `tests/fakes/fake_repositories.py` — in-memory dict keyed by `(workspace_id, id)`, tracks `transitions` and `ownership_records` lists (2026-04-15)
- [x] `tests/unit/application/test_event_bus.py` — 7 tests: sub/emit round-trip, multi-handler, no-subscribers no-op, exception isolation, different event types isolated (2026-04-15)

**Status: COMPLETED** (2026-04-15)

### Acceptance Criteria — WorkItemService

See also: specs/work-item-model/spec.md, specs/state-machine/spec.md, specs/ownership/spec.md

WHEN `WorkItemService.create(title, type, creator_id, project_id)` is called without `owner_id`
THEN the created work item has `owner_id = creator_id`
AND `state = DRAFT`
AND `completeness_score` is computed synchronously

WHEN `WorkItemService.create()` is called with an `owner_id` that belongs to a suspended user
THEN it raises `OwnerSuspendedError` and no work item is persisted

WHEN `WorkItemService.transition(item_id, target_state=IN_REVIEW, actor_id=owner_id)` is called on a `DRAFT` item
THEN it raises `InvalidTransitionError` (draft → in_review is invalid)
AND the `state_transitions` table has NO new row

WHEN `WorkItemService.transition(item_id, target_state=READY, actor_id=owner_id)` is called and mandatory validations are pending
THEN it raises `MandatoryValidationsPendingError` with `pending_ids` list
AND no `state_transitions` row is inserted

WHEN `WorkItemService.force_ready(item_id, justification="", confirmed=True, actor_id=owner_id)` is called
THEN it raises `ValueError` (justification required, min 10 chars per the endpoint schema)

WHEN `WorkItemService.force_ready(item_id, justification="reason text here", confirmed=False, actor_id=owner_id)` is called
THEN it raises `ConfirmationRequiredError` with the list of pending validation IDs

WHEN `WorkItemService.update(item_id, {title: "new title"}, actor_id=owner_id)` is called on a `READY` item
THEN the title is updated
AND the item auto-transitions back to `IN_CLARIFICATION`
AND a `state_transitions` row is inserted with `actor_id = 'system'`
AND `WorkItemContentChangedAfterReadyEvent` is emitted
AND `has_override` is reset to `False`

WHEN `WorkItemService.delete(item_id)` is called on an `IN_REVIEW` item
THEN it raises `CannotDeleteNonDraftError`

WHEN `WorkItemService.reassign(item_id, new_owner_id=suspended_user_id, actor_id=owner_id)` is called
THEN it raises `TargetUserSuspendedError`

---

## Phase 4 — Presentation Layer

### 4.1 Pydantic Schemas

- [x] Implement `presentation/schemas/work_item_schemas.py`: all 7 schemas with Pydantic v2, `ConfigDict(extra="forbid")`, full typing — 2026-04-15, already implemented in prior session

### 4.2 Controllers

- [x] [RED] Write controller integration tests: 24 tests across all 10 routes, happy + error paths — 2026-04-15, already implemented in prior session
- [x] [GREEN] Implement `presentation/controllers/work_item_controller.py` — 10 routes, thin handlers, type-safe, ruff+mypy clean — 2026-04-15
- [x] Register router on FastAPI app with prefix `/api/v1` — 2026-04-15, already wired in main.py

### Acceptance Criteria — Controllers

See also: specs/work-item-model/spec.md, specs/state-machine/spec.md, specs/ownership/spec.md

**POST /api/v1/work-items**
WHEN called with valid `{ title: "Bug X", type: "bug", project_id: "uuid" }`
THEN response is HTTP 201 with body `{ "data": { ...WorkItemResponse... }, "message": "Work item created" }`
AND `data.state = "draft"`, `data.completeness_score` is an integer 0–100

WHEN called with `{ title: "AB", type: "bug", project_id: "uuid" }` (title too short)
THEN response is HTTP 422 `{ "error": { "code": "VALIDATION_ERROR", "details": { "field": "title" } } }`

WHEN called with `{ type: "bug", project_id: "uuid" }` (missing title)
THEN response is HTTP 422 with field `title` identified

WHEN called without auth cookie
THEN response is HTTP 401

**GET /api/v1/work-items/{id}**
WHEN called with a UUID that does not exist
THEN response is HTTP 404 `{ "error": { "code": "WORK_ITEM_NOT_FOUND" } }`

WHEN called with a valid ID for an item in a project the user cannot access
THEN response is HTTP 403

**PATCH /api/v1/work-items/{id}**
WHEN body includes `{ "state": "in_review" }`
THEN response is HTTP 422 `{ "error": { "code": "VALIDATION_ERROR", "details": { "reason": "use_transition_endpoint" } } }`
AND item state is unchanged

**POST /api/v1/work-items/{id}/transitions**
WHEN called with `{ "target_state": "exported" }` on a `DRAFT` item
THEN response is HTTP 422 `{ "error": { "code": "INVALID_TRANSITION", "details": { "from_state": "draft", "to_state": "exported" } } }`

WHEN called with a valid transition and non-empty `reason` for `changes_requested`
THEN response is HTTP 200 with updated `WorkItemResponse`
AND `state_transitions` table has a new row

**POST /api/v1/work-items/{id}/force-ready**
WHEN called by a non-owner
THEN response is HTTP 403 `{ "error": { "code": "NOT_OWNER" } }`

WHEN called with `{ "justification": "short", "confirmed": true }` (justification < 10 chars)
THEN response is HTTP 422 `{ "error": { "code": "VALIDATION_ERROR", "details": { "field": "justification" } } }`

WHEN called with valid justification and `confirmed: false`
THEN response is HTTP 422 `{ "error": { "code": "CONFIRMATION_REQUIRED", "details": { "pending_validation_ids": [...] } } }`

**PATCH /api/v1/work-items/{id}/owner**
WHEN called by a non-owner, non-admin user
THEN response is HTTP 403 `{ "error": { "code": "NOT_OWNER" } }`

WHEN called with `{ "new_owner_id": "uuid-of-suspended-user" }`
THEN response is HTTP 422 `{ "error": { "code": "TARGET_USER_SUSPENDED" } }`

**GET /api/v1/projects/{project_id}/work-items**
WHEN called with `?state=in_review`
THEN response is HTTP 200 with `{ "data": { "items": [...], "total": N, "page": 1, "page_size": 20 } }`
AND all items in `data.items` have `state = "in_review"`

WHEN called with `?has_override=true`
THEN only items with `has_override = true` are returned

**DELETE /api/v1/work-items/{id}**
WHEN item is in `DRAFT` state and caller is owner
THEN response is HTTP 204

WHEN item is in any non-DRAFT state
THEN response is HTTP 422 `{ "error": { "code": "CANNOT_DELETE_NON_DRAFT" } }`

### 4.3 Error Middleware

- [x] All EP-01 domain exception handlers implemented in `error_middleware.py`: `InvalidTransitionError → 422`, `NotOwnerError → 403`, `MandatoryValidationsPendingError → 422`, `ConfirmationRequiredError → 422`, `OwnerSuspendedError → 422`, `TargetUserSuspendedError → 422`, `WorkItemNotFoundError → 404`, `CannotDeleteNonDraftError → 422`, `CreatorNotMemberError → 403` — 2026-04-15, already implemented in prior session
- [x] Unit tests added for all EP-01 handlers (9 parametrized + 4 detail assertions): `tests/unit/presentation/test_error_middleware.py` — 2026-04-15

**Status: COMPLETED** (2026-04-15)

---

## Phase 5 — Observability

- [x] Structured logging in `WorkItemService.transition` at INFO: `item_id`, `from_state`, `to_state`, `actor_id`, `workspace_id` — 2026-04-15, already implemented in prior session
- [x] Structured logging in `WorkItemService.force_ready` at WARN: `item_id`, `actor_id`, `workspace_id`, `justification` (truncated to 200 chars) — 2026-04-15, already implemented in prior session
- [x] Structured logging for suspended-owner blocks at WARN: `user_id`, `workspace_id` (create path) and `user_id`, `item_id` (reassign path) — 2026-04-15, already implemented in prior session
- [x] No PII: only `user_id` UUIDs logged, no email in work item paths — verified 2026-04-15

**Status: COMPLETED** (2026-04-15)

---

## Definition of Done

- [x] All tests pass (unit + integration) — 427 pass (non-infra) + 46 infra = 473 total — 2026-04-15
- [x] `mypy --strict` clean on all EP-01 modules (work_item_controller, work_item_schemas, error_middleware, dependencies, work_item_service) — 2026-04-15
- [x] `ruff` clean on all EP-01 modules; B008 suppressed project-wide (FastAPI pattern) — 2026-04-15
- [ ] Migrations apply and roll back cleanly on fresh DB — not re-verified in this session (infra tests pass)
- [x] All 10 API endpoints handle happy path and documented error cases correctly — 24 integration tests — 2026-04-15
- [x] `state_transitions` table populated for every state change in integration test run — verified by `test_transition_valid_returns_200_and_persists_row` — 2026-04-15
- [x] `ownership_history` table populated for every reassignment in integration test run — verified by `test_reassign_owner_valid_returns_200` — 2026-04-15
- [x] `has_override = true` items are filterable via list endpoint with `?has_override=true` — verified by `test_list_with_has_override_filter` — 2026-04-15
