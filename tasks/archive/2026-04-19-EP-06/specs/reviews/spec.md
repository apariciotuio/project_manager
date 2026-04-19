# EP-06 Reviews Spec — US-060, US-061, US-063

## US-060 — Request review from users or teams

### Scenario: Request review from a specific user

WHEN the owner of a work item requests a review targeting a specific user
THEN a `review_request` record is created with `reviewer_type=user`, `reviewer_id`, `work_item_id`, `version_id` (current version at request time), and `status=pending`
AND the target user receives a notification via SSE and async Celery task
AND the work item transitions to state `In Review` if not already there
AND a timestamp `requested_at` is stored on the review request

### Scenario: Request review from a team

WHEN the owner requests a review targeting a team
THEN a `review_request` record is created with `reviewer_type=team`, `team_id`, `work_item_id`, `version_id`, and `status=pending`
AND a Celery fan-out task enqueues individual notifications for every active member of the team
AND each notification carries the `review_request_id` so members can respond
AND the fan-out uses an idempotency key derived from `(review_request_id, member_id)` to avoid duplicate notifications on retry

### Scenario: Review is version-pinned

WHEN a review request is created
THEN `version_id` is captured from `work_item_versions` at the moment of the request
AND subsequent edits to the work item do not alter the `version_id` on the existing review request
AND the response UI surfaces the version snapshot alongside the current content so the reviewer can compare

### Scenario: Request review on a work item already in review

WHEN the owner requests an additional review while prior open review requests exist
THEN each new request is created independently with its own `version_id` and `status=pending`
AND the work item remains in state `In Review`
AND the owner can see a list of all open review requests with their individual statuses

### Scenario: Non-owner attempts to request review

WHEN a user who is not the owner or an authorized actor attempts to create a review request
THEN the system returns 403 Forbidden
AND no `review_request` record is created
AND no notification is dispatched

---

## US-061 — Respond to review: approve, reject, or request changes

### Scenario: Reviewer approves

WHEN an assigned reviewer submits a response with `decision=approved`
THEN a `review_response` record is created with `review_request_id`, `responder_id`, `decision=approved`, `content` (optional comment), and `responded_at`
AND the parent `review_request.status` transitions to `closed`
AND the system evaluates whether the closed review satisfies any linked `validation_requirement`
AND if it does, the corresponding `validation_status` is updated to `passed`
AND the owner receives a notification that the review was approved

### Scenario: Reviewer rejects

WHEN an assigned reviewer submits `decision=rejected`
THEN a `review_response` record is created with `decision=rejected` and mandatory `content` (rejection reason)
AND the parent `review_request.status` transitions to `closed`
AND the work item transitions to state `Changes Requested`
AND the owner is notified with the rejection reason

### Scenario: Reviewer requests changes

WHEN an assigned reviewer submits `decision=changes_requested`
THEN a `review_response` record is created with `decision=changes_requested` and mandatory `content`
AND the parent `review_request.status` transitions to `closed`
AND the work item transitions to state `Changes Requested`
AND no validation requirement is updated to `passed`
AND the owner is notified with the requested changes

### Scenario: Non-assigned user attempts to respond

WHEN a user who is not the designated `reviewer_id` (or a member of `team_id`) attempts to submit a response
THEN the system returns 403 Forbidden
AND no `review_response` record is created

### Scenario: Reviewer responds to an already-closed review request

WHEN a reviewer attempts to submit a response on a `review_request` with `status=closed`
THEN the system returns 409 Conflict
AND no duplicate `review_response` is created

### Scenario: Team review — member responds on behalf of team

WHEN a team `review_request` is open and one team member submits a response
THEN the `review_response` records `responder_id` explicitly (identifying the individual)
AND the `review_request.status` transitions to `closed`
AND remaining team members are notified that the review has been resolved
AND the owner can see who within the team provided the response
AND if the team has a designated lead, the system does not restrict responses to the lead only (any member may respond unless the team policy enforces lead-only — enforced at team configuration level from EP-08)

---

## US-063 — Iterative owner-reviewer flow

### Scenario: Owner resubmits for review after changes requested

WHEN the work item is in state `Changes Requested` and the owner submits a new review request
THEN a new `review_request` is created with a new `version_id` (reflecting the current version after edits)
AND the previous closed review requests remain in history with their original `version_id`
AND the work item transitions back to state `In Review`
AND the assigned reviewer (or team) is notified of the new request

### Scenario: Review on outdated version surfaced to reviewer

WHEN a reviewer opens a pending review request
AND the current `work_item.version_id` differs from `review_request.version_id`
THEN the response surface displays a visible warning: "This review was requested on version N; the item has since been updated to version M"
AND the reviewer can still submit their response — the system does not block outdated-version responses
AND the response is recorded with the original `review_request.version_id` for audit fidelity

### Scenario: Multiple review rounds tracked

WHEN several iterative rounds of review occur on the same work item
THEN each round produces distinct `review_request` and `review_response` records
AND the full history is retrievable ordered by `requested_at`
AND the UI distinguishes active (pending) from historical (closed) review requests

### Scenario: Owner cancels a pending review request

WHEN the owner cancels a pending `review_request`
THEN the `review_request.status` transitions to `cancelled`
AND the assigned reviewer is notified of the cancellation
AND no `review_response` is required
AND the work item state is re-evaluated — if no other pending review requests exist, state may revert to `In Clarification` or previous state per FSM rules from EP-01
