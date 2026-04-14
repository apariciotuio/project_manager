# Specification — US-040, US-041
# Structured Specification Generation & Manual Editing

## US-040 — Generate Structured Specification

### Overview

Transform element content (raw text, clarification conversation history, EP-02 captured input) into an
organized set of editable sections. Section layout is determined by element type. The operation is
idempotent: calling generate on an element that already has a specification merges new content into
existing sections rather than wiping them.

---

### Scenarios

#### SC-040-01: First-time generation on a Draft element

WHEN an authenticated user requests specification generation for a work item in `Draft` state that has no
existing specification
THEN the backend creates one `work_item_section` row per section defined for that element type
AND each section `content` is populated from the element's raw text and conversation history via the
LLM adapter (EP-03 integration)
AND the section `order` follows the canonical ordering for that element type
AND the specification `generation_source` is recorded as `llm`
AND the work item `state` remains unchanged (generation does not auto-advance state)
AND the response includes the full section list with `id`, `section_type`, `content`, `order`,
`is_required`, and `version`

#### SC-040-02: Generation on element with existing sections (re-generation)

WHEN a user requests re-generation on a work item that already has sections
THEN existing section content is updated in-place, preserving section `id` values
AND a new version snapshot is created before overwriting (version increment per section)
AND sections that were manually edited (`generation_source = manual`) are NOT overwritten unless the
user explicitly passes `force: true` in the request body
AND the response body includes a `skipped_sections` array listing section IDs that were protected

#### SC-040-03: Generation with no source content

WHEN a user requests specification generation for an element whose raw text AND conversation history are
both empty
THEN the backend returns HTTP 422 with error code `SPEC_GENERATION_NO_CONTENT`
AND no sections are created or modified

#### SC-040-04: Section structure adapts to element type

WHEN a specification is generated for a `Bug` element
THEN sections include: `summary`, `steps_to_reproduce`, `expected_behavior`, `actual_behavior`,
`environment`, `impact`, `acceptance_criteria`
AND sections `objective`, `business_value`, `scope` are NOT included

WHEN a specification is generated for a `User Story` element
THEN sections include: `summary`, `context`, `objective`, `acceptance_criteria`, `scope`,
`dependencies`, `risks`, `notes`
AND section `steps_to_reproduce` is NOT included

WHEN a specification is generated for an `Initiative` element
THEN sections include: `summary`, `business_value`, `objective`, `scope`, `success_metrics`,
`dependencies`, `risks`, `stakeholders`, `notes`

WHEN a specification is generated for a `Task` element
THEN sections include: `summary`, `objective`, `steps`, `acceptance_criteria`, `dependencies`, `notes`

WHEN a specification is generated for a `Spike` element
THEN sections include: `summary`, `objective`, `context`, `questions_to_answer`, `approach`,
`time_box`, `output_definition`, `notes`

WHEN a specification is generated for an `Epic` element
THEN sections include: `summary`, `business_value`, `objective`, `scope`, `user_stories_breakdown`,
`success_metrics`, `dependencies`, `risks`, `stakeholders`, `notes`

WHEN a specification is generated for a `Sub-task` element
THEN sections include: `summary`, `objective`, `steps`, `acceptance_criteria`, `parent_context`, `notes`

WHEN a specification is generated for a `Requirement` element
THEN sections include: `summary`, `context`, `objective`, `functional_requirements`,
`non_functional_requirements`, `acceptance_criteria`, `dependencies`, `risks`, `notes`

#### SC-040-05: Concurrent generation requests

WHEN two generation requests are submitted simultaneously for the same work item
THEN the backend processes the first request and rejects the second with HTTP 409 and error code
`SPEC_GENERATION_IN_PROGRESS`
AND a `retry_after` hint is included in the response

---

## US-041 — Edit Specification Manually

### Overview

Users can edit individual sections. Every save triggers a version snapshot. Partial saves (one section at
a time) are supported. Bulk section updates are also allowed via a single PATCH request.

---

### Scenarios

#### SC-041-01: Edit a single section

WHEN an authenticated user submits a PATCH to `/api/v1/work-items/:id/sections/:section_id` with a
`content` body
THEN the section `content` is updated
AND a version snapshot of the section's previous content is stored with `created_at` and `created_by`
AND the section `generation_source` is set to `manual`
AND the section `updated_at` and `updated_by` fields are updated
AND the response returns the updated section with `version` incremented by 1

