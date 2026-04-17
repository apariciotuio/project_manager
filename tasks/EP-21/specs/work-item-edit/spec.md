# Spec — Edit Work Item (F-5)

**Capability:** Modal-based edit form wired to existing `PATCH /api/v1/work-items/{id}`.

## Scenarios

### Edit button visible to authorized users

- **WHEN** the user navigates to `/workspace/[slug]/items/[id]`
- **AND** the user is the owner OR has workspace admin role
- **THEN** an "Edit" button appears in the detail header

### Edit button hidden for unauthorized

- **WHEN** the user is neither owner nor admin
- **THEN** the "Edit" button is not rendered
- **AND** no keyboard shortcut opens the edit modal

### Modal opens with prefilled values

- **WHEN** the user clicks "Edit"
- **THEN** a modal opens with inputs for `title`, `description`, `priority`, `type`
- **AND** each input is prefilled with the current value

### Save patches and refreshes

- **WHEN** the user modifies values and clicks "Save"
- **THEN** a `PATCH /api/v1/work-items/{id}` request is fired with only the changed fields
- **AND** on 200 response, the modal closes
- **AND** the detail view reflects the new values without page reload

### Cancel discards changes

- **WHEN** the user modifies values and clicks "Cancel" or presses Esc
- **THEN** the modal closes
- **AND** no request is fired
- **AND** the detail view is unchanged

### Validation errors surface in modal

- **WHEN** the user submits an invalid value (e.g. empty `title`)
- **AND** the backend returns `400` with `field: "title"`
- **THEN** the error is shown below the `title` input inside the modal
- **AND** the modal stays open

### Concurrent edit lock respected

- **WHEN** the work item is edit-locked by another user (EP-17)
- **THEN** the "Edit" button is disabled with a tooltip `"Locked by <user>"`
- **AND** clicking does nothing

### Optimistic save not used

- **WHEN** the user clicks "Save"
- **THEN** the modal shows a pending state (spinner) until the backend responds
- **AND** local state only mutates after 2xx

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| Unauthorized user bypasses frontend hide and calls PATCH directly | Backend authorization already enforced — frontend hide is UX, not security |
| Stale edit overwrites a newer version | Include `If-Match: <etag>` or `updated_at` guard in PATCH; backend returns 409 on conflict |
| XSS via description field | Render description with sanitizer (same pipeline as existing detail view) |
| CSRF on PATCH | Existing JWT + SameSite cookie pattern — unchanged |

## Out of Scope

- Inline editing (click-to-edit on detail fields)
- Rich-text editor for description (plain textarea for MVP)
- Batch edit across multiple items
- Edit history UI (already exists in Timeline tab)
