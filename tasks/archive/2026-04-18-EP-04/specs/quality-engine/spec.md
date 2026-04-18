# Quality Engine — US-042, US-043
# Completeness Score, Gap Detection, Next Step & Validator Suggestion

## Scoring Model

Completeness is a weighted score from 0–100 computed entirely in the backend. It is never stored
permanently — it is computed on demand and cached in Redis with a short TTL (invalidated on any section
change or state transition).

### Dimensions and Weights

| Dimension              | Weight | Applies to                                    | Check rule                                                            |
|------------------------|--------|-----------------------------------------------|-----------------------------------------------------------------------|
| problem_clarity        |  15%   | Bug, Story, Epic, Initiative, Requirement      | summary + context/actual_behavior filled and >= 50 chars             |
| objective              |  15%   | All types                                     | objective section filled and >= 30 chars                             |
| scope                  |  10%   | Story, Epic, Initiative, Requirement           | scope section filled                                                 |
| acceptance_criteria    |  20%   | Bug, Story, Task, Sub-task, Requirement        | acceptance_criteria has >= 2 distinct criteria (line/bullet check)   |
| dependencies           |   5%   | All types                                     | dependencies section explicitly filled OR marked "none"              |
| risks                  |   5%   | Story, Epic, Initiative, Requirement           | risks section filled OR marked "none"                                |
| breakdown              |  10%   | Epic, Initiative, Story                        | at least 1 linked child work item OR user_stories_breakdown filled   |
| ownership              |   5%   | All types                                     | owner assigned on the work item record                              |
| validations            |  10%   | All types                                     | at least 1 validator assigned OR validation_status acknowledged      |
| next_step_clarity      |   5%   | All types                                     | next_step computed (see US-043) is not `undefined`                   |

Dimensions that do not apply to an element type are excluded and weights are renormalized so total = 100%.

### Score Bands

| Score   | Level  | Hex color (reference) |
|---------|--------|-----------------------|
| 0–39    | Low    | #E53E3E               |
| 40–69   | Medium | #DD6B20               |
| 70–89   | High   | #38A169               |
| 90–100  | Ready  | #2B6CB0               |

The `Ready` band does NOT grant the `Ready` state. It is a signal, not a gate (the state gate is
handled by EP-01 FSM rules which additionally check validations_complete and owner confirmation).

---

## US-042 — View Completeness Level and Functional Gaps

### Scenarios

#### SC-042-01: Compute completeness for a valid element

WHEN an authenticated user requests GET `/api/v1/work-items/:id/completeness`
THEN the backend computes the weighted score across all applicable dimensions
AND returns `score` (integer 0–100), `level` (low|medium|high|ready), and a `dimensions` array
AND each dimension entry includes `name`, `weight`, `score` (0 or 1), `filled` (boolean), and
`contribution` (weight * score, as float)
AND the computation excludes dimensions not applicable to the element type
AND the response is served from Redis cache if valid (TTL 60 seconds)

#### SC-042-02: Cache invalidation on section change

WHEN a section is saved (created or updated)
THEN the completeness cache key for that work item is deleted
AND the next GET request recomputes from scratch

#### SC-042-03: Cache invalidation on state change

WHEN a work item transitions to a new state
THEN the completeness cache key is deleted
AND the validations dimension is recomputed on next request

#### SC-042-04: Gap list

WHEN an authenticated user requests GET `/api/v1/work-items/:id/gaps`
THEN the backend returns only the dimensions where `filled = false` and the dimension applies to this
element type
AND each gap entry includes `dimension`, `message` (human-readable actionable description), and
`severity` (blocking | warning)
AND `blocking` gaps are those from required sections or dimensions with weight >= 10%
AND the gap list is ordered: blocking first, then warnings

#### SC-042-05: No gaps case

WHEN all applicable dimensions are filled
THEN GET `/api/v1/work-items/:id/gaps` returns an empty array `[]`
AND `score` in the completeness response is >= 90

#### SC-042-06: Gap messages are actionable

WHEN the `acceptance_criteria` dimension is not filled on a User Story
THEN the gap message reads: "Define at least 2 acceptance criteria for this User Story."

WHEN the `breakdown` dimension is not filled on an Epic
THEN the gap message reads: "Link at least one User Story or fill the user_stories_breakdown section."

WHEN the `dependencies` dimension is not filled
THEN the gap message reads: "Confirm dependencies exist or explicitly mark them as none."

WHEN the `ownership` dimension is not filled
THEN the gap message reads: "Assign an owner to this work item."

#### SC-042-07: Unauthorized access

WHEN a user without read access to the work item requests completeness or gaps
THEN the backend returns HTTP 403 with error code `COMPLETENESS_ACCESS_FORBIDDEN`

---

## US-043 — Next Step Recommendation and Suggested Validators

### Next-Step Decision Tree

The next step is a single recommended action derived from the combination of current `state`,
`completeness.level`, and the gap list. Decision is pure backend logic — no LLM call.

Priority order (first matching rule wins):

