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

- [ ] [RED] Write parametrized unit tests covering all 7 `WorkItemState` values, all 8 `WorkItemType` values, all 3 `DerivedState` values
- [ ] [GREEN] Implement `domain/value_objects/work_item_state.py` — `WorkItemState(str, Enum)` with all 7 states: `draft`, `in_clarification`, `in_review`, `changes_requested`, `partially_validated`, `ready`, `exported`
- [ ] [GREEN] Implement `domain/value_objects/work_item_type.py` — `WorkItemType(str, Enum)` with all 8 types
- [ ] [GREEN] Implement `domain/value_objects/derived_state.py` — `DerivedState(str, Enum)`
- [ ] [GREEN] Implement `domain/value_objects/state_transition.py` — frozen dataclass: `work_item_id`, `from_state`, `to_state`, `actor_id`, `triggered_at`, `reason`, `is_override`, `override_justification`
- [ ] [GREEN] Implement `domain/value_objects/ownership_record.py` — frozen dataclass: `work_item_id`, `previous_owner_id`, `new_owner_id`, `changed_by`, `changed_at`, `reason`
- [ ] [REFACTOR] All value objects are immutable frozen dataclasses with no external dependencies

### 1.2 State Machine

- [ ] [RED] Write parametrized tests for all 14 valid transitions in `VALID_TRANSITIONS` — each should return `True` from `is_valid_transition()`
- [ ] [RED] Write parametrized tests for 10+ invalid transitions (e.g., `draft → ready`, `exported → draft`) — each should return `False`
- [ ] [GREEN] Implement `domain/state_machine.py` — `VALID_TRANSITIONS: frozenset[tuple[WorkItemState, WorkItemState]]` and `is_valid_transition(from_state, to_state) -> bool`
- [ ] [REFACTOR] Verify 100% branch coverage on state machine; no logic other than the dict lookup

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

- [ ] [RED] Write tests: construction with valid fields sets all defaults correctly (`state=DRAFT`, `completeness_score=0`, `has_override=False`, `tags=[]`)
- [ ] [RED] Write tests: title validation — 2 chars raises, 3 chars passes, 255 chars passes, 256 chars raises
- [ ] [RED] Write tests: `can_transition_to()` — delegates to `is_valid_transition()`, non-owner actor raises `NotOwnerError`
- [ ] [RED] Write tests: `apply_transition()` — returns correct `StateTransition` value object with `triggered_at` set to current time
- [ ] [RED] Write tests: `force_ready()` — sets `has_override=True`, stores `justification`, returns `StateTransition` with `is_override=True`
- [ ] [RED] Write tests: `reassign_owner()` — returns correct `OwnershipRecord` with `previous_owner_id`, `new_owner_id`, `changed_by`
- [ ] [RED] Write parametrized tests for `compute_completeness()` — 6 cases covering score = 0, 10, 35, 60, 80, 100
- [ ] [RED] Write tests for `derived_state` property — 5 conditions: `BLOCKED` when owner suspended, `IN_PROGRESS` when active state, `READY` when completeness ≥ 30 and state = `ready`, returns `None` when `EXPORTED`
- [ ] [GREEN] Implement `domain/models/work_item.py` — `WorkItem` dataclass with all fields from design.md and domain methods
- [ ] [REFACTOR] Zero infrastructure imports in `work_item.py`; completeness strategy per type extracted to callable dict

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

### 1.4 Domain Exceptions

- [ ] [GREEN] Implement `domain/exceptions.py` with all typed exceptions:
  - `InvalidTransitionError(from_state, to_state)`
  - `NotOwnerError(actor_id, item_id)`
  - `MandatoryValidationsPendingError(item_id, validation_ids)`
  - `OwnerSuspendedError(owner_id)`
  - `TargetUserNotInWorkspaceError(user_id)`
  - `WorkItemNotFoundError(item_id)`
  - `CannotDeleteNonDraftError(item_id, state)`

---

## Phase 2 — Infrastructure: Persistence

### 2.1 Database Migrations

- [ ] Write Alembic migration `create_work_items_table`: all columns from design.md schema, CHECK constraints for `type` and `state` enums, CHECK constraint for title length (3–255), CHECK constraint for `completeness_score` range (0–100), all 6 indexes
- [ ] Write Alembic migration `create_state_transitions_table`: all columns, index on `(work_item_id, triggered_at DESC)`
- [ ] Write Alembic migration `create_ownership_history_table`: all columns, index on `(work_item_id, changed_at DESC)`
- [ ] Run all 3 migrations in dev environment; verify schema with `psql \d work_items`
- [ ] Verify downgrade path: all 3 migrations roll back cleanly

