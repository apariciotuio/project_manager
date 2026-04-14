# EP-06 Technical Design — Reviews, Validations & Flow to Ready

## Domain Model

### ReviewRequest

```python
class ReviewRequest:
    id: UUID
    work_item_id: UUID          # FK work_items
    version_id: UUID            # FK work_item_versions — pinned at request time
    reviewer_type: Literal["user", "team"]
    reviewer_id: UUID | None    # set when reviewer_type=user
    team_id: UUID | None        # set when reviewer_type=team; FK teams (EP-08)
    validation_rule_id: str | None  # optional link to a ValidationRequirement rule
    status: Literal["pending", "closed", "cancelled"]
    requested_by: UUID          # FK users (must be owner)
    requested_at: datetime
    cancelled_at: datetime | None
```

### ReviewResponse

```python
class ReviewResponse:
    id: UUID
    review_request_id: UUID     # FK review_requests
    responder_id: UUID          # FK users — individual who responded
    decision: Literal["approved", "rejected", "changes_requested"]
    content: str | None         # required when decision != approved
    responded_at: datetime
```

### ValidationRequirement (rule definition — static or seeded)

```python
class ValidationRequirement:
    rule_id: str                # e.g. "spec_review_complete", "tech_review_complete"
    label: str
    required: bool              # true = blocks Ready; false = recommended only
    applies_to: list[str]       # work item types this rule applies to
```

### ValidationStatus (per work item instance)

```python
class ValidationStatus:
    id: UUID
    work_item_id: UUID
    rule_id: str                # FK validation_requirements
    status: Literal["pending", "passed", "waived", "obsolete"]
    passed_at: datetime | None
    passed_by_review_request_id: UUID | None
    waived_at: datetime | None
    waived_by: UUID | None
    waive_reason: str | None
```

---

## DB Schema

### review_requests

```sql
CREATE TABLE review_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id        UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    version_id          UUID NOT NULL REFERENCES work_item_versions(id),
    reviewer_type       VARCHAR(10) NOT NULL CHECK (reviewer_type IN ('user', 'team')),
    reviewer_id         UUID REFERENCES users(id),
    team_id             UUID REFERENCES teams(id),
    validation_rule_id  VARCHAR(100) REFERENCES validation_requirements(rule_id),
    status              VARCHAR(15) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'closed', 'cancelled')),
    requested_by        UUID NOT NULL REFERENCES users(id),
    requested_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelled_at        TIMESTAMPTZ,
    -- exactly one of reviewer_id or team_id must be set
    CONSTRAINT chk_reviewer_target CHECK (
        (reviewer_type = 'user' AND reviewer_id IS NOT NULL AND team_id IS NULL) OR
        (reviewer_type = 'team' AND team_id IS NOT NULL AND reviewer_id IS NULL)
    )
);

CREATE INDEX idx_review_requests_work_item ON review_requests(work_item_id);
CREATE INDEX idx_review_requests_reviewer  ON review_requests(reviewer_id) WHERE reviewer_id IS NOT NULL;
CREATE INDEX idx_review_requests_team      ON review_requests(team_id) WHERE team_id IS NOT NULL;
CREATE INDEX idx_review_requests_status    ON review_requests(work_item_id, status);

-- Per db_review.md IDX-2: inbox query filters on (reviewer_id, status='pending').
-- Partial index keeps only the hot rows (pending direct-user reviews) -- small, fast.
CREATE INDEX idx_review_requests_reviewer_pending
    ON review_requests(reviewer_id, status)
    WHERE reviewer_id IS NOT NULL AND status = 'pending';
-- Same pattern for team reviews (inbox Tier 2).
CREATE INDEX idx_review_requests_team_pending
    ON review_requests(team_id, status)
    WHERE team_id IS NOT NULL AND status = 'pending';
```

### review_responses

```sql
CREATE TABLE review_responses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_request_id   UUID NOT NULL REFERENCES review_requests(id) ON DELETE CASCADE,
    responder_id        UUID NOT NULL REFERENCES users(id),
    decision            VARCHAR(20) NOT NULL
                            CHECK (decision IN ('approved', 'rejected', 'changes_requested')),
    content             TEXT,
    responded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- one response per request (enforces the closed-check at service layer too)
    CONSTRAINT uq_one_response_per_request UNIQUE (review_request_id)
);
```

