# Capture Specs — EP-02

## US-020: Create Work Item from Free Text

### Overview

A workspace member creates a new work item by entering free text and selecting a type. Minimum viable input is a non-empty title (3–255 chars) and a type. All other fields are optional at creation. The item lands in `Draft` state with the creator as default owner.

---

### Scenario: Successful creation with minimal input

WHEN an authenticated user submits a creation request with a valid title and type
THEN the system creates a work item in `Draft` state
AND sets `owner_id = creator_id = requesting user`
AND stores the verbatim title text in `original_input`
AND sets `completeness_score` based on available fields
AND returns the created item with HTTP 201 including the full header (id, type, state, owner, completeness_score)
AND the item is immediately visible in the workspace listing for that project

---

### Scenario: Creation with full optional fields

WHEN an authenticated user submits title, type, description, priority, due_date, and tags
THEN all provided fields are persisted
AND `original_input` is set to the verbatim title value at creation time (immutable from this point)
AND `completeness_score` reflects the richer field set
AND state remains `Draft`

---

### Scenario: Title too short

WHEN a user submits a title with fewer than 3 characters
THEN the system rejects with HTTP 422
AND returns error code `VALIDATION_ERROR` with `details.field = "title"`
AND no item is created

---

### Scenario: Title too long

WHEN a user submits a title exceeding 255 characters
THEN the system rejects with HTTP 422
AND returns error code `VALIDATION_ERROR` with `details.field = "title"`

---

### Scenario: Invalid type

WHEN a user submits a type value not in the valid enum
THEN the system rejects with HTTP 422
AND returns error code `VALIDATION_ERROR` with `details.field = "type"`

---

### Scenario: Unauthenticated creation attempt

WHEN a request to POST /api/v1/work-items arrives without a valid JWT
THEN the system rejects with HTTP 401
AND no item is created

---

### Scenario: Project membership check

WHEN a user submits a valid creation request for a project they are not a member of
THEN the system rejects with HTTP 403
AND returns error code `FORBIDDEN`
AND no item is created

---

### Scenario: Item appears in workspace listing immediately

WHEN a work item is created
THEN a subsequent GET /api/v1/projects/{project_id}/work-items returns the new item
AND the item is present even with state filter `draft`

---

## US-021: Save and Resume Drafts

### Overview

While a user is composing a work item (partially filled form), the frontend auto-saves a draft periodically. If the user navigates away or closes the tab, the draft is preserved. On return, the in-progress state is restored. A draft is distinct from a committed work item: it has not been formally "created" yet (no `work_item_id` until the user confirms creation), or it may be a work item in `Draft` state that is being edited.

Two draft modes:
1. **Pre-creation draft**: user has started filling the form but not yet submitted. Stored client-side (localStorage) with a server-side backup via `draft_data` on a `work_item_drafts` session record.
2. **Post-creation edit draft**: a `Draft`-state work item whose fields are being edited. Auto-save writes directly to the `work_items` row via PATCH.

---

### Scenario: Auto-save triggers during form composition (pre-creation)

WHEN the user has entered at least a non-empty title field
AND has not submitted the creation form
AND 3 seconds have elapsed since the last keystroke (debounce)
THEN the frontend sends a draft save request to POST /api/v1/work-item-drafts
AND the server upserts a draft record keyed by (user_id, workspace_id)
AND returns HTTP 200 with the draft_id
AND the frontend stores the draft_id locally

---

### Scenario: Auto-save with partial/invalid data

WHEN the auto-save fires with data that would fail full creation validation (e.g., title < 3 chars)
THEN the server still persists the draft as-is (no validation gate on drafts)
AND returns HTTP 200
AND the draft is marked `incomplete = true`

---

### Scenario: User navigates away mid-form

WHEN the user leaves the creation page without submitting
AND a draft was auto-saved
THEN no committed work item is created
AND the draft record remains in the server with the last auto-saved state

---

### Scenario: User returns and resumes draft

WHEN an authenticated user opens the work item creation form
AND a draft record exists for (user_id, workspace_id)
THEN the system prompts the user to resume the existing draft
AND WHEN the user accepts THEN the form is pre-populated with the draft data
AND the draft_id is associated with the session
AND WHEN the user submits the form THEN the draft record is deleted
AND the committed work item is created with `original_input` set to the initial free text from the draft

---

### Scenario: User discards a draft

WHEN the user explicitly discards the draft
THEN the server deletes the draft record
AND the form resets to empty

---

### Scenario: Multiple concurrent tabs — last-write-wins with staleness warning

WHEN the same user has the creation form open in two tabs
AND both tabs are auto-saving
THEN the server accepts the save from whichever tab sends last (last-write-wins on draft)
AND WHEN a tab receives a 409 response because its local_version is behind the server version THEN it shows a staleness warning
AND offers the user a choice: keep local edits or reload from server

---

### Scenario: Draft for a committed Draft-state work item

WHEN the user edits a committed work item that is in `Draft` state
AND 3 seconds elapse since the last change (debounce)
THEN the frontend sends PATCH /api/v1/work-items/{id}/draft
AND the server updates `draft_data` (JSONB) on the work item row without changing `updated_at` on the main record
AND returns HTTP 200

---

### Scenario: original_input is immutable after creation

WHEN a work item has been formally created (committed)
AND the user subsequently edits the title or description
THEN `original_input` is NOT updated
AND the original verbatim text from initial submission is preserved in `original_input`
AND the updated title is saved normally to `title`

---

### Scenario: Draft expiry

WHEN a pre-creation draft has not been touched for 30 days
THEN a background job soft-deletes the draft record
AND the user is NOT notified (silent cleanup)
