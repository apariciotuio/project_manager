# Type Preview Specs — EP-22

## US-222: Right panel shows type-specific template in editable preview

### Overview

From the first render of the SplitView, the right panel shows the work item's type-specific specification sections (EP-04) in editable mode. Sections are pre-populated with template defaults from EP-02 (when `template_id` is present) and/or with any pre-existing content stored in `work_item_sections`. No "preview mode → edit mode" toggle is needed — the editor is always live, consistent with the existing EP-04 `SpecificationSectionsEditor` behavior inside the current "Especificación" tab.

Rationale (proposal decision): there is no "read-only preview". The right panel is the authoring surface.

---

### Scenario: Editable sections render from the first paint

WHEN the SplitView mounts for a work item
THEN the right panel renders `SpecificationSectionsEditor` (the EP-04 component)
AND the sections are editable when the user has write access (owner or superadmin)
AND each section shows its label, required marker, generation source badge, and version

---

### Scenario: Pre-populated from template defaults for newly-created item

WHEN a work item is created with a `template_id` (EP-02 template was applied)
AND `SpecificationSectionsEditor` loads the sections
THEN each section content is pre-populated from the template's default content for that section_type
AND each section's `generation_source` is `template` (not `manual`, not `ai`)

---

### Scenario: Pre-populated from existing content for an existing item

WHEN a user opens an existing work item (not freshly created) with stored section content
THEN each section shows its latest persisted content
AND `generation_source` reflects its actual origin (`manual`, `ai`, `template`)

---

### Scenario: Section save goes through EP-04 patch endpoint

WHEN the user edits a section content
AND the EP-04 600ms debounce fires (or the textarea blurs)
THEN the frontend calls the existing EP-04 `PATCH /work-items/{id}/sections/{section_id}` endpoint with `{ content }`
AND a new section version is recorded by the backend (existing EP-04 behavior)
AND the UI shows the saving indicator, then the updated version number

---

### Scenario: Non-editable when user lacks write access

WHEN a viewer (not owner, not superadmin) opens the SplitView
THEN the right panel renders all sections in read-only mode (existing `canEdit=false` path)
AND textareas are disabled with the existing disabled styles
AND no PATCH requests are issued

---

### Scenario: No collision with the chat composer

WHEN the user is typing in a section on the right panel
AND an assistant response arrives on the left
THEN the section input retains focus and the user's keystrokes are never interrupted
AND no modal, toast, or global overlay appears over the right panel
AND only the suggestion-bridge UX (see `specs/suggestion-bridge/spec.md`) can cause a non-blocking in-place change to sections

---

### Scenario: Empty sections allowed

WHEN a section has no content and the user has not edited it yet
THEN the textarea renders empty with the placeholder text
AND no save is triggered until the user types

---

### Scenario: Type-specific sections only

WHEN the work item type is e.g. `bug`
THEN only the section_types configured by the EP-04 template for `bug` are rendered
AND sections configured for other types are NOT shown
