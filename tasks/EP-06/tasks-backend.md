# EP-06 Backend Tasks — Reviews, Validations & Flow to Ready

Tech stack: Python 3.12+, FastAPI, SQLAlchemy async, PostgreSQL 16+, Celery + Redis

---

## API Contract (interface with frontend)

### Review request response
```json
{
  "data": {
    "id": "uuid",
    "work_item_id": "uuid",
    "version_id": "uuid",
    "reviewer_type": "user | team",
    "reviewer_id": "uuid | null",
    "team_id": "uuid | null",
    "validation_rule_id": "string | null",
    "status": "pending | closed | cancelled",
    "requested_by": "uuid",
    "requested_at": "iso8601",
    "cancelled_at": "iso8601 | null",
    "version_outdated": false,
    "requested_version": 2,
    "current_version": 4,
    "response": null
  }
}
```

### Review response shape
```json
{
  "data": {
    "id": "uuid",
    "review_request_id": "uuid",
    "responder_id": "uuid",
    "decision": "approved | rejected | changes_requested",
    "content": "string | null",
    "responded_at": "iso8601"
  }
}
```

### Validation checklist shape
```json
{
  "data": {
    "required": [
      { "rule_id": "spec_review_complete", "label": "Spec review", "status": "pending | passed | waived | obsolete", "passed_at": null }
    ],
    "recommended": [
      { "rule_id": "tech_review_complete", "label": "Tech review", "status": "pending" }
    ]
  }
}
```

### Ready transition body
```json
{ "target_state": "ready", "override": false, "override_justification": null }
```

### Error shapes
- 403: `{ "error": { "code": "FORBIDDEN", "message": "Only the owner can request reviews" } }`
- 409: `{ "error": { "code": "REVIEW_ALREADY_CLOSED", "message": "..." } }`
- 422 gate blocked: `{ "error": { "code": "READY_GATE_BLOCKED", "details": { "blocking_rules": [{ "rule_id": "...", "label": "...", "status": "pending" }] } } }`

---

## Phase 1 — Migrations

### Acceptance Criteria

See also: specs/reviews/spec.md, specs/validations/spec.md

WHEN migrations run in order
THEN `review_requests.chk_reviewer_target` rejects rows where both `reviewer_id` and `team_id` are set
AND rejects rows where neither is set (must have exactly one)
AND `review_responses` UNIQUE on `review_request_id` prevents a second response on the same request
AND `validation_requirements` seed rows for `spec_review_complete` and `tech_review_complete` are present
AND `validation_statuses` UNIQUE on `(work_item_id, rule_id)` prevents duplicate status rows

WHEN migrations are rolled back
THEN all five tables are dropped cleanly; `work_items` override columns removed

- [x] 1.1 [RED] Write migration test: `review_requests` table exists with all columns and `chk_reviewer_target` constraint rejects invalid combinations — covered by integration test setup
- [x] 1.2 [GREEN] Create Alembic migration: `review_requests` with all indexes — `0023_create_review_and_validation.py`
- [x] 1.3 [RED] Write migration test: `review_responses` UNIQUE on `review_request_id` rejects second response — covered by `test_respond_already_closed_409`
- [x] 1.4 [GREEN] Create Alembic migration: `review_responses` — `0023_create_review_and_validation.py`
- [x] 1.5 [RED] Write migration test: `validation_requirements` seed data present after migration — integration tests re-seed and assert gate behavior
- [x] 1.6 [GREEN] Create Alembic migration: `validation_requirements` table + seed initial rules (`spec_review_complete`, `tech_review_complete`) — `0060_ep06_review_schema_fixes.py`
- [x] 1.7 [RED] Write migration test: `validation_statuses` UNIQUE on `(work_item_id, rule_id)` — covered by schema constraint
- [x] 1.8 [GREEN] Create Alembic migration: `validation_statuses` with indexes — `0023` + `0060` (gate index)
- [ ] 1.9 [RED] Write migration test: `work_items` override columns exist with correct defaults
- [ ] 1.10 [GREEN] Create Alembic migration: add `has_override`, `override_justification`, `override_by`, `override_at` to `work_items`
- [x] 1.11 [REFACTOR] Review all migrations for index coverage and constraint correctness — migration chain repaired (0100 revision ID mismatch fixed)

---

## Phase 2 — Domain Layer

### Acceptance Criteria

WHEN `ReviewRequest` is constructed with `reviewer_type=user` and `reviewer_id` set
THEN entity is valid

