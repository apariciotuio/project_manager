# EP-01 — Implementation Checklist

**Status: NOT STARTED**

Execution order: domain models → repositories → application services → controllers → migrations → integration tests.
Every step follows RED → GREEN → REFACTOR. Failing test must exist before implementation code.

---

## Phase 1: Domain Layer

### 1.1 Enums and Value Objects

- [ ] [RED] Write tests for `WorkItemState`, `WorkItemType`, `DerivedState` enum coverage
- [ ] [GREEN] Implement `domain/value_objects/work_item_state.py` — all 7 states
- [ ] [GREEN] Implement `domain/value_objects/work_item_type.py` — all 8 types
- [ ] [GREEN] Implement `domain/value_objects/derived_state.py`
- [ ] [GREEN] Implement `domain/value_objects/state_transition.py` — frozen dataclass
- [ ] [GREEN] Implement `domain/value_objects/ownership_record.py` — frozen dataclass
- [ ] [REFACTOR] Ensure all value objects are immutable and have no external deps

### 1.2 State Machine

- [ ] [RED] Write tests for all 14 valid transitions (parametrized)
- [ ] [RED] Write tests for all invalid transitions in the rejection list (parametrized)
- [ ] [GREEN] Implement `domain/state_machine.py` — `VALID_TRANSITIONS` frozenset + `is_valid_transition()`
- [ ] [REFACTOR] Verify 100% branch coverage on state machine

### 1.3 WorkItem Entity

- [ ] [RED] Write tests: creation with valid fields sets correct defaults
- [ ] [RED] Write tests: title length validation (2 chars → fail, 3 chars → pass, 255 chars → pass, 256 chars → fail)
- [ ] [RED] Write tests: `can_transition_to` delegates to state machine + enforces owner check
- [ ] [RED] Write tests: `apply_transition` returns correct `StateTransition` value object
- [ ] [RED] Write tests: `force_ready` sets `has_override=True`, stores justification
- [ ] [RED] Write tests: `reassign_owner` returns correct `OwnershipRecord`
- [ ] [RED] Write tests: `compute_completeness` — 6 parametrized cases covering score ranges
- [ ] [RED] Write tests: `derived_state` property — all 5 conditions
- [ ] [GREEN] Implement `domain/models/work_item.py` — `WorkItem` entity with all fields and methods
- [ ] [REFACTOR] Ensure entity has zero infrastructure dependencies

### 1.4 Domain Exceptions

- [ ] [GREEN] Implement `domain/exceptions.py`:
  - `InvalidTransitionError(from_state, to_state)`
  - `NotOwnerError(actor_id, item_id)`
  - `MandatoryValidationsPendingError(item_id, validation_ids)`
  - `OwnerSuspendedError(owner_id)`
  - `TargetUserNotInWorkspaceError(user_id)`
  - `WorkItemNotFoundError(item_id)`
  - `CannotDeleteNonDraftError(item_id, state)`

---

## Phase 2: Infrastructure — Persistence

### 2.1 Database Migration

- [ ] Write Alembic migration: `create_work_items_table`
  - All columns per schema in design.md
  - CHECK constraints for type and state enums
  - CHECK constraint for title length
  - CHECK constraint for completeness_score range
- [ ] Write Alembic migration: `create_state_transitions_table`
- [ ] Write Alembic migration: `create_ownership_history_table`
- [ ] Write indexes (per design.md)
- [ ] Run migrations in dev environment; verify schema with `psql \d`

### 2.2 ORM Models (SQLAlchemy)

- [ ] Implement `infrastructure/persistence/models/work_item_orm.py` — SQLAlchemy `WorkItemORM` mapped class
- [ ] Implement `infrastructure/persistence/models/state_transition_orm.py`
- [ ] Implement `infrastructure/persistence/models/ownership_history_orm.py`

### 2.3 Mappers

- [ ] [RED] Write mapper unit tests: domain → ORM and ORM → domain round-trip
- [ ] [GREEN] Implement `infrastructure/persistence/mappers/work_item_mapper.py`

### 2.4 Repository Interface

- [ ] Implement `domain/repositories/work_item_repository.py` — abstract interface:
  - `async get(item_id) -> WorkItem | None`
  - `async list(project_id, filters) -> Page[WorkItem]`
  - `async save(item: WorkItem) -> WorkItem`
  - `async delete(item_id) -> None`
  - `async record_transition(transition: StateTransition) -> None`
  - `async record_ownership_change(record: OwnershipRecord) -> None`
  - `async get_transitions(item_id) -> list[StateTransition]`
  - `async get_ownership_history(item_id) -> list[OwnershipRecord]`

### 2.5 Repository Implementation

- [ ] [RED] Write integration tests for repository against test DB (use pytest-asyncio + real PostgreSQL)
  - Test: save and get round-trip
  - Test: list with state filter
  - Test: soft delete filters from list
  - Test: record_transition inserts audit row
  - Test: record_ownership_change inserts audit row
- [ ] [GREEN] Implement `infrastructure/persistence/repositories/work_item_repository_impl.py`
- [ ] [REFACTOR] Verify no N+1 queries; use single query with joins for list+owner data if needed

---

## Phase 3: Application Layer

### 3.1 Commands and Queries (input DTOs)

