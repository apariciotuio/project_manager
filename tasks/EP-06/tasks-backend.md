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

- [ ] 1.1 [RED] Write migration test: `review_requests` table exists with all columns and `chk_reviewer_target` constraint rejects invalid combinations
- [ ] 1.2 [GREEN] Create Alembic migration: `review_requests` with all indexes
- [ ] 1.3 [RED] Write migration test: `review_responses` UNIQUE on `review_request_id` rejects second response
- [ ] 1.4 [GREEN] Create Alembic migration: `review_responses`
- [ ] 1.5 [RED] Write migration test: `validation_requirements` seed data present after migration
- [ ] 1.6 [GREEN] Create Alembic migration: `validation_requirements` table + seed initial rules (`spec_review_complete`, `tech_review_complete`)
- [ ] 1.7 [RED] Write migration test: `validation_statuses` UNIQUE on `(work_item_id, rule_id)`
- [ ] 1.8 [GREEN] Create Alembic migration: `validation_statuses` with indexes
- [ ] 1.9 [RED] Write migration test: `work_items` override columns exist with correct defaults
- [ ] 1.10 [GREEN] Create Alembic migration: add `has_override`, `override_justification`, `override_by`, `override_at` to `work_items`
- [ ] 1.11 [REFACTOR] Review all migrations for index coverage and constraint correctness

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

- [ ] 2.1 [RED] Test `ReviewRequest` entity: construction with valid `reviewer_type=user` + `reviewer_id` set; construction with `reviewer_type=team` + `team_id` set; both or neither reviewer fields raises `InvariantError`
- [ ] 2.2 [GREEN] Implement `domain/models/review_request.py`
- [ ] 2.3 [RED] Test `ReviewResponse` entity: `decision=rejected` with no `content` raises `ValidationError`; `decision=approved` with no content passes; `decision=changes_requested` with no content raises
- [ ] 2.4 [GREEN] Implement `domain/models/review_response.py`
- [ ] 2.5 [RED] Test `ValidationStatus` entity: `pending→passed` allowed; `pending→waived` allowed; `passed→pending` blocked (no regression); `passed→waived` blocked
- [ ] 2.6 [GREEN] Implement `domain/models/validation_status.py`
- [ ] 2.7 [GREEN] Extract shared enums to `domain/models/enums.py`: `ReviewDecision`, `ReviewStatus`, `ValidationStatusEnum`
- [ ] Refactor: all repository methods must accept `workspace_id` as a required parameter — `find_by_id(id, workspace_id)`, `find_by_work_item(work_item_id, workspace_id)`, etc. Queries must include `WHERE workspace_id = :workspace_id`. Return `None` (not 403) on workspace mismatch to avoid existence disclosure (CRIT-2).
- [ ] 2.8 [GREEN] Define `domain/repositories/review_request_repository.py` interface
- [ ] 2.9 [GREEN] Define `domain/repositories/review_response_repository.py` interface
- [ ] 2.10 [GREEN] Define `domain/repositories/validation_status_repository.py` interface

---

## Phase 3 — Infrastructure (Repositories)

- [ ] 3.1 [RED] Write repository tests: `ReviewRequestRepository` — create, `find_by_id`, `find_by_work_item`, `find_pending_by_reviewer`, `find_pending_by_team`
- [ ] 3.2 [GREEN] Implement `infrastructure/persistence/review_request_repository.py`
- [ ] 3.3 [RED] Write repository tests: `ReviewResponseRepository` — create, `find_by_review_request_id`; second create for same request raises DB unique violation
- [ ] 3.4 [GREEN] Implement `infrastructure/persistence/review_response_repository.py`
- [ ] 3.5 [RED] Write repository tests: `ValidationStatusRepository` — `find_by_work_item`, `find_required_pending`, upsert behavior
- [ ] 3.6 [GREEN] Implement `infrastructure/persistence/validation_status_repository.py`

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

