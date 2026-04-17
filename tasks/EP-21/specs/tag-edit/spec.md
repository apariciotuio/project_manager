# Spec — Edit Tag (F-10)

**Capability:** Wire the existing backend `PATCH /api/v1/tags/{tag_id}` endpoint to a frontend edit modal. Backend is already done — this is purely frontend work.

## Context

- Backend: `backend/app/presentation/controllers/tag_controller.py:136` — `PATCH /tags/{tag_id}` exists and accepts name/color/archived.
- Frontend: `useAdmin.ts:216` — only wires `PATCH` for `{ archived: true }`. No edit form.
- User-visible symptom: tags can be created, archived, and deleted, but NOT renamed or recolored. The backend capability is dark.

## Scenarios

### Edit button visible to admins

- **WHEN** the user is a workspace admin
- **AND** the admin tag list renders a tag row
- **THEN** an Edit icon (pencil) appears on hover/focus
- **AND** the icon has `aria-label="Edit tag <name>"`

### Edit button hidden for non-admins

- **WHEN** the user is not a workspace admin
- **THEN** no Edit icon renders
- **AND** no keyboard shortcut opens the edit modal

### Modal opens with prefilled values

- **WHEN** the admin clicks Edit on a tag
- **THEN** a modal opens with inputs for `name` (text) and `color` (F-9 color picker)
- **AND** inputs are prefilled with the current tag values

### Save sends only changed fields

- **WHEN** the admin changes `name` only and submits
- **THEN** `PATCH /api/v1/tags/{id}` is called with body `{ name: "..." }` (color omitted)
- **WHEN** the admin changes both
- **THEN** the body includes both fields
- **WHEN** the admin submits with no changes
- **THEN** the Save button is disabled (no request fired)

### UI refresh after save

- **WHEN** the backend returns 200
- **THEN** the modal closes
- **AND** the tag row in the admin list shows the new values without page reload (see F-3)

### Cancel discards

- **WHEN** the admin clicks Cancel or presses Esc
- **THEN** the modal closes
- **AND** no request is fired
- **AND** the tag list is unchanged

### Validation errors in modal

- **WHEN** the admin submits an empty name
- **AND** the backend returns `400` with `field: "name"`
- **THEN** the error is rendered below the name input
- **AND** the modal stays open

### Archived tags also editable

- **WHEN** the tag is archived
- **THEN** the Edit action is still available (admins can rename archived tags)
- **AND** a visual indicator shows the archived state inside the modal

### Name uniqueness

- **WHEN** the admin renames a tag to a name already used in the workspace
- **THEN** the backend returns `409` with `code: "TAG_NAME_TAKEN"`, `field: "name"`
- **AND** the error surfaces in the modal

### Authorization enforced server-side

- **WHEN** a non-admin somehow fires the PATCH request (e.g. via dev tools)
- **THEN** the backend returns 403
- **AND** the frontend surfaces a generic "Not authorized" toast

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| Non-admin bypasses frontend hide | Backend authorization is the real gate — unchanged |
| Concurrent edit overwrites another admin's change | Low risk (workspace admin edits are rare); not adding ETags in this EP. If it becomes a problem, add `If-Match` later |
| XSS via tag name in list rendering | Tag names are rendered via React (auto-escaped); no `dangerouslySetInnerHTML` |
| Stale list after edit (F-3 again) | Explicit coverage: `useTags` refreshes the affected tag from the PATCH response |

## Out of Scope

- Bulk edit of multiple tags
- Edit history / audit log UI (EP-07 timeline already covers via comments/versions)
- Renaming tags from the tag chip inline in a work item
- Moving a tag between workspaces