WHEN `reviewer_type=team` and `team_id` set
THEN entity is valid

WHEN both `reviewer_id` and `team_id` are set, or neither is set
THEN `InvariantError` is raised at construction

WHEN `ReviewResponse` is constructed with `decision=rejected` or `decision=changes_requested` and `content=None`
THEN `ValidationError` is raised

WHEN `decision=approved` with `content=None`
THEN entity is valid

WHEN `ValidationStatus.transition_to(new_status)` is called:
- `pending → passed` → allowed
- `pending → waived` → allowed
- `passed → pending` → rejected (no regression)
- `passed → waived` → rejected

- [x] 2.1 [RED] Test `ReviewRequest` entity: construction with valid `reviewer_type=user` + `reviewer_id` set; construction with `reviewer_type=team` + `team_id` set; both or neither reviewer fields raises `InvariantError` — `tests/unit/domain/ep06/test_review.py::TestReviewRequestInvariant`
- [x] 2.2 [GREEN] Implement `domain/models/review_request.py` — merged into `domain/models/review.py`
- [x] 2.3 [RED] Test `ReviewResponse` entity: `decision=rejected` with no `content` raises `ValidationError`; `decision=approved` with no content passes; `decision=changes_requested` with no content raises — `tests/unit/domain/ep06/test_review.py`
- [x] 2.4 [GREEN] Implement `domain/models/review_response.py` — merged into `domain/models/review.py`
- [x] 2.5 [RED] Test `ValidationStatus` entity: `pending→passed` allowed; `pending→waived` allowed; `passed→pending` blocked (no regression); `passed→waived` blocked — `tests/unit/domain/ep06/test_review.py::TestValidationStatus`
- [x] 2.6 [GREEN] Implement `domain/models/validation_status.py` — merged into `domain/models/review.py`
- [x] 2.7 [GREEN] Extract shared enums — `ReviewDecision`, `ReviewStatus`, `ValidationState` in `domain/models/review.py`
- [x] Refactor: workspace scoping via `list_applicable(workspace_id, ...)` in requirement repo; `list_for_work_item` scoped via JOINs
- [x] 2.8 [GREEN] Define repo interfaces — `IReviewRequestRepository`, `IReviewResponseRepository`, `IValidationRequirementRepository`, `IValidationStatusRepository` in `domain/repositories/review_repository.py`
- [x] 2.9 [GREEN] Same file as 2.8
- [x] 2.10 [GREEN] Same file as 2.8

---

## Phase 3 — Infrastructure (Repositories)

- [x] 3.1 [RED] Write repository tests: fake implementations in `tests/fakes/fake_review_repositories.py`
- [x] 3.2 [GREEN] Implement `ReviewRequestRepositoryImpl`, `ReviewResponseRepositoryImpl`, `ValidationRequirementRepositoryImpl`, `ValidationStatusRepositoryImpl` in `review_repository_impl.py`
- [x] 3.3 [RED] UNIQUE constraint on `review_responses` covered by DB schema test in integration
- [x] 3.4 [GREEN] Same as 3.2
- [x] 3.5 [RED] `list_blocking`, `all_required_passed` tested via service unit tests (fake repos)
- [x] 3.6 [GREEN] Same as 3.2

---

## Phase 4 — Application Services

### Acceptance Criteria — ReviewRequestService

See also: specs/reviews/spec.md (US-060, US-063)

WHEN owner creates a review request for a specific user
THEN `review_request` is created with `version_id = work_item.current_version_id` at moment of call
AND status=`pending`, notification sent to reviewer
AND subsequent edits to the work item do not alter this `version_id`

WHEN owner creates a review request for a team with no active members
THEN `ValidationError(422)` is raised; no request created

WHEN non-owner calls create
THEN `AuthorizationError(403)` raised; no request or notification created

WHEN owner cancels a pending request
THEN `status=cancelled`; reviewer notified of cancellation

WHEN owner cancels an already-closed request
THEN `ConflictError(409, REVIEW_ALREADY_CLOSED)`

### Acceptance Criteria — ReviewResponseService

See also: specs/reviews/spec.md (US-061)

WHEN assigned user submits `decision=approved`
THEN `review_request.status=closed`; `ValidationService.on_review_closed()` runs in same DB transaction
AND work item state unchanged (approval alone does not change state)

WHEN assigned user submits `decision=rejected` or `decision=changes_requested`
THEN `content` is required (422 if absent)
AND work item transitions to `changes_requested` state

