# US-011 — State Machine

## Story

As the system, I need to enforce a strict state machine on work items so that maturation progress is governed, auditable, and cannot be bypassed without explicit override.

---

## State Definitions

| State (enum value) | Display name | Meaning |
|--------------------|--------------|---------|
| `draft` | Draft | Item exists but is not yet being actively worked |
| `in_clarification` | In Clarification | Owner is actively defining content |
| `in_review` | In Review | Awaiting response from reviewers or validators |
| `changes_requested` | Changes Requested | Explicit changes requested by a reviewer |
| `partially_validated` | Partially Validated | Some validations complete, not all |
| `ready` | Ready | Owner declares item ready for export |
| `exported` | Exported | Final snapshot sent to Jira |

---

## Derived Operational State (computed, never stored)

| Derived state | Condition |
|---------------|-----------|
| `in_progress` | Primary state is `in_clarification`, `in_review`, `changes_requested`, or `partially_validated` AND no active blocking condition |
| `blocked` | Any pending mandatory validation OR explicit block record exists AND item is not `ready` or `exported` |
| `ready` | Primary state is `ready` |

Rule: `exported` items have no derived state (or display `exported` directly).

---

## Valid Transitions

| From | To | Trigger | Actor |
|------|----|---------|-------|
| `draft` | `in_clarification` | Owner starts working | Owner |
| `in_clarification` | `in_review` | Owner submits for review | Owner |
| `in_clarification` | `changes_requested` | Reviewer requests changes directly | Reviewer |
| `in_clarification` | `partially_validated` | Some validations auto-close during clarification | System or Owner |
| `in_clarification` | `ready` | Owner declares ready (requires all mandatory validations OR override) | Owner |
| `in_review` | `changes_requested` | Reviewer requests changes | Reviewer |
| `in_review` | `partially_validated` | Review resolves some validations | System |
| `in_review` | `in_clarification` | Owner pulls back to iterate | Owner |
| `changes_requested` | `in_clarification` | Owner acknowledges and resumes work | Owner |
| `changes_requested` | `in_review` | Owner resubmits after addressing changes | Owner |
| `partially_validated` | `in_review` | Owner submits remaining validations | Owner |
| `partially_validated` | `ready` | Owner declares ready (requires all mandatory validations OR override) | Owner |
| `ready` | `exported` | Explicit export action | Owner (or delegated) |
| `ready` | `in_clarification` | Substantial content change detected or owner reverts | System or Owner |

---

## Invalid Transitions (explicit rejection list)

| From | To | Rejection reason |
|------|----|-----------------|
| `draft` | `in_review` | Must clarify before review |
| `draft` | `ready` | Cannot skip clarification and review |
| `draft` | `exported` | Cannot export a draft |
| `in_clarification` | `exported` | Must reach ready first |
| `in_review` | `exported` | Must reach ready first |
| `changes_requested` | `ready` | Must address changes before ready |
| `changes_requested` | `exported` | Cannot export with pending changes |
| `partially_validated` | `exported` | Must reach ready first |
| `exported` | any | Exported state is terminal |

---

## Acceptance Criteria

### Valid transition — draft to in_clarification

**WHEN** the owner calls the transition endpoint with `target_state = in_clarification` on a `draft` item
**THEN** the system updates the item state to `in_clarification`
**AND** emits `work_item.state_changed` domain event with `from=draft`, `to=in_clarification`, actor, timestamp
**AND** records a state_transition audit row

### Valid transition — in_clarification to in_review

**WHEN** the owner submits a transition to `in_review` from `in_clarification`
**THEN** the system validates that `title` and `description` are non-empty (minimum content gate for entering review)
**AND** transitions state if content gate passes
**AND** rejects with HTTP 422 and `CONTENT_GATE_FAILED` if content gate fails

### Valid transition — in_review to changes_requested

**WHEN** a reviewer triggers `changes_requested` on an `in_review` item
**THEN** the system requires a non-empty `reason` field in the transition payload
**AND** transitions state
**AND** notifies the owner (domain event `work_item.changes_requested`)

### Valid transition — to ready (normal path)

**WHEN** the owner requests transition to `ready` from `in_clarification` or `partially_validated`
**THEN** the system checks all mandatory validations
**AND** if all mandatory validations are complete, transitions to `ready`
**AND** records transition with actor and timestamp

### Invalid transition — rejected with reason

**WHEN** any actor requests a transition not listed in the valid transitions table
**THEN** the system returns HTTP 422 with error code `INVALID_TRANSITION`
**AND** includes `from_state`, `to_state`, and `reason` in the error response body
**AND** the item state remains unchanged

### Non-owner attempting owner-only transitions

**WHEN** a non-owner calls a transition that requires owner role (e.g., `draft` -> `in_clarification`, `* -> ready`)
**THEN** the system returns HTTP 403 with error code `NOT_OWNER`
**AND** the item state remains unchanged

### State entered timestamp

**WHEN** a state transition succeeds
**THEN** `state_entered_at` on the work item is set to the current timestamp
**AND** the previous value is not preserved (current state age is always since last transition)

### State change audit

**WHEN** any state transition succeeds
**THEN** the system inserts a row in `state_transitions` with: `work_item_id`, `from_state`, `to_state`, `actor_id`, `triggered_at`, `transition_reason` (nullable), `is_override` (boolean)

**WHEN** a state transition fails validation
**THEN** no audit row is written

### Derived state computation

**WHEN** a client requests a work item
**THEN** the system computes `derived_state` at read time based on primary state and blocking conditions
**AND** never exposes a stale cached derived state without recomputation

**WHEN** primary state is `ready`
**THEN** `derived_state` equals `ready` regardless of any blocking conditions (override already accepted)

**WHEN** primary state is `exported`
**THEN** `derived_state` is not present (null) in the response

**WHEN** primary state is in `{in_clarification, in_review, changes_requested, partially_validated}` AND one or more mandatory validations are unresolved
**THEN** `derived_state = blocked` AND `blocked_reason` lists the unresolved validation names

**WHEN** primary state is in `{in_clarification, in_review, changes_requested, partially_validated}` AND no blocking conditions exist
**THEN** `derived_state = in_progress`

### Substantial change reverting ready state

**WHEN** an item in `ready` state has `title` or `description` updated with a change that alters content by more than a trivial threshold (backend-defined: >10% character delta or any structural change)
**THEN** the system automatically transitions the item back to `in_clarification`
**AND** emits `work_item.reverted_from_ready` event
**AND** records the automatic transition in the audit table with `actor_id = system`

---

## Out of Scope

- Override logic (US-013)
- Validation definition and resolution (EP-07)
- Review request lifecycle (EP-07)