### validation_requirements

```sql
CREATE TABLE validation_requirements (
    rule_id             VARCHAR(100) PRIMARY KEY,
    workspace_id        UUID REFERENCES workspaces(id) ON DELETE CASCADE,  -- NULL = built-in default, workspace-scoped when set
    label               VARCHAR(255) NOT NULL,
    description         TEXT,
    required            BOOLEAN NOT NULL DEFAULT true,            -- true = mandatory, false = recommended/optional
    applies_to          TEXT[] NOT NULL DEFAULT '{}',             -- work item types
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_by          UUID REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_validation_requirements_ws_rule
    ON validation_requirements (workspace_id, rule_id)
    WHERE workspace_id IS NOT NULL;
-- Built-in defaults have workspace_id IS NULL and are code-owned. Workspace-level
-- overrides/additions are editable via API (POST/PATCH/DELETE /api/v1/admin/validation-rules)
-- and via the admin UI (resolution #21, decisions_pending.md).
```

### Review-request rule selection

At review request creation, the owner may attach **extra** rules beyond the baseline enforced by `applies_to`. Mandatory rules (those with `required=true` for the work-item type) cannot be removed from a review — they are always attached. Optional (`required=false`) rules can be added ad-hoc per request.

### validation_statuses

```sql
CREATE TABLE validation_statuses (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id                    UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    rule_id                         VARCHAR(100) NOT NULL REFERENCES validation_requirements(rule_id),
    status                          VARCHAR(10) NOT NULL DEFAULT 'pending'
                                        CHECK (status IN ('pending', 'passed', 'waived', 'obsolete')),
    passed_at                       TIMESTAMPTZ,
    passed_by_review_request_id     UUID REFERENCES review_requests(id),
    waived_at                       TIMESTAMPTZ,
    waived_by                       UUID REFERENCES users(id),
    waive_reason                    TEXT,
    CONSTRAINT uq_validation_status UNIQUE (work_item_id, rule_id)
);

CREATE INDEX idx_validation_statuses_work_item ON validation_statuses(work_item_id);

-- Per db_review.md IDX-7: ReadyGateService filters out 'passed' and 'obsolete' statuses
-- when checking which rules still block ready. Partial index covers the hot path and
-- stays small because most rules are eventually 'passed'.
CREATE INDEX idx_validation_statuses_gate
    ON validation_statuses(work_item_id, status)
    WHERE status NOT IN ('passed', 'obsolete');
```

### work_items override columns

> **Note**: The override columns (`has_override`, `override_justification`, `override_by`,
> `override_at`) are defined in EP-01's `work_items` CREATE TABLE. EP-06 does NOT add them
> — running a duplicate `ALTER TABLE ... ADD COLUMN has_override` would fail with
> `column "has_override" of relation "work_items" already exists`.
>
> EP-06 only *consumes* those columns: `ReadyGateService` writes `has_override=TRUE`,
> `override_justification`, `override_by`, `override_at` atomically inside the
> transition-to-Ready transaction when the override path is taken.

---

## Version-Pinned Reviews

At review request creation, the service reads `work_item.current_version_id` (FK to `work_item_versions`) and writes it to `review_requests.version_id`. This is a snapshot FK — never mutated after creation. The response UI fetches `work_item_versions.snapshot` for that `version_id` to render the "version at review time" alongside current content.

**Outdated version detection**: `GET /api/v1/review-requests/{id}` compares `review_request.version_id` to `work_item.current_version_id`. If they differ, the response includes `{ "version_outdated": true, "requested_version": N, "current_version": M }`.

---

## Review-to-Validation Linkage

A `review_request` optionally carries `validation_rule_id`. When the review closes (any decision), the `ReviewResponseService` calls `ValidationService.on_review_closed(review_request_id)`:

