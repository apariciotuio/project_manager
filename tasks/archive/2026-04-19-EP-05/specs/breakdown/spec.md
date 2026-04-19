# EP-05 Breakdown Spec — US-050, US-051, US-052

## US-050 — Generate Tasks and Subtasks from Specification

**Actor**: Authenticated user with edit access to the work item.
**Precondition**: Work item has at least one non-empty `work_item_sections` row (EP-04 spec exists).

### Scenario 1: Generate breakdown for the first time

WHEN the user triggers POST `/api/v1/work-items/:id/tasks/generate`
THEN the system calls the LLM breakdown adapter with the full specification content
AND the adapter returns a structured list of tasks and subtasks
AND each task node is persisted in `task_nodes` with `work_item_id`, `title`, `description`, `order`, `parent_id` (null for root tasks), `section_id` pointing to the originating `work_item_sections` row, and `status = draft`
AND the response body contains the full task tree in hierarchical form
AND if no `task_nodes` existed for this work item before, the breakdown completeness dimension in EP-04 is invalidated from Redis

### Scenario 2: Re-generate when breakdown already exists

WHEN the user triggers POST `/api/v1/work-items/:id/tasks/generate` and `task_nodes` already exist for this work item
THEN the system returns HTTP 409 with error code `BREAKDOWN_ALREADY_EXISTS`
AND does not overwrite existing nodes
AND the response body includes a hint to use PATCH or the explicit replace flag

### Scenario 3: Generate with force-replace flag

WHEN the user triggers POST `/api/v1/work-items/:id/tasks/generate` with `{ "force": true }` in the request body
THEN the system deletes all existing `task_nodes` for the work item (cascades to `task_dependencies`)
AND re-generates and persists as in Scenario 1
AND the response includes `"replaced": true` in the data envelope

### Scenario 4: Specification is empty

WHEN the user triggers POST `/api/v1/work-items/:id/tasks/generate` and all spec sections have empty content
THEN the system returns HTTP 422 with error code `SPECIFICATION_EMPTY`
AND no task nodes are created

### Scenario 5: LLM call fails

WHEN the LLM adapter raises an exception or returns a non-parseable response
THEN the system rolls back any partial inserts
AND returns HTTP 502 with error code `BREAKDOWN_GENERATION_FAILED`
AND logs the raw LLM response for diagnostics

---

## US-051 — Edit, Split, Merge, and Reorder Tasks

**Actor**: Authenticated user with edit access to the work item.
**Precondition**: At least one `task_node` exists for the work item.

### Scenario 1: Rename a task

WHEN the user sends PATCH `/api/v1/tasks/:task_id` with `{ "title": "new title" }`
THEN the task node `title` is updated
AND `updated_at` is refreshed
AND the `section_id` foreign key is not modified

### Scenario 2: Update task description

WHEN the user sends PATCH `/api/v1/tasks/:task_id` with `{ "description": "..." }`
THEN the task node `description` is updated
AND all other fields, including `section_id` and `parent_id`, remain unchanged

### Scenario 3: Reorder tasks within the same parent

WHEN the user sends PATCH `/api/v1/work-items/:id/tasks/reorder` with `{ "ordered_ids": ["uuid-a", "uuid-b", "uuid-c"] }`
THEN the system validates all IDs belong to the same parent (or are all root-level)
AND reassigns `order` values to match the submitted sequence (1-indexed, gapless)
AND if any ID does not belong to the work item, returns HTTP 422 with `INVALID_TASK_IDS`
AND all `section_id` links are preserved unchanged

### Scenario 4: Split a task into two

WHEN the user sends POST `/api/v1/tasks/:task_id/split` with `{ "title_a": "...", "title_b": "...", "description_a": "...", "description_b": "..." }`
THEN the original task node is deleted
AND two new task nodes are created with the same `parent_id`, `work_item_id`, and `section_id` as the original
AND the new nodes are inserted at the original node's `order` position (first new node) and `order + 1` (second), shifting subsequent siblings
AND any `task_dependencies` referencing the original node are removed (dependencies do not auto-inherit to split nodes — user must re-add)
AND the response contains both new node representations
AND the `section_id` link is present on both new nodes

### Scenario 5: Split a task — missing required fields

WHEN the user sends POST `/api/v1/tasks/:task_id/split` with missing `title_a` or `title_b`
THEN the system returns HTTP 422 with field-level validation errors
AND no task nodes are created or deleted

### Scenario 6: Merge two or more tasks into one

WHEN the user sends POST `/api/v1/tasks/merge` with `{ "source_ids": ["uuid-a", "uuid-b"], "title": "...", "description": "..." }`
THEN the system validates all source IDs belong to the same parent and the same work item
AND a new task node is created with `parent_id` equal to the shared parent, `order` equal to the minimum order of the sources, and `status = draft`
AND the new node's `section_ids` is a deduplicated union of all source nodes' `section_id` values (stored in `task_node_section_links` join table — see design)
AND source nodes are deleted
AND any `task_dependencies` pointing to or from source nodes are removed
AND the response includes the new node with all linked `section_ids`

### Scenario 7: Merge across different parents

WHEN the user sends POST `/api/v1/tasks/merge` with `source_ids` belonging to different parents
THEN the system returns HTTP 422 with error code `MERGE_CROSS_PARENT_FORBIDDEN`
AND no mutations are performed

### Scenario 8: Change task status

WHEN the user sends PATCH `/api/v1/tasks/:task_id` with `{ "status": "in_progress" }`
THEN the system validates the transition is allowed (draft → in_progress → done; no skipping to done if blocked tasks exist)
AND updates `status`
AND if the task has unresolved blocking dependencies (all predecessor tasks not in `done` state), returns HTTP 422 with `TASK_BLOCKED`

---

## US-052 — Maintain Traceability Between Spec and Breakdown

**Actor**: Authenticated user with read access.

### Scenario 1: View spec origin from a task

WHEN the user sends GET `/api/v1/tasks/:task_id`
THEN the response includes `section_links`: a list of objects each with `section_id`, `section_type`, and `display_order` from the originating `work_item_sections` row(s)
AND for tasks created by the LLM generator, exactly one `section_link` is present (the source section)
AND for merged tasks, all contributing sections are listed

### Scenario 2: View all tasks referencing a section

WHEN the user sends GET `/api/v1/work-items/:id/sections/:section_id/tasks`
THEN the response lists all `task_nodes` that reference the given section
AND includes both direct (root) and subtask nodes
AND ordering follows `parent_id` then `order`

### Scenario 3: Traceability preserved after reorder

WHEN the user reorders tasks via the reorder endpoint (US-051, Scenario 3)
THEN subsequent GET on each task still returns the correct `section_links`
AND the section IDs are not affected by the order change

### Scenario 4: Traceability after manual task creation (no LLM origin)

WHEN the user sends POST `/api/v1/work-items/:id/tasks` with no `section_id` in the body
THEN the task is created with `section_links: []`
AND the response reflects the empty link list
AND the task is still valid and operational

### Scenario 5: Assign or update traceability link manually

WHEN the user sends PATCH `/api/v1/tasks/:task_id/section-links` with `{ "section_ids": ["uuid-x"] }`
THEN the system replaces the task's section links with the provided list
AND validates all section IDs belong to the same work item
AND if a section ID does not belong to the work item, returns HTTP 422 with `INVALID_SECTION_ID`