### 2.2 ORM Models

- [ ] Implement `infrastructure/persistence/models/work_item_orm.py` — SQLAlchemy `WorkItemORM` mapped class matching migration schema
- [ ] Implement `infrastructure/persistence/models/state_transition_orm.py`
- [ ] Implement `infrastructure/persistence/models/ownership_history_orm.py`

### 2.3 Mappers

- [ ] [RED] Write unit tests for mapper round-trips: `WorkItem → WorkItemORM → WorkItem` preserves all fields, enum string values map correctly
- [ ] [GREEN] Implement `infrastructure/persistence/mappers/work_item_mapper.py`

### 2.4 Repository Interface

- [ ] Refactor: all repository methods must accept `workspace_id` as a required parameter — `get(item_id, workspace_id)`, `list(workspace_id, ...)`. Queries must include `WHERE workspace_id = :workspace_id`. Return `None` (not 403) on workspace mismatch to avoid existence disclosure (CRIT-2).
- [ ] Implement `domain/repositories/work_item_repository.py` — `IWorkItemRepository` ABC:
  - `async get(item_id: UUID, workspace_id: UUID) -> WorkItem | None`
  - `async list(workspace_id: UUID, project_id: UUID, filters: WorkItemFilters) -> Page[WorkItem]`
  - `async save(item: WorkItem) -> WorkItem`
  - `async delete(item_id: UUID) -> None`
  - `async record_transition(transition: StateTransition) -> None`
  - `async record_ownership_change(record: OwnershipRecord) -> None`
  - `async get_transitions(item_id: UUID) -> list[StateTransition]`
  - `async get_ownership_history(item_id: UUID) -> list[OwnershipRecord]`

### 2.5 Repository Implementation

- [ ] [RED] Write integration tests against real test PostgreSQL DB:
  - `save` + `get` round-trip preserves all fields
  - `list` with `state=in_review` filter returns only matching items
  - Soft-deleted items excluded from `list` results
  - `record_transition` inserts row in `state_transitions`
  - `record_ownership_change` inserts row in `ownership_history`
- [ ] [GREEN] Implement `infrastructure/persistence/repositories/work_item_repository_impl.py`
- [ ] [REFACTOR] Verify no N+1 queries in `list` — use single query with explicit JOINs if owner data needed

---

## Phase 3 — Application Layer

### 3.1 Commands and Filters

- [ ] Implement `application/commands/create_work_item_command.py` — typed dataclass: `title`, `type`, `owner_id`, `creator_id`, `project_id`, `description?`, `priority?`, `due_date?`, `tags?`
- [ ] Implement `application/commands/update_work_item_command.py` — all optional fields except `state` (excluded from update)
- [ ] Implement `application/commands/transition_state_command.py` — `item_id`, `target_state`, `actor_id`, `reason?`
- [ ] Implement `application/commands/force_ready_command.py` — `item_id`, `actor_id`, `justification`, `confirmed: bool`
- [ ] Implement `application/commands/reassign_owner_command.py` — `item_id`, `new_owner_id`, `actor_id`, `reason?`
- [ ] Implement `application/queries/work_item_filters.py` — `state?`, `type?`, `owner_id?`, `has_override?`, `page`, `page_size`

### 3.2 Event Bus

- [ ] Implement `application/events/event_bus.py` — simple in-process synchronous event bus: `subscribe(event_type, handler)`, `emit(event)`
- [ ] Implement typed event dataclasses for all 8 events listed in design.md: `WorkItemCreatedEvent`, `WorkItemStateChangedEvent`, `WorkItemReadyOverrideEvent`, `WorkItemRevertedFromReadyEvent`, `WorkItemOwnerChangedEvent`, `WorkItemChangesRequestedEvent`, `WorkItemContentChangedAfterReadyEvent`, `WorkspaceMemberSuspendedWithActiveItemsEvent`

### 3.3 WorkItemService

