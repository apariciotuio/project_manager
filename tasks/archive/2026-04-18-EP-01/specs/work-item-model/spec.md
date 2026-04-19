# US-010 — Work Item Domain Model

## Story

As a platform user, I need a well-defined work item entity so that all types of work can be captured, tracked, and matured through the system with consistent rules.

## Scope

This spec covers creation, reading, updating, and deletion of work items. It does not cover state transitions (US-011), ownership changes (US-012/013), or export (covered in EP-12).

---

## Field Definitions

### Required Fields (all types)

| Field | Type | Rules |
|-------|------|-------|
| `id` | UUID | System-generated, immutable |
| `title` | string | 3–255 characters, non-empty after trim |
| `type` | enum | One of 8 defined types |
| `state` | enum | Set by state machine; defaults to `draft` |
| `owner_id` | UUID | FK to users; required at creation |
| `project_id` | UUID | FK to projects; required |
| `creator_id` | UUID | FK to users; set from auth context, immutable |
| `created_at` | timestamp | System-generated, immutable |
| `updated_at` | timestamp | System-managed |

### Optional Fields

| Field | Type | Notes |
|-------|------|-------|
| `description` | text | Raw input / problem statement |
| `original_input` | text | Verbatim capture; preserved even if description changes |
| `priority` | enum | `low`, `medium`, `high`, `critical`; nullable |
| `due_date` | date | Optional deadline; no enforcement ⚠️ originally MVP-scoped — see decisions_pending.md |
| `tags` | string[] | Free-form labels |
| `completeness_score` | int | 0–100; computed by backend, not user-settable |
| `derived_state` | enum | `in_progress`, `blocked`, `ready`; computed, not stored |
| `blocked_reason` | text | Populated when derived_state is `blocked` |
| `next_step` | text | System-recommended next action; computed |
| `exported_at` | timestamp | Set when state reaches `exported` |
| `export_reference` | string | External Jira key; nullable |

---

## Element Types

| Type | English | Notes |
|------|---------|-------|
| `idea` | Idea | Exploratory; minimal required fields beyond title |
| `bug` | Bug | Should capture reproduction steps |
| `enhancement` | Enhancement | Improvement to existing functionality |
| `task` | Task | Actionable unit with clear scope |
| `initiative` | Initiative | Parent of multiple items; strategic |
| `spike` | Spike / Research | Time-boxed investigation |
| `business_change` | Business Change | Process or policy change |
| `requirement` | Requirement | Formal functional or non-functional requirement |

All 8 types share the same entity structure. Type affects: initial template suggestions, recommended validations, and completeness scoring weights. No separate tables per type.

---

## Acceptance Criteria

### Creation

**WHEN** a user submits a create request with a valid `title`, `type`, `project_id`, and authenticated identity
**THEN** the system creates a work item with `state = draft`, `creator_id` from auth context, `created_at = now()`
**AND** the `owner_id` defaults to `creator_id` if not explicitly provided
**AND** the system returns the full work item representation including computed fields

**WHEN** a create request omits `title`
**THEN** the system returns HTTP 422 with error code `VALIDATION_ERROR` and field `title` identified
**AND** no work item is persisted

**WHEN** a create request provides a `title` shorter than 3 characters (after trim)
**THEN** the system rejects with HTTP 422 and error detail `title_too_short`

**WHEN** a create request provides a `title` longer than 255 characters
**THEN** the system rejects with HTTP 422 and error detail `title_too_long`

**WHEN** a create request specifies an invalid `type` value
**THEN** the system rejects with HTTP 422 and error detail `invalid_type`

**WHEN** a create request references a non-existent or inaccessible `project_id`
**THEN** the system rejects with HTTP 404

**WHEN** a create request specifies an `owner_id` that does not exist in the workspace
**THEN** the system rejects with HTTP 422 and error detail `invalid_owner`

### Reading

**WHEN** an authenticated user requests a work item by ID
**THEN** the system returns the full representation including `derived_state`, `completeness_score`, and `next_step`

**WHEN** the requester does not have access to the project containing the work item
**THEN** the system returns HTTP 403

**WHEN** a work item ID does not exist
**THEN** the system returns HTTP 404

**WHEN** listing work items for a project
**THEN** the system returns paginated results with `total`, `page`, `page_size`, and `items`
**AND** results are ordered by `updated_at` descending by default

### Updating

**WHEN** the owner or an authorized collaborator updates `title`, `description`, `priority`, `due_date`, or `tags`
**THEN** the system persists changes and updates `updated_at`
**AND** an audit event is emitted with actor, timestamp, and changed fields

**WHEN** a user attempts to update `state` directly via the update endpoint
**THEN** the system rejects with HTTP 422 and error detail `use_transition_endpoint`
**AND** state remains unchanged

**WHEN** a user attempts to update `creator_id`, `id`, or `created_at`
**THEN** the system ignores those fields silently (read-only fields are stripped from input)

**WHEN** a substantial content change is made to an item in `ready` state (title or description modified)
**THEN** the system recomputes `completeness_score`
**AND** emits a domain event `work_item.content_changed_after_ready` for downstream handling

### Deletion

**WHEN** the owner requests deletion of a `draft` item
**THEN** the system soft-deletes the item (sets `deleted_at`, filters from all queries)

**WHEN** a deletion is requested on an item in any state other than `draft`
**THEN** the system rejects with HTTP 422 and error detail `cannot_delete_non_draft`

**WHEN** a non-owner attempts to delete an item
**THEN** the system rejects with HTTP 403

### Completeness Score

**WHEN** a work item is created
**THEN** the system computes an initial `completeness_score` of 0–100 based on: title presence (weight 10), description (15), original_input (10), type-appropriate fields filled (25), validations passed (20), owner assigned (10), next_step resolvable (10)

**WHEN** any field on the work item changes
**THEN** the system recomputes `completeness_score` synchronously

**WHEN** `completeness_score` is below 30
**THEN** `derived_state` can never be `ready` (regardless of primary state machine)

### Field-level Validation per Type

**WHEN** type is `bug`
**THEN** `description` is strongly recommended (completeness penalty if absent); no hard block

**WHEN** type is `spike`
**THEN** `due_date` is strongly recommended (completeness penalty if absent)

**WHEN** type is `initiative`
**THEN** `description` is required for any state transition beyond `draft`

**WHEN** type is `requirement`
**THEN** `description` is required for any state transition beyond `draft`

---

## Out of Scope

- Specification sub-structure (EP-05)
- Task/subtask hierarchy (EP-06)
- Versioning and diff (EP-08)
- Comments and conversations (EP-08)
- Export fields beyond FK reference (EP-12)