- [ ] 4.1 [RED] Test create: owner + user reviewer → pins `version_id = work_item.current_version_id`, status=pending, triggers notification
- [ ] 4.2 [RED] Test create: team reviewer → triggers fan-out Celery task to all team members
- [ ] 4.3 [RED] Test create: non-owner → raises `AuthorizationError`
- [ ] 4.4 [RED] Test cancel: owner → `status=cancelled`; already closed → raises `ConflictError`; non-owner → raises `AuthorizationError`
- [ ] 4.4a [RED] Test `list_for_user(user_id)`: returns reviews where `reviewer_type='user' AND reviewer_id=user_id` UNION reviews where `reviewer_type='team' AND user_id IN team.members`; a team-assigned review appears in results for any team member, not only the direct reviewer
- [ ] 4.5 [GREEN] Implement `application/services/review_request_service.py` — `list_for_user` must cover both direct and team-assignment paths

### ReviewResponseService (US-061)

- [ ] 4.6 [RED] Test submit: assigned user + approved → closes request, calls `ValidationService.on_review_closed()`, work item state unchanged
- [ ] 4.7 [RED] Test submit: rejected → closes request, calls FSM transition to `changes_requested`, content required
- [ ] 4.8 [RED] Test submit: `changes_requested` → same as rejected path, content required
- [ ] 4.9 [RED] Test submit: non-assigned user → raises `AuthorizationError`
- [ ] 4.10 [RED] Test submit: team review → any current team member may respond, `responder_id` recorded
- [ ] 4.11 [RED] Test submit: already closed request → raises `ConflictError`
- [ ] 4.12 [RED] Test submit: approved without content → succeeds
- [ ] 4.13 [GREEN] Implement `application/services/review_response_service.py`
- [ ] 4.14 [REFACTOR] Ensure `ValidationService.on_review_closed()` runs in same DB transaction as response INSERT — `ReviewResponseService.submit()` must explicitly pass the active SQLAlchemy session to `ValidationService.on_review_closed()`, or both services must share the same unit of work. Using a separate session in `ValidationService` creates two independent transactions (Fixed per backend_review.md TC-3)
- [ ] 4.14a [RED] Integration test: WHEN DB error occurs between `review_responses` INSERT and `validation_statuses` UPDATE THEN neither operation is committed (rollback atomicity test)

### ValidationService (US-062)

- [ ] 4.15 [RED] Test `get_checklist`: returns all rules applicable to work item type with current statuses
- [ ] 4.16 [RED] Test `on_review_closed`: approved + linked `rule_id` → `status=passed`, `passed_by_review_request_id` set; rejected + linked rule → status stays `pending`; no linked rule → no-op; already passed → idempotent
- [ ] 4.17 [RED] Test `waive_validation`: recommended rule → `status=waived`; required rule → raises `ValidationError`
- [ ] 4.18 [RED] Test `recalculate_on_version_change`: new applicable rules added as `pending`, obsolete rules marked `obsolete`, passed rules preserved
- [ ] 4.19 [GREEN] Implement `application/services/validation_service.py`

### ReadyGateService (US-064)

- [ ] 4.20 [RED] Test `check`: all required `passed` → `GateResult(passed=True, blocking=[])`; one required `pending` → `GateResult(passed=False, blocking=[rule])`; only recommended `pending` → `GateResult(passed=True)`; waived recommended → `GateResult(passed=True)`
- [ ] 4.20a [RED] Test `check`: required rule with `status=waived` → `GateResult(passed=False, blocking=[rule])` AND a warning is logged — belt-and-suspenders guard (Fixed per backend_review.md ALG-3)
- [ ] 4.21 [GREEN] Implement `application/services/ready_gate_service.py` — treat required+waived as blocking with `log.warning`

### Ready Gate Integration — EP-01 WorkItemService Extension (Fixed per backend_review.md SD-2)

> `WorkItemTransitionService` is NOT implemented as a standalone service — it duplicates FSM ownership. Instead, `WorkItemService.transition_state()` (EP-01) accepts an optional `ready_gate_checker` callable and calls it when `target_state == READY`. EP-06 exports `ReadyGateService` which is injected into EP-01's service.

