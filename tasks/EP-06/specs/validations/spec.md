# EP-06 Validations Spec — US-062, US-064

## US-062 — Manage validation checklist

### Scenario: Validation requirements loaded for a work item

WHEN a work item is created or its spec is updated (EP-04)
THEN the system evaluates the active `validation_requirement` rules applicable to the work item type
AND each rule produces a `validation_status` record with `status=pending` if one does not already exist
AND rules carry a `required` boolean — required rules block the Ready transition, recommended rules do not

### Scenario: View validation checklist

WHEN the owner or any team member views a work item
THEN the checklist is returned with each `validation_requirement`: `rule_id`, `label`, `required`, and the current `validation_status` (`pending`, `passed`, `waived`)
AND required items are visually distinguished from recommended items
AND the checklist shows the count of passed / total required validations

### Scenario: Manual waiver of a recommended validation

WHEN an owner marks a recommended validation as waived
THEN `validation_status.status` transitions to `waived` with `waived_by`, `waived_at`, and mandatory `waive_reason`
AND a waiver does not block the Ready transition
AND the waiver is visible in the checklist with its reason

### Scenario: Manual waiver of a required validation is not permitted through the normal flow

WHEN an owner attempts to waive a required validation outside of the override flow
THEN the system returns 422 Unprocessable Entity
AND the required validation remains `pending`
AND the owner is directed to use the override flow (US-064) if they need to proceed

### Scenario: Auto-update checklist when a review closes with approval

WHEN a `review_request` transitions to `status=closed` with a `review_response.decision=approved`
AND the review request is linked to a `validation_requirement` via `review_request.validation_rule_id`
THEN the corresponding `validation_status.status` transitions to `passed`
AND `passed_at` and `passed_by_review_request_id` are recorded
AND the owner is notified if this causes all required validations to pass

### Scenario: Auto-update checklist when a review closes without approval (reject or changes_requested)

WHEN a `review_request` transitions to `closed` with `decision=rejected` or `decision=changes_requested`
AND the review request is linked to a `validation_requirement`
THEN the corresponding `validation_status.status` remains `pending` (does not regress from a prior `passed` state if a different review previously satisfied it)
AND no checklist update is applied

### Scenario: Multiple reviews can satisfy the same validation requirement

WHEN more than one `review_request` is linked to the same `validation_rule_id` and at least one closes with `approved`
THEN the `validation_status` is `passed`
AND the `passed_by_review_request_id` records the first review that achieved approval

### Scenario: Validation checklist recalculated after spec version change

WHEN a work item version is incremented (EP-04) and the spec content changes substantially
THEN the system re-evaluates active `validation_requirement` rules
AND new rules that become applicable are added as `pending`
AND rules that no longer apply are marked `obsolete`
AND previously `passed` statuses that are still applicable are preserved

---

## US-064 — Normal and override flow to Ready

### Scenario: Normal transition to Ready — all required validations passed

WHEN all `validation_status` records with `required=true` for the work item have `status=passed`
AND the owner triggers the Ready transition
THEN the work item state transitions to `Ready`
AND `work_item.has_override` remains `false`
AND `work_item.override_justification` remains null
AND the transition is recorded in the FSM event log with actor and timestamp

### Scenario: Normal Ready blocked by pending required validations

WHEN the owner attempts to trigger the Ready transition
AND one or more `validation_status` records with `required=true` have `status=pending`
THEN the system returns 422 Unprocessable Entity
AND the response body lists each blocking `validation_requirement`: `rule_id`, `label`
AND the work item state does not change
AND no FSM event is recorded

### Scenario: Override flow — owner forces Ready with justification

WHEN the owner triggers the override-Ready endpoint
AND provides a non-empty `override_justification` string
AND explicitly confirms (`override_confirmed: true` in request body)
THEN the work item transitions to `Ready`
AND `work_item.has_override` is set to `true`
AND `work_item.override_justification` is stored on the row
AND `work_item.override_by` and `work_item.override_at` are recorded
AND the override is visible in the work item detail with a distinct indicator
AND an audit event is written to the FSM event log with actor, timestamp, justification, and list of pending validations that were bypassed

### Scenario: Override attempted without justification

WHEN the owner triggers the override-Ready endpoint with an empty or missing `override_justification`
THEN the system returns 422 Unprocessable Entity
AND the work item state does not change
AND `has_override` remains unchanged

### Scenario: Override attempted without explicit confirmation

WHEN the owner triggers the override-Ready endpoint without `override_confirmed: true`
THEN the system returns 422 Unprocessable Entity
AND the work item state does not change

### Scenario: Non-owner attempts override

WHEN a user who is not the owner of the work item attempts the override-Ready endpoint
THEN the system returns 403 Forbidden
AND no state change occurs
AND no audit event is written

### Scenario: Override visible and auditable after the fact

WHEN any user views a work item with `has_override=true`
THEN the checklist displays which required validations were pending at time of override
AND the `override_justification`, `override_by`, and `override_at` are accessible
AND this information is included in any export or audit report

### Scenario: Subsequent edit on a Ready item with override invalidates Ready

WHEN a work item is in state `Ready` with `has_override=true`
AND a substantial content change is made (new version created)
THEN the system transitions the work item out of `Ready` per EP-01 FSM rules
AND `has_override` is reset to `false`
AND `override_justification` is cleared
AND the prior override event remains in the FSM event log for audit purposes (log is append-only)
