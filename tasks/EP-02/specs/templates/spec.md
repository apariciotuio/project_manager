# Templates & Header Specs — EP-02

## US-022: Use Templates by Type

### Overview

Each of the 8 work item types has an optional template: a structured JSON document that defines default sections and placeholder prompts. When a user selects a type, the template (if one exists for that type) pre-populates the description field with a structured scaffold. Templates are workspace-level configurable; a default system template ships per type. The user can override, extend, or ignore the template at any time.

---

### Scenario: Template exists for selected type

WHEN a user selects a type during work item creation (e.g., `bug`)
AND a template exists for `bug` in the active workspace
THEN the system fetches the template via GET /api/v1/templates?type=bug
AND pre-populates the description field with the template scaffold
AND marks the pre-population as template-applied (for tracking)
AND the user can freely edit or clear the template content

---

### Scenario: No template for selected type

WHEN a user selects a type for which no template exists in the workspace
THEN the description field is left empty
AND no error is shown
AND creation proceeds normally

---

### Scenario: User changes type after template was applied

WHEN the user selects a type (template is applied)
AND subsequently changes the type to a different value
THEN the system prompts: "Changing type will replace the current template. Continue?"
AND WHEN the user confirms THEN the new type's template (or empty if none) replaces the description field
AND WHEN the user cancels THEN the type selection reverts and the existing description is untouched

---

### Scenario: User edits template content

WHEN the template is applied and the user modifies the description field
THEN the edits are persisted to the work item normally
AND the original template is NOT modified
AND the template scaffold is preserved in `template_id` on the work item for audit purposes only

---

### Scenario: Workspace admin creates a custom template

WHEN a workspace admin sends POST /api/v1/templates with a valid type and content
THEN the system creates a workspace-level template record
AND it takes precedence over the system-default template for that type in this workspace
AND returns HTTP 201 with the template id

---

### Scenario: Workspace admin updates a template

WHEN a workspace admin updates an existing template via PATCH /api/v1/templates/{id}
THEN the update is applied to the template record
AND existing work items that referenced the old template version are NOT affected (snapshot at creation)
AND new creations from this point use the updated template

---

### Scenario: System default template used when no workspace override exists

WHEN a user creates a work item of a given type
AND no workspace-specific template exists for that type
THEN the system default template for that type is applied (if one exists)
AND the system default is read-only (cannot be modified, only overridden at workspace level)

---

### Scenario: Template content size limit

WHEN a template body exceeds 50,000 characters
THEN the system rejects with HTTP 422
AND returns error code `VALIDATION_ERROR` with `details.field = "content"`

---

### Scenario: Unauthenticated template fetch

WHEN GET /api/v1/templates is called without a valid JWT
THEN the system returns HTTP 401

---

### Scenario: Non-admin template mutation

WHEN a non-admin workspace member attempts POST or PATCH on /api/v1/templates
THEN the system returns HTTP 403
AND returns error code `FORBIDDEN`

---

## US-023: Show Functional Header from Creation

### Overview

From the moment a work item exists (even in `Draft` state), a persistent header is visible on the detail view. The header shows: type badge, title, state chip, owner avatar + name, completeness score bar, and a "next step" indicator. These are computed and served with every GET /work-items/{id} response. No separate endpoint needed.

---

### Scenario: Header visible immediately after creation

WHEN a work item is created (POST /work-items returns 201)
THEN the response payload includes the full header block:
  - `type` (enum value + display label)
  - `title`
  - `state` = `draft`
  - `owner.id`, `owner.display_name`, `owner.avatar_url`
  - `completeness_score` (0–100)
  - `derived_state` (computed: `in_progress` | `blocked` | `ready` | null)
AND the frontend renders these immediately without a second fetch

---

### Scenario: Header reflects current state after transition

WHEN a state transition occurs (POST /work-items/{id}/transitions)
THEN the GET /work-items/{id} response returns updated `state` and `derived_state`
AND the header chip updates to reflect the new state

---

### Scenario: Completeness score shown as percentage bar

WHEN a work item is fetched
THEN `completeness_score` is an integer 0–100
AND the frontend renders a visual progress bar
AND the score updates in real-time as the user fills fields (optimistic update during editing)

---

### Scenario: Owner always shown from creation

WHEN a work item is fetched
THEN `owner` is always populated (defaults to creator at creation)
AND if the owner's workspace membership is suspended, `owner.suspended = true` is present
AND the header shows a warning indicator when the owner is suspended

---

### Scenario: Next step indicator when completeness is low

WHEN `completeness_score < 30`
THEN the header shows a "next step" hint (e.g., "Add a description to improve completeness")
AND the hint is computed from the missing high-weight fields per the completeness algorithm

---

### Scenario: Derived state shown as secondary indicator

WHEN `derived_state = blocked`
THEN the header shows a blocking indicator alongside the primary state chip
AND WHEN `derived_state = ready` AND `state = draft` THEN the header shows a "ready to advance" affordance

---

### Scenario: Header on a deleted (soft-deleted) item

WHEN a work item has been soft-deleted (`deleted_at IS NOT NULL`)
THEN GET /work-items/{id} returns HTTP 404
AND no header is rendered

---

### Scenario: Owner avatar fallback

WHEN the owner does not have an avatar_url
THEN the header renders the owner's initials as a fallback avatar
AND no broken image is shown