- [ ] [RED] Write unit tests using fake repository (not real DB):
  - `create`: defaults `owner_id` to `creator_id` when not provided, suspended owner raises `OwnerSuspendedError`
  - `transition`: valid edge succeeds and emits `WorkItemStateChangedEvent`
  - `transition`: invalid edge raises `InvalidTransitionError`
  - `transition`: non-owner raises `NotOwnerError`
  - `transition` to `ready`: pending mandatory validations raises `MandatoryValidationsPendingError`
  - `transition` to `ready`: no pending validations succeeds
  - `force_ready`: missing justification raises `ValueError`, missing `confirmed=True` raises `ConfirmationRequiredError`
  - `force_ready`: sets `has_override=True` and stores justification, emits `WorkItemReadyOverrideEvent`
  - `force_ready`: non-owner raises `NotOwnerError`
  - `reassign`: owner can reassign; admin can reassign; non-owner non-admin raises `NotOwnerError`
  - `reassign`: suspended target raises `TargetUserSuspendedError`
  - `delete`: non-draft item raises `CannotDeleteNonDraftError`
  - `update`: content update on `ready` item emits `WorkItemContentChangedAfterReadyEvent` and auto-reverts to `in_clarification`
- [ ] [GREEN] Implement `application/services/work_item_service.py`
- [ ] [REFACTOR] Extract completeness computation into `domain/services/completeness_service.py` — pure function, no service injection

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

- [ ] Implement `presentation/schemas/work_item_schemas.py`:
  - `WorkItemCreateRequest` — validates title (3–255), type required
  - `WorkItemUpdateRequest` — all optional; explicitly excludes `state` field
  - `WorkItemResponse` — includes `derived_state`, `completeness_score`, `next_step`, `override_info`
  - `TransitionRequest` — `target_state`, `reason?`
  - `ForceReadyRequest` — `justification` (required, min 10 chars), `confirmed: bool`
  - `ReassignOwnerRequest` — `new_owner_id`
  - `PagedWorkItemResponse` — `items: list[WorkItemResponse]`, `total`, `page`, `page_size`

### 4.2 Controllers

- [ ] [RED] Write controller integration tests with fake service:
  - `POST /work-items` → 201 on valid input, `WorkItemResponse` body
  - `POST /work-items` → 422 on missing title
  - `GET /work-items/{id}` → 404 when not found
  - `PATCH /work-items/{id}` → 422 when `state` field included in body
  - `DELETE /work-items/{id}` → 422 when state is not `draft`
  - `POST /work-items/{id}/transitions` → 422 with `INVALID_TRANSITION` and `details.from_state`
  - `POST /work-items/{id}/force-ready` → 403 for non-owner
  - `POST /work-items/{id}/force-ready` → 422 for missing justification
  - `PATCH /work-items/{id}/owner` → 403 for non-owner non-admin
- [ ] [GREEN] Implement `presentation/controllers/work_item_controller.py` — FastAPI router with all 10 routes
- [ ] Register router on FastAPI app with prefix `/api/v1`

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

- [ ] Add to global error handler: `InvalidTransitionError → 422 INVALID_TRANSITION`, `NotOwnerError → 403 NOT_OWNER`, `MandatoryValidationsPendingError → 422 VALIDATIONS_PENDING` (with `details.pending_ids`), `OwnerSuspendedError → 422 OWNER_SUSPENDED`, `WorkItemNotFoundError → 404 WORK_ITEM_NOT_FOUND`, `CannotDeleteNonDraftError → 422 CANNOT_DELETE_NON_DRAFT`

---

## Phase 5 — Observability

- [ ] Add structured logging in `WorkItemService` for all state transitions at INFO level: `item_id`, `from_state`, `to_state`, `actor_id`
- [ ] Add structured logging for override events at WARN level: `item_id`, `actor_id`, `justification` (truncated), `skipped_validations`
- [ ] Add structured logging for suspended-owner blocks at WARN level
- [ ] Verify no secrets or PII in log output (email is PII — log user_id only)

---

## Definition of Done

- [ ] All tests pass (unit + integration)
- [ ] `mypy --strict` clean on all EP-01 modules
- [ ] `ruff` clean
- [ ] Migrations apply and roll back cleanly on fresh DB
- [ ] All 10 API endpoints handle happy path and documented error cases correctly
- [ ] `state_transitions` table populated for every state change in integration test run
- [ ] `ownership_history` table populated for every reassignment in integration test run
- [ ] `has_override = true` items are filterable via list endpoint with `?has_override=true`