| Priority | Condition                                                           | Recommended Next Step                     |
|----------|---------------------------------------------------------------------|-------------------------------------------|
| 1        | owner is null                                                       | `assign_owner`                            |
| 2        | level = low AND blocking gaps exist                                 | `fill_required_sections`                  |
| 3        | acceptance_criteria gap exists AND type in (Story, Bug, Task)       | `define_acceptance_criteria`              |
| 4        | breakdown gap exists AND type in (Epic, Initiative)                 | `create_child_items`                      |
| 5        | validations dimension unfilled AND state = Draft                    | `assign_validator`                        |
| 6        | state = Draft AND level = medium                                    | `request_clarification`                   |
| 7        | state = Clarification AND level >= medium AND no blocking gaps      | `request_review`                          |
| 8        | state = Review AND no blocking gaps                                 | `address_review_comments`                 |
| 9        | state = ChangesRequested                                            | `apply_requested_changes`                 |
| 10       | state = PartiallyValidated AND validations pending                  | `complete_remaining_validations`          |
| 11       | level = ready AND all validations complete                          | `mark_ready`                              |
| 12       | state = Ready                                                       | `export_to_jira`                          |
| 13       | (fallback)                                                          | `continue_refining`                       |

### Scenarios

#### SC-043-01: Next step when owner is missing

WHEN an authenticated user requests GET `/api/v1/work-items/:id/next-step`
AND the work item has no owner assigned
THEN the response returns `next_step: "assign_owner"` with `message: "Assign an owner before proceeding."`
AND `blocking: true`

#### SC-043-02: Next step with low completeness and blocking gaps

WHEN completeness level is `low` and blocking gaps exist
THEN the response returns `next_step: "fill_required_sections"`
AND `gaps_referenced` lists the blocking gap dimension names
AND `blocking: true`

#### SC-043-03: Next step ready to request review

WHEN completeness level is `medium` or higher AND no blocking gaps exist AND state is `Clarification`
THEN the response returns `next_step: "request_review"` and `blocking: false`

#### SC-043-04: Next step when fully ready

WHEN completeness level is `ready` AND all applicable validations are complete AND state is not yet `Ready`
THEN the response returns `next_step: "mark_ready"` with `blocking: false`
AND `message` explains that the element meets all quality thresholds

#### SC-043-05: Next step when already exported

WHEN the work item state is `Exported`
THEN the response returns `next_step: null` with `message: "This item has been exported to Jira."`

#### SC-043-06: Suggested validators

WHEN an authenticated user requests GET `/api/v1/work-items/:id/next-step`
THEN the response includes a `suggested_validators` array
AND each entry includes `role` (e.g. "tech_lead", "product_owner", "qa_engineer"), `reason`, and
`configured` (boolean indicating whether the workspace has a user mapped to that role)

#### SC-043-07: Validator suggestion by element type

WHEN the work item type is `Bug`
THEN suggested validators include `qa_engineer` (required) and `tech_lead` (optional)

WHEN the work item type is `User Story`
THEN suggested validators include `product_owner` (required) and `tech_lead` (optional)

WHEN the work item type is `Epic` or `Initiative`
THEN suggested validators include `product_owner` (required), `tech_lead` (required), and
`stakeholder` (optional)

WHEN the work item type is `Spike`
THEN suggested validators include `tech_lead` (required)

WHEN the work item type is `Task` or `Sub-task`
THEN suggested validators include `tech_lead` (optional)

WHEN the work item type is `Requirement`
THEN suggested validators include `product_owner` (required), `business_analyst` (optional), and
`tech_lead` (optional)

#### SC-043-08: Validator suggestion when roles not configured

WHEN no user is mapped to a suggested validator role in the workspace configuration
THEN `configured: false` is set for that entry
AND a `setup_hint` field is included with the message "Configure this role in workspace settings."

#### SC-043-09: Override to Ready with pending validations

WHEN the owner requests a state transition to `Ready` and blocking validations are pending
THEN the backend returns HTTP 422 with `next_step: "complete_remaining_validations"` and a list of
pending validation items
AND includes an `override_allowed: true` flag
AND the owner may force the transition by re-submitting with `force_ready: true` and a non-empty
`override_reason`
AND the override is recorded in the work item audit log with reason and timestamp

#### SC-043-10: Next-step caching

WHEN a next-step response is served
THEN it is NOT cached independently — it piggybacks on the completeness cache
AND invalidation of completeness cache also invalidates next-step

---

## Gap Severity Classification

| Dimension             | Severity  | Rationale                                              |
|-----------------------|-----------|--------------------------------------------------------|
| ownership             | blocking  | No owner = no accountability                          |
| objective             | blocking  | Core purpose of the element                           |
| acceptance_criteria   | blocking  | Cannot validate Done without it                       |
| problem_clarity       | blocking  | Ambiguous problem = unclearable scope                 |
| scope                 | blocking  | Scope creep starts here                               |
| breakdown             | warning   | Not always required to start review                   |
| dependencies          | warning   | Should be filled but can be clarified later           |
| risks                 | warning   | Desirable but not a hard blocker                      |
| validations           | warning   | Blocking only once state advances past Clarification  |
| next_step_clarity     | warning   | Derived — not a hard blocker on its own               |