```
on_review_closed(review_request_id):
    rr = load review_request
    if rr.validation_rule_id is None: return
    vs = load validation_status(work_item_id=rr.work_item_id, rule_id=rr.validation_rule_id)
    if rr.response.decision == "approved" and vs.status != "passed":
        vs.status = "passed"
        vs.passed_at = now()
        vs.passed_by_review_request_id = rr.id
        save(vs)
        emit event: VALIDATION_PASSED(work_item_id, rule_id)
```

The linkage is set at review request creation time by the owner or a future rules engine. Currently the owner selects the target validation rule when requesting a review (optional field). ⚠️ originally MVP-scoped — see decisions_pending.md

---

## Ready Gate Logic

`ReadyGateService.check(work_item_id) -> GateResult`:

```
required_statuses = query validation_statuses
    WHERE work_item_id = ? AND rule_id IN (
        SELECT rule_id FROM validation_requirements WHERE required = true
        AND ? = ANY(applies_to)   -- work_item.type
    )

-- Fixed per backend_review.md ALG-3:
-- required+waived must be treated as blocking. The domain invariant prevents waiving
-- required rules, but the gate must not silently pass if that invariant is ever
-- violated (e.g. DB migration error, direct SQL edit).
for vs in required_statuses:
    if vs.status == 'waived':
        log.warning(f"Required rule {vs.rule_id} has waived status — treating as blocking")
        blocking.append(vs)
    elif vs.status != 'passed':
        blocking.append(vs)

-- Original (incorrect) line removed:
-- blocking = [vs for vs in required_statuses if vs.status not in ('passed', 'waived')]

return GateResult(passed=len(blocking)==0, blocking_rules=blocking)
```

Called by `WorkItemFSMService` before allowing any transition to `Ready`. If `gate.passed` is false and no override flag is present, return 422 with `blocking_rules`.

Override path bypasses gate check but writes full audit to `work_item_fsm_events` with all `blocking_rules` at time of override.

---

## API Endpoints

### Review Requests

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/work-items/{id}/review-requests` | Create review request (owner only) |
| GET | `/api/v1/work-items/{id}/review-requests` | List all review requests for item |
| GET | `/api/v1/review-requests/{id}` | Get single request with version-outdated flag |
| DELETE | `/api/v1/review-requests/{id}` | Cancel pending request (owner only) |

### Review Responses

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/review-requests/{id}/response` | Submit response (assigned reviewer only) |
| GET | `/api/v1/review-requests/{id}/response` | Get response for a request |

### Validations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/work-items/{id}/validations` | Get checklist with statuses |
| POST | `/api/v1/work-items/{id}/validations/{rule_id}/waive` | Waive recommended validation (owner only) |

### Ready Transition

> **Note**: Dedicated ready transition endpoints are removed. Ready gate logic is invoked by EP-01's generic `POST /api/v1/work-items/{id}/transition` endpoint when `target_state='ready'`. The `ReadyGateService` is defined here but called from EP-01's `WorkItemService.transition_state()`.

> **SD-2 fix (per backend_review.md SD-2)**: `WorkItemTransitionService` must NOT exist as a standalone service — it duplicates FSM ownership with EP-01's `WorkItemService`. The ready gate check is a pre-condition for the `→ ready` transition, not a separate service. Implementation:
> - EP-01's `WorkItemService.transition_state()` accepts an optional `ready_gate_checker: Callable | None` parameter
> - When `target_state == READY`, it calls `ready_gate_checker(work_item_id)` if provided
> - `ReadyGateService` (EP-06) is injected into EP-01's `WorkItemService` as the checker
> - EP-06 does NOT implement a separate `WorkItemTransitionService` class
> Override justification is passed via the generic transition request body: `{ "target_state": "ready", "override": true, "override_justification": "string (required when override=true)" }`.

---

## Sequence Diagram: Review Request → Notification → Response → Validation Update → Ready Check

