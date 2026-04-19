# US-012 / US-013 — Ownership and Override

## Stories

**US-012**: As a platform user, I need a single-owner model with reassignment so that accountability is clear and transferable.

**US-013**: As an owner, I need to force an item to Ready even with pending validations, with explicit justification and visible traceability.

---

## Ownership Model

- Every work item has exactly one `owner_id` at all times.
- The owner is responsible for moving the item to `Ready`.
- Only the owner can perform owner-only transitions (see US-011 valid transitions table).
- Ownership can be transferred by: the current owner, a workspace admin.
- All ownership changes are recorded in `ownership_history`.

---

## Acceptance Criteria

### US-012 — Ownership Assignment and Reassignment

#### Assignment at creation

**WHEN** a work item is created without an explicit `owner_id`
**THEN** `owner_id` defaults to `creator_id`

**WHEN** a work item is created with an explicit `owner_id`
**THEN** the system validates that `owner_id` is a member of the workspace
**AND** sets `owner_id` to the provided value

**WHEN** `owner_id` references a suspended or inactive user
**THEN** the system rejects with HTTP 422 and error detail `owner_suspended`

#### Reassignment

**WHEN** the current owner requests reassignment to a different active workspace member
**THEN** the system updates `owner_id` to the new user
**AND** inserts a row in `ownership_history` with: `work_item_id`, `previous_owner_id`, `new_owner_id`, `changed_by`, `changed_at`, `reason` (optional)
**AND** emits `work_item.owner_changed` domain event

**WHEN** a workspace admin requests reassignment regardless of current owner
**THEN** the system applies the change with the same audit trail
**AND** records `changed_by = admin_user_id`

**WHEN** a non-owner, non-admin user requests reassignment
**THEN** the system returns HTTP 403

**WHEN** the target user for reassignment is not a member of the workspace
**THEN** the system rejects with HTTP 422 and error detail `target_user_not_in_workspace`

**WHEN** the target user for reassignment is suspended
**THEN** the system rejects with HTTP 422 and error detail `target_user_suspended`

#### Suspended owner — orphan prevention

**WHEN** a workspace member with active owned work items is suspended
**THEN** the system raises an alert (domain event `workspace.member_suspended_with_active_items`)
**AND** does NOT automatically reassign (requires human decision)
**AND** marks affected items with `owner_suspended_flag = true`
**AND** the items remain fully readable but no owner-only transitions are allowed until reassignment

**WHEN** an admin attempts to complete member suspension when the member owns items in `in_review` or later states
**THEN** the system warns with a list of affected items
**AND** requires either bulk reassignment or explicit acknowledgment before proceeding

**WHEN** an item has `owner_suspended_flag = true`
**THEN** `derived_state` is `blocked` and `blocked_reason` includes `owner_suspended`

#### Orphaned items

**WHEN** reassignment is performed on an item with `owner_suspended_flag = true`
**THEN** the flag is cleared
**AND** a new `ownership_history` row is recorded
**AND** the item resumes normal operation

---

### US-013 — Force Ready (Override)

#### Normal path blocked

**WHEN** the owner requests transition to `ready` and one or more mandatory validations are unresolved
**THEN** the system returns HTTP 422 with error code `MANDATORY_VALIDATIONS_PENDING`
**AND** includes a list of unresolved validation identifiers in the response

#### Override initiation

**WHEN** the owner calls the override endpoint (`POST /api/v1/work-items/{id}/force-ready`) with a non-empty `justification` field
**THEN** the system transitions the item to `ready`
**AND** sets `is_override = true` on the state_transitions audit row
**AND** stores `override_justification` text against the transition record
**AND** marks the work item with `has_override = true` (visible flag on the entity)
**AND** emits `work_item.ready_override` domain event

**WHEN** the override endpoint is called with an empty or missing `justification`
**THEN** the system rejects with HTTP 422 and error detail `justification_required`

**WHEN** a non-owner calls the override endpoint
**THEN** the system returns HTTP 403

#### Override visibility

**WHEN** any user reads a work item that has `has_override = true`
**THEN** the response includes `override_info` object with: `justification`, `overridden_by`, `overridden_at`, list of `skipped_validations`

**WHEN** a work item with `has_override = true` is exported
**THEN** the export snapshot includes the override information

#### Override confirmation step

**WHEN** the owner calls the force-ready endpoint
**THEN** the system requires `confirmed: true` in the request body alongside `justification`
**AND** if `confirmed` is absent or false, returns HTTP 422 with `CONFIRMATION_REQUIRED` and the list of pending validations to acknowledge

#### Limits and governance

**WHEN** a work item has been force-readied and then reverted to `in_clarification` (due to content change)
**THEN** `has_override` is reset to `false` and a new override must be performed if needed again

**WHEN** an admin queries items with `has_override = true`
**THEN** the system supports filtering by `has_override=true` in the list endpoint

---

## Audit Tables Referenced

- `ownership_history`: tracks every ownership transfer
- `state_transitions`: tracks every state change; `is_override` flag and `override_justification` column on this table

---

## Out of Scope

- Validation definition and resolution lifecycle (EP-07)
- Admin suspension workflow UI (EP-11)
- Notification delivery (EP-09)