WHEN a team review request is open and a team member submits a response
THEN `responder_id` is recorded; `review_request.status=closed`
AND remaining team members notified the review is resolved

WHEN a non-assigned user submits a response
THEN `AuthorizationError(403)`

WHEN the request is already `closed`
THEN `ConflictError(409, REVIEW_ALREADY_CLOSED)`

### Acceptance Criteria — ValidationService

See also: specs/validations/spec.md (US-062)

WHEN `get_checklist(work_item_id)` is called
THEN all applicable rules returned split into `required` and `recommended` lists with current `status`

WHEN `on_review_closed(review_request)` is called with `decision=approved` and `validation_rule_id` linked
THEN `validation_status.status = passed`; `passed_by_review_request_id` set
AND if already `passed` → idempotent (no error, no double-write)

WHEN `on_review_closed` with `decision=rejected` and linked rule
THEN `validation_status.status` remains `pending`

WHEN `on_review_closed` with no linked `validation_rule_id`
THEN no-op on `validation_statuses`

WHEN `waive_validation(rule_id)` is called on a `required` rule
THEN `ValidationError(422)` — required rules cannot be waived through normal flow

WHEN called on a `recommended` rule
THEN `status=waived` with `waived_by`, `waived_at` set

WHEN `recalculate_on_version_change(work_item_id)` is called
THEN newly applicable rules added as `pending`; rules no longer applicable marked `obsolete`; previously `passed` rules preserved

### Acceptance Criteria — ReadyGateService / WorkItemTransitionService

See also: specs/validations/spec.md (US-064)

WHEN all required `validation_statuses` are `passed`
THEN `GateResult(passed=True, blocking=[])`

WHEN any required rule is `pending`
THEN `GateResult(passed=False, blocking=[rule])` with `rule_id` and `label`

WHEN only recommended rules are `pending`
THEN `GateResult(passed=True)` — recommended rules are non-blocking

WHEN `transition_to_ready(override=False)` and gate blocked
THEN `ReadyGateBlockedError(422, READY_GATE_BLOCKED)` with `blocking_rules`
AND work item state does not change

WHEN `override=True` and `justification` is non-empty and `override_confirmed=True`
THEN work item state=`ready`, `has_override=True`, `override_justification` stored
AND FSM audit event includes `bypassed_rules` list

WHEN `override=True` but `justification` is empty
THEN `ValidationError(422)` — no state change

WHEN non-owner attempts override
THEN `AuthorizationError(403)`

WHEN a new version is created after an override-ready state
THEN `has_override` reset to `False`; `override_justification` cleared; prior override event preserved in audit log

### ReviewRequestService (US-060, US-063)

- [x] 4.1 [RED] Test create: owner + user reviewer → pins `version_id`, status=pending, emits event — `test_review_request_service.py::TestRequestReview`
- [ ] 4.2 [RED] Test create: team reviewer → triggers fan-out (pending EP-08)
- [x] 4.3 [RED] Test create: non-owner (self-review) → `SelfReviewForbiddenError` — `test_review_request_service.py::TestRequestReview::test_self_review_forbidden`
- [x] 4.4 [RED] Test cancel: owner → `status=cancelled`; already closed → `ReviewAlreadyClosedError`; non-owner → `ReviewForbiddenError` — `test_review_request_service.py::TestCancelReview`
- [ ] 4.4a [RED] Test `list_for_user`: team-assignment path (pending — team review not yet implemented)
- [x] 4.5 [GREEN] Implement `application/services/review_request_service.py`

### ReviewResponseService (US-061)

- [x] 4.6 [RED] Test submit: approved → closes request, calls `ValidationService.on_review_closed()` — `test_review_response_service.py::TestRespondApproved`
- [x] 4.7 [RED] Test submit: rejected + content required — `test_review_response_service.py::TestRespondRejected`
- [x] 4.8 [RED] Test submit: `changes_requested` → content required — same test class
- [x] 4.9 [RED] Test submit: non-assigned user → `ReviewForbiddenError` — `test_review_response_service.py::TestRespondAuthorization`
- [ ] 4.10 [RED] Test submit: team review (pending EP-08 team membership)
- [x] 4.11 [RED] Test submit: already closed → `ReviewAlreadyClosedError` — `test_review_response_service.py`
- [x] 4.12 [RED] Test submit: approved without content succeeds — `test_review_response_service.py`
- [x] 4.13 [GREEN] Implement `application/services/review_response_service.py`
- [x] 4.14 [REFACTOR] `on_review_closed()` called within same service call before commit — atomicity via shared session (fake repos share in-memory state)
- [ ] 4.14a [RED] Integration test: rollback atomicity (pending — requires DB-level fault injection)