- [ ] 4.22 [RED] Test `WorkItemService.transition_state(target_state=READY, ready_gate_checker=...)`: gate passed → `work_item.state=ready`, `has_override=false`; gate blocked → raises `ReadyGateBlockedError` with `blocking_rules`
- [ ] 4.23 [RED] Test override: valid justification + `override=true` → `state=ready`, `has_override=true`, FSM audit event includes bypassed rules list
- [ ] 4.24 [RED] Test override: empty justification → raises `ValidationError`; non-owner → raises `AuthorizationError`
- [ ] 4.25 [RED] Test override fields reset on new version increment
- [ ] 4.26 [GREEN] Extend `WorkItemService.transition_state()` in EP-01 to accept `ready_gate_checker: Callable[[UUID], GateResult] | None`; inject `ReadyGateService` from EP-06. Do NOT create a standalone `WorkItemTransitionService`

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

- [ ] 5.1 [RED] Test fan-out Celery task: sends one `INSERT notifications` per team member; idempotency key `sha256(review_request_id + member_id)` prevents duplicate on retry
- [ ] 5.2 [RED] Test: SSE notification dispatched to reviewer on new review request (via Redis pub/sub)
- [ ] 5.3 [RED] Test: SSE notification dispatched to owner when review response received
- [ ] 5.4 [RED] Test: SSE notification dispatched to owner when all required validations pass
- [ ] 5.5 [GREEN] Implement `infrastructure/tasks/review_notification_tasks.py` — Celery fan-out tasks
- [ ] 5.6 [REFACTOR] Reuse EP-08 SSE publisher (`sse_publisher.py`); do not duplicate Redis push logic

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

- [ ] 6.1 [RED] Integration test: `POST /api/v1/work-items/{id}/review-requests` → 201, shape correct; non-owner → 403; invalid reviewer_type → 422
- [ ] 6.2 [RED] Integration test: `GET /api/v1/work-items/{id}/review-requests` → list; `GET /api/v1/review-requests/{id}` → includes `version_outdated` flag when versions differ
- [ ] 6.3 [RED] Integration test: `DELETE /api/v1/review-requests/{id}` → 200 status=cancelled; non-owner → 403; already closed → 409
- [ ] 6.4 [GREEN] Implement `presentation/controllers/review_request_controller.py`

### review_response_controller.py

- [ ] 6.5 [RED] Integration test: `POST /api/v1/review-requests/{id}/response` approved → 200; rejected → 200 + work item `changes_requested`; non-assigned → 403; closed → 409; rejected without content → 422
- [ ] 6.6 [RED] Integration test: `GET /api/v1/review-requests/{id}/response` → 200 or 404
- [ ] 6.7 [GREEN] Implement `presentation/controllers/review_response_controller.py`

### validation_controller.py

- [ ] 6.8 [RED] Integration test: `GET /api/v1/work-items/{id}/validations` → checklist with `required`/`recommended` split
- [ ] 6.9 [RED] Integration test: `POST /api/v1/work-items/{id}/validations/{rule_id}/waive` recommended → 200; required → 422
- [ ] 6.10 [GREEN] Implement `presentation/controllers/validation_controller.py`

### work_item_controller.py (extend EP-01)

- [ ] 6.11 [RED] Integration test: `POST /api/v1/work-items/{id}/transition` with `target_state=ready` — all passed → 200; pending required → 422 `READY_GATE_BLOCKED` with `blocking_rules`; override=true + justification → 200 `has_override=true`; override=true + no justification → 422; non-owner → 403
- [ ] 6.12 [GREEN] Extend EP-01 `work_item_controller.py` to handle `target_state=ready` via `WorkItemTransitionService`

---

## Phase 7 — Integration & Edge Cases

- [ ] 7.1 [RED] E2E: full review round-trip — request → team fan-out → member responds approved → validation passes → transition to Ready → 200
- [ ] 7.2 [RED] E2E: iterative flow — request → reject → owner edits (new version) → re-request → approve → Ready
- [ ] 7.3 [RED] E2E: override flow — pending required validation → `override=true` → audit event contains `bypassed_rules`
- [ ] 7.4 [RED] Test: outdated version detection — review requested on v2, item now at v4, GET returns `version_outdated=true`
- [ ] 7.5 [RED] Test: second approve on same validation rule → idempotent on `passed` status
- [ ] 7.6 [REFACTOR] N+1 check on checklist endpoint; error message consistency pass