- [ ] Implement `application/commands/create_work_item_command.py`
- [ ] Implement `application/commands/update_work_item_command.py`
- [ ] Implement `application/commands/transition_state_command.py`
- [ ] Implement `application/commands/force_ready_command.py`
- [ ] Implement `application/commands/reassign_owner_command.py`
- [ ] Implement `application/queries/work_item_filters.py`

### 3.2 WorkItemService

- [ ] [RED] Write service unit tests using fake repository:
  - Test: create — defaults owner to creator when not provided
  - Test: create — rejects suspended owner
  - Test: transition — valid edge succeeds and emits event
  - Test: transition — invalid edge raises `InvalidTransitionError`
  - Test: transition — non-owner raises `NotOwnerError`
  - Test: transition to ready — pending mandatory validations raises `MandatoryValidationsPendingError`
  - Test: transition to ready — no pending validations succeeds
  - Test: force_ready — missing justification raises validation error
  - Test: force_ready — missing confirmed flag raises `CONFIRMATION_REQUIRED`
  - Test: force_ready — sets `has_override=True` and stores justification
  - Test: force_ready — non-owner raises `NotOwnerError`
  - Test: reassign — owner can reassign
  - Test: reassign — admin can reassign
  - Test: reassign — non-owner raises `NotOwnerError` (unless admin)
  - Test: reassign — suspended target raises error
  - Test: delete — non-draft raises `CannotDeleteNonDraftError`
  - Test: content update on ready item emits `work_item.content_changed_after_ready`
  - Test: substantial change auto-reverts ready to in_clarification
- [ ] [GREEN] Implement `application/services/work_item_service.py`
- [ ] [REFACTOR] Extract completeness computation into `domain/services/completeness_service.py`

### 3.3 Event Bus

- [ ] Implement `application/events/event_bus.py` — in-process sync bus for domain events
- [ ] Implement event dataclasses for all 8 events listed in design.md

---

## Phase 4: Presentation Layer

### 4.1 Pydantic Schemas

- [ ] Implement `presentation/schemas/work_item_schemas.py`:
  - `WorkItemCreateRequest`
  - `WorkItemUpdateRequest`
  - `WorkItemResponse` (includes `derived_state`, `completeness_score`, `next_step`, `override_info`)
  - `TransitionRequest`
  - `ForceReadyRequest`
  - `ReassignOwnerRequest`
  - `PagedWorkItemResponse`

### 4.2 Controllers

- [ ] [RED] Write controller unit tests with service fakes:
  - Test: POST /work-items — 201 on valid input
  - Test: POST /work-items — 422 on missing title
  - Test: GET /work-items/{id} — 404 when not found
  - Test: GET /work-items/{id} — 403 when no project access
  - Test: PATCH /work-items/{id} — 422 when state field included in body
  - Test: DELETE /work-items/{id} — 422 when state is not draft
  - Test: POST /work-items/{id}/transitions — 422 with INVALID_TRANSITION
  - Test: POST /work-items/{id}/force-ready — 403 for non-owner
  - Test: POST /work-items/{id}/force-ready — 422 for missing justification
  - Test: PATCH /work-items/{id}/owner — 403 for non-owner non-admin
- [ ] [GREEN] Implement `presentation/controllers/work_item_controller.py` — FastAPI router
- [ ] [REFACTOR] Verify error mapping: domain exceptions → HTTP response codes via global error middleware

### 4.3 Error Middleware

- [ ] Add `InvalidTransitionError` → 422 mapping to global error handler
- [ ] Add `NotOwnerError` → 403 mapping
- [ ] Add `MandatoryValidationsPendingError` → 422 mapping with details
- [ ] Add `OwnerSuspendedError` → 422 mapping
- [ ] Add `WorkItemNotFoundError` → 404 mapping

---

## Phase 5: Integration Tests

- [ ] [RED] Write end-to-end API integration tests (real DB, real FastAPI test client):
  - Full lifecycle: create → in_clarification → in_review → ready → exported
  - Override path: create → ready with pending validations → force-ready → verify audit record
  - Ownership: create → reassign → verify ownership_history row
  - Invalid transition returns structured error
  - Suspended owner flag: set flag → attempt owner-only transition → 422
  - Soft delete: draft → delete → list returns 0 items
- [ ] Run full test suite; verify all pass

---

## Phase 6: Observability and Cleanup

- [ ] Add structured logging in `WorkItemService` for all state transitions (info level)
- [ ] Add structured logging for override events (warn level with justification)
- [ ] Add structured logging for suspended-owner blocks (warn level)
- [ ] Verify no secrets in log output
- [ ] Run `mypy --strict` on all EP-01 modules; fix all type errors
- [ ] Run `ruff check` and `ruff format`; fix all issues

---

## Definition of Done

- [ ] All tests pass (unit + integration)
- [ ] `mypy --strict` clean
- [ ] `ruff` clean
- [ ] Migrations run cleanly on fresh DB and roll back cleanly
- [ ] All 10 API endpoints respond correctly to happy path and documented error cases
- [ ] `state_transitions` table has rows for every state change in integration test run
- [ ] `ownership_history` table has rows for every reassignment in integration test run
- [ ] `has_override = true` items are filterable via list endpoint
- [ ] `code-reviewer` agent review completed
- [ ] `review-before-push` workflow completed

**Status: NOT STARTED**