```
Owner                   API                  ReviewService         NotificationService    ValidationService     FSMService
  |                      |                        |                        |                     |                   |
  |--POST review-request→|                        |                        |                     |                   |
  |                      |--create_review_req()-->|                        |                     |                   |
  |                      |                        |--pin version_id        |                     |                   |
  |                      |                        |--INSERT review_request |                     |                   |
  |                      |                        |--UPDATE work_item FSM→ In Review             |                   |
  |                      |                        |--fan_out_notify()----->|                     |                   |
  |                      |                        |                        |--Celery task per     |                   |
  |                      |                        |                        |  member (idempotent) |                   |
  |                      |                        |                        |--SSE push to reviewer|                  |
  |<--201 Created--------|                        |                        |                     |                   |
  |                      |                        |                        |                     |                   |
Reviewer                 |                        |                        |                     |                   |
  |--POST .../response-->|                        |                        |                     |                   |
  |                      |--submit_response()---->|                        |                     |                   |
  |                      |                        |--validate responder    |                     |                   |
  |                      |                        |--INSERT review_response|                     |                   |
  |                      |                        |--UPDATE rr.status=closed                     |                   |
  |                      |                        |--on_review_closed()-------------------------→|                   |
  |                      |                        |                        |                     |--evaluate rule    |
  |                      |                        |                        |                     |--UPDATE vs.status |
  |                      |                        |                        |                     |--emit VALIDATED   |
  |                      |                        |                        |                     |--notify owner---->|
  |                      |                        |--update FSM if needed→ (Changes Requested / partial)            |
  |<--200 OK-------------|                        |                        |                     |                   |
  |                      |                        |                        |                     |                   |
Owner                    |                        |                        |                     |                   |
  |--POST .../ready------>|                       |                        |                     |                   |
  |                      |--transition_ready()----|------------------------------------------------>|                |
  |                      |                        |                        |                     |--check_gate()     |
  |                      |                        |                        |                     |  blocking=[]      |
  |                      |                        |                        |                     |--gate passed----->|
  |                      |                        |                        |                        |--FSM to Ready  |
  |<--200 OK-------------|                        |                        |                        |               |
```

---

## Cross-Epic Dependencies

> **Resolved 2026-04-14 (decisions_pending.md #21)**: cross-epic fan-out uses the in-process event bus (EP-08). `ReviewResponseService.submit()` directly calls `WorkItemService.transition_state()` for the state change (simple, synchronous, same transaction), AND emits a `review.completed` domain event on the bus carrying `{work_item_id, review_request_id, decision, responder_id}` for observational consumers (notifications, dashboards, Puppet re-index). Subscribers listen via `AbstractEventBus`; see EP-08 for the bus contract. Direct call for state transition, event emission for fan-out.

### Admin API for validation rules

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/admin/validation-rules` | workspace admin | List rules (built-in + workspace overrides). |
| POST | `/api/v1/admin/validation-rules` | workspace admin | Create a workspace-scoped rule. |
| PATCH | `/api/v1/admin/validation-rules/:rule_id` | workspace admin | Edit label/required/applies_to/is_active. |
| DELETE | `/api/v1/admin/validation-rules/:rule_id` | workspace admin | Soft-disable workspace rule (sets `is_active=false`). |

All mutations are audited (`validation_rule.created|updated|disabled`). Built-in (workspace_id IS NULL) rules cannot be deleted, only overridden per workspace.

---

## Authorization Summary

| Action | Allowed roles |
|--------|--------------|
| Create review request | Owner of work item |
| Cancel review request | Owner of work item |
| Submit review response | Designated `reviewer_id` or member of `team_id` |
| Waive recommended validation | Owner of work item |
| Attempt to waive required validation | Blocked (422) |
| Transition to Ready (normal) | Owner of work item |
| Transition to Ready (override) | Owner of work item only |
| View review requests and checklist | Any authenticated team member |

---

## Key Constraints and Edge Cases

- `review_responses` has a UNIQUE constraint on `review_request_id` — enforces one response per request at DB level as backstop to service-layer check.
- Team reviews: any member may respond; lead-only restriction is a team-level policy from EP-08, not enforced here.
- A `validation_status` of `passed` is never downgraded by a subsequent reject/changes_requested response — only a new version increment (spec change) can trigger re-evaluation.
- Override fields on `work_items` are reset when a new version causes exit from `Ready` — but the FSM event log is append-only and retains the original override record.
- Fan-out notifications use idempotency key `sha256(review_request_id + member_id)` to be safe on Celery retry.