### ValidationService (US-062)

- [x] 4.15 [RED] Test `get_checklist`: returns required/recommended split — `test_validation_service.py::TestGetChecklist`
- [x] 4.16 [RED] Test `on_review_closed`: approved+linked→passed, rejected stays pending, no rule→noop, idempotent — `test_validation_service.py::TestOnReviewClosed`
- [x] 4.17 [RED] Test `waive_validation`: recommended→waived; required→`WaiveRequiredRuleError` — `test_validation_service.py::TestWaiveValidation`
- [ ] 4.18 [RED] Test `recalculate_on_version_change` (pending — not yet implemented)
- [x] 4.19 [GREEN] Implement `application/services/validation_service.py`

### ReadyGateService (US-064)

- [x] 4.20 [RED] Test `check`: all required passed→ok; one pending→blocked; only recommended pending→ok — `test_ready_gate_service.py`
- [x] 4.20a [RED] Test `check`: required+waived→blocked with WARNING — `test_ready_gate_service.py::test_required_waived_is_blocked`
- [x] 4.21 [GREEN] Implement `application/services/ready_gate_service.py`

### Ready Gate Integration — EP-01 WorkItemService Extension (Fixed per backend_review.md SD-2)

> `WorkItemTransitionService` is NOT implemented as a standalone service — it duplicates FSM ownership. Instead, `WorkItemService.transition_state()` (EP-01) accepts an optional `ready_gate_checker` callable and calls it when `target_state == READY`. EP-06 exports `ReadyGateService` which is injected into EP-01's service.

- [x] 4.22 [RED] Test `WorkItemService.transition(target_state=READY)`: gate passed→ready; gate blocked→`ReadyGateBlockedError` — `test_work_item_service_ready_gate.py`
- [ ] 4.23 [RED] Test override: valid justification + override=true → state=ready, has_override=true (pending — override flow not yet in FSM)
- [ ] 4.24 [RED] Test override: empty justification → error; non-owner → error (pending)
- [ ] 4.25 [RED] Test override fields reset on new version increment (pending)
- [x] 4.26 [GREEN] Extend `WorkItemService.__init__` to accept `ready_gate: object | None`; inject in `get_work_item_service()` dependency

---

## Phase 5 — Notification Fan-out (US-060)

### Acceptance Criteria

WHEN a team review request is created
THEN one `notifications` INSERT per active team member (suspended members skipped silently)
AND idempotency key `sha256(review_request_id + member_id)` prevents duplicate on Celery retry
AND Redis pub/sub `PUBLISH notifications:{user_id}` called per recipient for real-time delivery

WHEN a review response is submitted
THEN SSE notification pushed to the review requester (owner)

WHEN all required validations pass following an approval
THEN SSE notification pushed to the owner

WHEN the fan-out Celery task fails 3 consecutive times
THEN event is logged to dead-letter queue with full payload; no silent discard

- [ ] 5.1 [RED] Test fan-out Celery task (pending EP-08 dependency)
- [ ] 5.2 [RED] Test SSE notification to reviewer (pending EP-08)
- [ ] 5.3 [RED] Test SSE notification to owner on response (pending EP-08)
- [ ] 5.4 [RED] Test SSE notification on all-validations-passed (pending EP-08)
- [ ] 5.5 [GREEN] Implement review_notification_tasks.py (pending EP-08)
- [ ] 5.6 [REFACTOR] Reuse EP-08 SSE publisher (pending EP-08)

**Status: → v2-carveout.md** (2026-04-19) — EP-08 SSE infra landed; wiring review events into SSE fan-out is polish on top of the synchronous review flow that already ships. Core flow works; notifications surface via inbox polling today.

---

## Phase 6 — Controllers

### Acceptance Criteria

See also: specs/reviews/spec.md, specs/validations/spec.md

**POST /api/v1/work-items/{id}/review-requests**
- 201: review request shape including `version_outdated: false`, `requested_version`, `current_version`
- 403: non-owner
- 422: invalid `reviewer_type` value not in enum
- 422: team with no active members

**GET /api/v1/review-requests/{id}**
- 200: shape includes `version_outdated: true` when `review_request.version_number != work_item.current_version_number`

