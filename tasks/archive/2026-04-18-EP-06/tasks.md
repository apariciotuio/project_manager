# EP-06 Implementation Checklist

All steps follow RED → GREEN → REFACTOR. Write failing test first. No exceptions.

---

## Phase 1 — Domain & DB Foundation

### 1.1 Migrations

- [ ] **[RED]** Write migration test: verify `review_requests` table exists with all columns and constraints
- [ ] **[GREEN]** Create Alembic migration: `review_requests` table with indexes
- [ ] **[RED]** Write migration test: verify `review_responses` table with UNIQUE constraint on `review_request_id`
- [ ] **[GREEN]** Create Alembic migration: `review_responses` table
- [ ] **[RED]** Write migration test: verify `validation_requirements` table and seed data integrity
- [ ] **[GREEN]** Create Alembic migration: `validation_requirements` table + seed initial rules
- [ ] **[RED]** Write migration test: verify `validation_statuses` table with UNIQUE constraint on `(work_item_id, rule_id)`
- [ ] **[GREEN]** Create Alembic migration: `validation_statuses` table with indexes
- [ ] **[RED]** Write migration test: verify override columns added to `work_items`
- [ ] **[GREEN]** Create Alembic migration: add `has_override`, `override_justification`, `override_by`, `override_at` to `work_items`
- [ ] **[REFACTOR]** Review all migrations for index coverage and constraint correctness

### 1.2 Domain Entities

- [ ] **[RED]** Test `ReviewRequest` entity: construction, invalid reviewer_type raises, missing target raises
- [ ] **[GREEN]** Implement `domain/models/review_request.py` — `ReviewRequest` entity with invariant checks
- [ ] **[RED]** Test `ReviewResponse` entity: decision validation, content required for non-approved decisions
- [ ] **[GREEN]** Implement `domain/models/review_response.py` — `ReviewResponse` entity
- [ ] **[RED]** Test `ValidationStatus` entity: status transitions (pending→passed, pending→waived, passed does not regress)
- [ ] **[GREEN]** Implement `domain/models/validation_status.py` — `ValidationStatus` entity
- [ ] **[REFACTOR]** Extract shared enums (`ReviewDecision`, `ReviewStatus`, `ValidationStatusEnum`) to `domain/models/enums.py`

---

## Phase 2 — Repositories

- [ ] **[RED]** Test `ReviewRequestRepository`: create, find_by_id, find_by_work_item, find_pending_by_reviewer, find_pending_by_team
- [ ] **[GREEN]** Implement `infrastructure/persistence/review_request_repository.py`
- [ ] **[RED]** Test `ReviewResponseRepository`: create, find_by_review_request_id, duplicate raises on existing
- [ ] **[GREEN]** Implement `infrastructure/persistence/review_response_repository.py`
- [ ] **[RED]** Test `ValidationStatusRepository`: create, find_by_work_item, find_required_pending, upsert on recalculation
- [ ] **[GREEN]** Implement `infrastructure/persistence/validation_status_repository.py`
- [ ] **[REFACTOR]** Ensure all repos inject async session; no direct DB access outside infra layer

---

## Phase 3 — Application Services

### 3.1 ReviewRequestService (US-060, US-063)

- [ ] **[RED]** Test create review request: happy path user reviewer → pins version_id, status=pending, triggers notification
- [ ] **[RED]** Test create review request: team reviewer → pins version_id, triggers fan-out
- [ ] **[RED]** Test create review request: non-owner → raises AuthorizationError
- [ ] **[RED]** Test cancel review request: owner → status=cancelled, notification dispatched
- [ ] **[RED]** Test cancel review request: non-owner → raises AuthorizationError
- [ ] **[RED]** Test cancel review request: already closed → raises ConflictError
- [ ] **[GREEN]** Implement `application/services/review_request_service.py`
- [ ] **[REFACTOR]** Extract version-pinning to a dedicated `VersionPinService` or util if reused

### 3.2 ReviewResponseService (US-061)

- [ ] **[RED]** Test submit response: approved by assigned user → closes request, triggers ValidationService.on_review_closed
- [ ] **[RED]** Test submit response: rejected → closes request, work item → Changes Requested, content required
- [ ] **[RED]** Test submit response: changes_requested → closes request, work item → Changes Requested, content required
- [ ] **[RED]** Test submit response: non-assigned user → raises AuthorizationError
- [ ] **[RED]** Test submit response: team review → member of team may respond, responder_id recorded
- [ ] **[RED]** Test submit response: already closed request → raises ConflictError
- [ ] **[RED]** Test submit response: approved without content → succeeds (content optional on approve)
- [ ] **[RED]** Test submit response: rejected without content → raises ValidationError
- [ ] **[GREEN]** Implement `application/services/review_response_service.py`
- [ ] **[REFACTOR]** Ensure FSM transition calls route through EP-01 `WorkItemFSMService`, not direct field update

### 3.3 ValidationService (US-062)

- [ ] **[RED]** Test get_checklist: returns all applicable rules with statuses for work item type
- [ ] **[RED]** Test on_review_closed: approved + linked rule_id → status transitions to passed, passed_by recorded
- [ ] **[RED]** Test on_review_closed: rejected + linked rule_id → status stays pending
- [ ] **[RED]** Test on_review_closed: no linked rule_id → no-op
- [ ] **[RED]** Test on_review_closed: already passed status → idempotent (no regression)
- [ ] **[RED]** Test waive_validation: recommended rule → status=waived, waive fields recorded
- [ ] **[RED]** Test waive_validation: required rule → raises ValidationError (not allowed outside override)
- [ ] **[RED]** Test recalculate_on_version_change: new rules added as pending, obsolete marked, passed rules preserved
- [ ] **[GREEN]** Implement `application/services/validation_service.py`
- [ ] **[REFACTOR]** on_review_closed should be transactional with the response commit (same unit of work)