#### SC-041-02: Edit attempt by non-owner

WHEN a user who is NOT the work item owner and does NOT have `editor` role submits a PATCH to a section
THEN the backend returns HTTP 403 with error code `SPEC_EDIT_FORBIDDEN`
AND no section is modified

#### SC-041-03: Edit a section with empty content

WHEN a user submits a PATCH with `content` set to an empty string on a section marked `is_required: true`
THEN the backend returns HTTP 422 with error code `SPEC_SECTION_REQUIRED_EMPTY`
AND the section is not modified

WHEN a user submits a PATCH with `content` set to an empty string on a section marked `is_required: false`
THEN the section content is updated to empty string
AND a version snapshot is created as normal

#### SC-041-04: Bulk section update

WHEN a user submits a PATCH to `/api/v1/work-items/:id/sections` with an array of `{id, content}` objects
THEN all sections in the array are updated atomically within a single transaction
AND each section gets its own version snapshot
AND if any section in the batch fails validation the entire batch is rejected with HTTP 422
AND the error response identifies which section ID failed and why

#### SC-041-05: Version history retrieval

WHEN a user requests GET `/api/v1/work-items/:id/sections/:section_id/versions`
THEN the response includes the full version history sorted by `version` descending
AND each entry includes `version`, `content`, `created_at`, `created_by`, and `generation_source`

#### SC-041-06: Revert section to a prior version

WHEN a user submits a PATCH to `/api/v1/work-items/:id/sections/:section_id` with a `revert_to_version`
field
THEN the section content is replaced with the content from that version
AND a new version snapshot is created with `generation_source: revert` and a reference to the source
version number
AND the response returns the restored content with the new version number

#### SC-041-07: Section order reordering

WHEN a user submits a PATCH to `/api/v1/work-items/:id/sections` with updated `order` values only
THEN the section display order is updated
AND no version snapshots are created (order changes do not count as content versions)
AND the response confirms new ordering

---

## Section Type Reference

| section_type              | Bug | Story | Epic | Initiative | Task | Sub-task | Spike | Requirement |
|---------------------------|-----|-------|------|------------|------|----------|-------|-------------|
| summary                   |  R  |   R   |  R   |     R      |  R   |    R     |   R   |      R      |
| context                   |     |   O   |      |            |      |          |   O   |      O      |
| objective                 |     |   R   |  R   |     R      |  R   |    R     |   R   |      R      |
| business_value            |     |       |  R   |     R      |      |          |       |             |
| scope                     |     |   O   |  R   |     R      |      |          |       |             |
| acceptance_criteria       |  R  |   R   |      |            |  R   |    R     |       |      R      |
| steps_to_reproduce        |  R  |       |      |            |      |          |       |             |
| expected_behavior         |  R  |       |      |            |      |          |       |             |
| actual_behavior           |  R  |       |      |            |      |          |       |             |
| environment               |  O  |       |      |            |      |          |       |             |
| impact                    |  O  |       |      |            |      |          |       |             |
| steps                     |     |       |      |            |  R   |    R     |       |             |
| questions_to_answer       |     |       |      |            |      |          |   R   |             |
| approach                  |     |       |      |            |      |          |   O   |             |
| time_box                  |     |       |      |            |      |          |   R   |             |
| output_definition         |     |       |      |            |      |          |   R   |             |
| user_stories_breakdown    |     |       |  O   |            |      |          |       |             |
| success_metrics           |     |       |  O   |     O      |      |          |       |             |
| functional_requirements   |     |       |      |            |      |          |       |      R      |
| non_functional_requirements|    |       |      |            |      |          |       |      O      |
| dependencies              |     |   O   |  O   |     O      |  O   |          |       |      O      |
| risks                     |     |   O   |  O   |     O      |      |          |       |      O      |
| stakeholders              |     |       |  O   |     O      |      |          |       |             |
| parent_context            |     |       |      |            |      |    O     |       |             |
| notes                     |  O  |   O   |  O   |     O      |  O   |    O     |   O   |      O      |

Legend: R = Required, O = Optional, blank = not included
