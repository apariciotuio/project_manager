# EP-02 — Capture, Drafts & Templates

## Business Need

The system must allow users to capture ambiguous work quickly — free text, partial info, rough ideas — without forcing structure upfront. Drafts persist automatically. Templates per element type provide starting structure without rigidity. The original input must always be preserved.

## Objectives

- Create work items from free text with minimal friction
- Support type selection at creation
- Auto-save drafts with partial data
- Preserve original input verbatim
- Apply templates based on element type
- Show functional header (state, owner, completeness) from creation

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-020 | Create element from free text | Must |
| US-021 | Save and resume drafts | Must |
| US-022 | Use templates by type | Should |
| US-023 | Show functional header from creation | Must |

## Acceptance Criteria

- WHEN a user starts creation THEN they can enter free text and select a type
- WHEN the user leaves mid-creation THEN the draft persists and is resumable
- WHEN a template exists for the selected type THEN it pre-populates structure
- WHEN the element is created THEN the original input is preserved separately from any structured content
- WHEN viewing any element THEN the header shows type, owner, state, and initial completeness
- AND the element appears in workspace listings immediately after creation
- AND the creator is the default owner unless reassigned

## Technical Notes

- Form with auto-save (debounced persistence)
- Templates as configurable JSON/structured data per type
- Original input stored as immutable field
- Creation event triggers notifications if configured

## Dependencies

- EP-00 (auth)
- EP-01 (work item model, states, ownership)

## Complexity Assessment

**Medium** — Straightforward CRUD with auto-save and template logic. The main complexity is in preserving original input while allowing structured editing.

## Risks

- Auto-save conflicts if multiple tabs
- Template changes affecting existing drafts