### 3.4 ReadyGateService (US-064)

- [ ] **[RED]** Test check: all required passed → GateResult(passed=True, blocking=[])
- [ ] **[RED]** Test check: one required pending → GateResult(passed=False, blocking=[rule_id])
- [ ] **[RED]** Test check: only recommended pending → GateResult(passed=True) (recommended does not block)
- [ ] **[RED]** Test check: waived recommended → GateResult(passed=True)
- [ ] **[GREEN]** Implement `application/services/ready_gate_service.py`

### 3.5 WorkItemTransitionService — Ready and Override (US-064)

- [ ] **[RED]** Test transition_to_ready: gate passed → work_item.state=Ready, has_override=false
- [ ] **[RED]** Test transition_to_ready: gate blocked → raises ReadyGateBlockedError with blocking rules
- [ ] **[RED]** Test override_to_ready: valid justification + confirmed → state=Ready, has_override=true, audit event written
- [ ] **[RED]** Test override_to_ready: empty justification → raises ValidationError
- [ ] **[RED]** Test override_to_ready: missing confirmation → raises ValidationError
- [ ] **[RED]** Test override_to_ready: non-owner → raises AuthorizationError
- [ ] **[RED]** Test override fields reset on subsequent version increment (via FSM event)
- [ ] **[GREEN]** Implement transition methods in `application/services/work_item_transition_service.py` (or extend EP-01 FSMService)
- [ ] **[REFACTOR]** Verify audit event includes list of blocking rules bypassed at override time

---

## Phase 4 — Notification Fan-out (US-060)

- [ ] **[RED]** Test fan-out Celery task: sends one notification per team member, idempotency key prevents duplicate on retry
- [ ] **[RED]** Test SSE notification dispatched to reviewer on new review request
- [ ] **[RED]** Test SSE notification dispatched to owner on review response received
- [ ] **[RED]** Test SSE notification dispatched to owner when all required validations pass
- [ ] **[GREEN]** Implement `infrastructure/tasks/review_notification_tasks.py` — Celery tasks for fan-out
- [ ] **[REFACTOR]** Reuse EP-08 notification infrastructure; do not duplicate SSE dispatch logic

---

## Phase 5 — API Layer (Controllers)

### 5.1 Review Request Endpoints

- [ ] **[RED]** Integration test: POST `/api/v1/work-items/{id}/review-requests` → 201, review request created
- [ ] **[RED]** Integration test: POST — non-owner → 403
- [ ] **[RED]** Integration test: GET `/api/v1/work-items/{id}/review-requests` → list with statuses
- [ ] **[RED]** Integration test: GET `/api/v1/review-requests/{id}` → includes `version_outdated` flag when versions differ
- [ ] **[RED]** Integration test: DELETE `/api/v1/review-requests/{id}` (cancel) → 200, status=cancelled
- [ ] **[GREEN]** Implement `presentation/controllers/review_request_controller.py`

### 5.2 Review Response Endpoints

- [ ] **[RED]** Integration test: POST `.../response` approved → 200, request closed, validation updated
- [ ] **[RED]** Integration test: POST `.../response` rejected → 200, work item Changes Requested
- [ ] **[RED]** Integration test: POST `.../response` non-assigned user → 403
- [ ] **[RED]** Integration test: POST `.../response` on closed request → 409
- [ ] **[GREEN]** Implement `presentation/controllers/review_response_controller.py`

### 5.3 Validation Endpoints

- [ ] **[RED]** Integration test: GET `/api/v1/work-items/{id}/validations` → checklist with required/recommended split
- [ ] **[RED]** Integration test: POST `.../waive` recommended rule → 200, status=waived
- [ ] **[RED]** Integration test: POST `.../waive` required rule → 422
- [ ] **[GREEN]** Implement `presentation/controllers/validation_controller.py`

### 5.4 Ready Transition Endpoints

- [ ] **[RED]** Integration test: POST `.../transition/ready` all passed → 200, state=Ready
- [ ] **[RED]** Integration test: POST `.../transition/ready` pending required → 422 with blocking rules list
- [ ] **[RED]** Integration test: POST `.../transition/ready-override` valid → 200, has_override=true, audit recorded
- [ ] **[RED]** Integration test: POST `.../transition/ready-override` empty justification → 422
- [ ] **[RED]** Integration test: POST `.../transition/ready-override` non-owner → 403
- [ ] **[GREEN]** Implement ready transition routes in `presentation/controllers/work_item_controller.py` (extend EP-01 controller)

---

## Phase 6 — Integration & Edge Cases

- [ ] **[RED]** E2E test: full review round-trip — request → team fan-out → member responds approved → validation passes → Ready
- [ ] **[RED]** E2E test: iterative flow — request → reject → owner edits (new version) → re-request → approve → Ready
- [ ] **[RED]** E2E test: override flow — pending required validation → override with justification → audit event contains bypassed rules
- [ ] **[RED]** Test: outdated version detection — review requested on v2, item now at v4, GET returns version_outdated=true
- [ ] **[RED]** Test: multiple reviews satisfy same validation rule — second approve is idempotent on passed status
- [ ] **[GREEN]** Fix any integration failures
- [ ] **[REFACTOR]** Full pass: dead code, missing type hints, N+1 query check on checklist endpoint, error message consistency

---

## Phase 7 — Review Gates

- [ ] Run `code-reviewer` agent on all EP-06 changes
- [ ] Run `review-before-push` workflow
- [ ] Confirm all tests pass, lint clean, type checks pass

---

**Status: IN PROGRESS** (2026-04-13)