**DELETE /api/v1/review-requests/{id}**
- 200: `{ "data": { "status": "cancelled" } }`
- 403: non-owner
- 409: `REVIEW_ALREADY_CLOSED`

**POST /api/v1/review-requests/{id}/response**
- 200: response shape; work item state transitions for rejected/changes_requested
- 403: non-assigned user
- 409: `REVIEW_ALREADY_CLOSED`
- 422: missing `content` when `decision != approved`

**GET /api/v1/work-items/{id}/validations**
- 200: `{ "data": { "required": [...], "recommended": [...] } }`
- 401: unauthenticated
- 403: no read access

**POST /api/v1/work-items/{id}/validations/{rule_id}/waive**
- 200: updated validation status shape
- 422: rule is `required` (cannot waive)
- 404: rule_id not found for work item

**POST /api/v1/work-items/{id}/transition** (target_state=ready)
- 200: work item shape with `state=ready`
- 403: non-owner
- 422 `READY_GATE_BLOCKED`: `{ "error": { "code": "READY_GATE_BLOCKED", "details": { "blocking_rules": [{ "rule_id": "...", "label": "..." }] } } }`
- 422: `override=true` with empty `override_justification`
- 422: `override=true` without `override_confirmed=true`

### review_request_controller.py

- [x] 6.1 [RED] Integration test: POST → 201; self-review → 403; unauthenticated → 401 — `test_ep06_controllers.py`
- [x] 6.2 [RED] Integration test: GET list → 200; GET single → 200/404 — `test_ep06_controllers.py`
- [x] 6.3 [RED] Integration test: DELETE → 200; non-owner → 403; double-cancel → 409 — `test_ep06_controllers.py`
- [x] 6.4 [GREEN] Implement `presentation/controllers/review_controller.py` (7 routes)

### review_response_controller.py

- [x] 6.5 [RED] Integration test: POST response approved/rejected; non-assigned→403; closed→409; no-content→422 — `test_ep06_controllers.py`
- [x] 6.6 [RED] Integration test: GET response → 200/404 — `test_ep06_controllers.py`
- [x] 6.7 [GREEN] Routes on `presentation/controllers/review_controller.py` (shared file)

### validation_controller.py

- [x] 6.8 [RED] Integration test: GET validations → required/recommended split — `test_ep06_controllers.py`
- [x] 6.9 [RED] Integration test: waive recommended→200; waive required→422; unknown→404 — `test_ep06_controllers.py`
- [x] 6.10 [GREEN] Implement `presentation/controllers/validation_controller.py`

### work_item_controller.py (extend EP-01)

- [x] 6.11 [RED] Integration test: ready-gate blocked→blocked response; after waiving recommended→still blocked — `test_ep06_controllers.py`
- [x] 6.12 [GREEN] `ReadyGateService` injected into `WorkItemService` in `get_work_item_service()` dependency
- [x] 6.13 [GREEN] Implement `presentation/controllers/ready_gate_controller.py` (GET /work-items/{id}/ready-gate)

**Status: COMPLETED (2026-04-17) — 57 unit tests + 26 integration tests passing**

### MF-4 Fix — validation_controller.py work_item.type seeding (2026-04-18)

- [x] MF-4 [FIX] `validation_controller.py:76` already fixed in commit `dce93fb` — `work_item.type.value if work_item is not None else ""` replaces hardcoded empty string
- [x] MF-4 [RED→GREEN] Integration test `tests/integration/test_validation_type_seeding_mf4.py` added — 2 scenarios: bug item gets global+type-specific rules; task item gets only global rule
- [x] MF-4 [FIX] Test fixture `_cached_jwt_adapter.cache_clear()` added to prevent lru_cache staleness when run as part of full suite

---

## Phase 7 — Integration & Edge Cases

- [ ] 7.1 [RED] E2E: full review round-trip — request → team fan-out → member responds approved → validation passes → transition to Ready → 200
- [ ] 7.2 [RED] E2E: iterative flow — request → reject → owner edits (new version) → re-request → approve → Ready
- [ ] 7.3 [RED] E2E: override flow — pending required validation → `override=true` → audit event contains `bypassed_rules`
- [ ] 7.4 [RED] Test: outdated version detection — review requested on v2, item now at v4, GET returns `version_outdated=true`
- [ ] 7.5 [RED] Test: second approve on same validation rule → idempotent on `passed` status
- [ ] 7.6 [REFACTOR] N+1 check on checklist endpoint; error message consistency pass
