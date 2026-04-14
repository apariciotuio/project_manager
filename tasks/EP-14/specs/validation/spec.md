# Spec: Type-Parent Validation Rules
# US-143

## Scope

`HierarchyValidator` is the single authoritative source of type-compatibility truth. Every create and update path calls it. This spec defines the full rule table, rejection behaviour, and edge cases.

---

## Type Compatibility Table

| Child Type | Allowed Parent Types | Notes |
|---|---|---|
| `milestone` | none | Always top-level. Parent assignment rejected unconditionally. |
| `iniciativa` | `milestone` | Iniciativa-level strategic container. |
| `story` | `iniciativa` | User-facing feature. |
| `requisito` | `iniciativa`, `story` | Same parent rules as story plus nested under story. |
| `mejora` | `iniciativa`, `story` | Same rules as requisito. |
| `tarea` | any or null | Execution unit. Flexible placement. |
| `bug` | any or null | Same as tarea. |
| `idea` | any or null | Same as tarea. |
| `spike` | any or null | Same as tarea. |
| `cambio` | any or null | Same as tarea. |

"any" = any non-deleted work item in the same workspace+project, regardless of its type.
"null" = no parent; item becomes top-level under its project.

---

## Scenario Group 1: Milestone parent assignment blocked

### Scenario 1.1: Attempt to assign a parent to a milestone at create

WHEN a user submits `POST /api/v1/work-items` with `"type": "milestone"` and a non-null `parent_work_item_id`
THEN the server responds 422
AND the error code is `HIERARCHY_INVALID_PARENT_TYPE`
AND the error details include `{"child_type": "milestone", "parent_type": "<actual-type>", "allowed_parent_types": []}`
AND no item is created

### Scenario 1.2: Attempt to reparent a milestone via PATCH

WHEN a user submits `PATCH /api/v1/work-items/:id` for a milestone with a non-null `parent_work_item_id`
THEN the server responds 422
AND the error code is `HIERARCHY_INVALID_PARENT_TYPE`
AND the milestone is not modified

---

## Scenario Group 2: Iniciativa / Initiative parent rules

### Scenario 2.1: Iniciativa created with milestone parent — valid

WHEN a user creates an `iniciativa` with `parent_work_item_id` referencing a `milestone`
THEN the server responds 201
AND `parent_work_item_id` is set

### Scenario 2.2: Iniciativa created with no parent — valid

WHEN a user creates an `iniciativa` with no `parent_work_item_id`
THEN the server responds 201
AND the epic is top-level

### Scenario 2.3: Iniciativa created with epic parent — rejected

WHEN a user creates an `iniciativa` with `parent_work_item_id` referencing another `iniciativa`
THEN the server responds 422
AND the error code is `HIERARCHY_INVALID_PARENT_TYPE`
AND the error details include `{"child_type": "epic", "allowed_parent_types": ["milestone"]}`

### Scenario 2.4: Iniciativa created with story parent — rejected

WHEN a user creates an `iniciativa` with `parent_work_item_id` referencing a `story`
THEN the server responds 422
AND the error code is `HIERARCHY_INVALID_PARENT_TYPE`

### Scenario 2.5: Initiative follows the same rules as epic

WHEN the same scenarios (2.1–2.4) are repeated for `iniciativa` type
THEN results are identical to epic

---

## Scenario Group 3: Story / Requirement / Enhancement parent rules

### Scenario 3.1: Story created with epic parent — valid

WHEN a user creates a `story` with `parent_work_item_id` referencing an `iniciativa`
THEN the server responds 201

### Scenario 3.2: Story created with initiative parent — valid

WHEN a user creates a `story` with `parent_work_item_id` referencing an `iniciativa`
THEN the server responds 201

### Scenario 3.3: Story created with no parent — valid

WHEN a user creates a `story` without `parent_work_item_id`
THEN the server responds 201 with `parent_work_item_id = null`

### Scenario 3.4: Story created with milestone parent — rejected

WHEN a user creates a `story` with `parent_work_item_id` referencing a `milestone`
THEN the server responds 422
AND the error code is `HIERARCHY_INVALID_PARENT_TYPE`
AND the error details include `{"child_type": "story", "allowed_parent_types": ["epic", "initiative"]}`

### Scenario 3.5: Story created with story parent — rejected

WHEN a user creates a `story` with `parent_work_item_id` referencing another `story`
THEN the server responds 422
AND the error code is `HIERARCHY_INVALID_PARENT_TYPE`

### Scenario 3.6: Requirement and enhancement follow the same rules as story

WHEN the same scenarios (3.1–3.5) are repeated for `requisito` and `mejora` types
THEN results are identical to story

---

## Scenario Group 4: Flexible types (task, bug, idea, spike, cambio)

### Scenario 4.1: Task with milestone parent — valid

WHEN a user creates a `tarea` with `parent_work_item_id` referencing a `milestone`
THEN the server responds 201

### Scenario 4.2: Task with epic parent — valid

WHEN a user creates a `tarea` with `parent_work_item_id` referencing an `iniciativa`
THEN the server responds 201

### Scenario 4.3: Task with story parent — valid

WHEN a user creates a `tarea` with `parent_work_item_id` referencing a `story`
THEN the server responds 201

### Scenario 4.4: Task with task parent — valid

WHEN a user creates a `tarea` with `parent_work_item_id` referencing another `tarea`
THEN the server responds 201

### Scenario 4.5: Task with no parent — valid

WHEN a user creates a `tarea` without `parent_work_item_id`
THEN the server responds 201

### Scenario 4.6: Bug, idea, spike, cambio follow the same permissive rules as task

WHEN any of these types are created with any non-deleted parent in the same workspace+project
THEN the server responds 201

---

## Scenario Group 5: Cycle prevention

### Scenario 5.1: Item cannot be its own parent

WHEN a user submits `PATCH /api/v1/work-items/:id` with `"parent_work_item_id": "<same-id>"`
THEN the server responds 422
AND the error code is `HIERARCHY_CYCLE_DETECTED`
AND the error details include `{"cycle_path": ["<id>"]}`

### Scenario 5.2: Cycle via existing descendants blocked

WHEN item A is the parent of item B, and a user attempts to set A's parent to B
THEN the server responds 422
AND the error code is `HIERARCHY_CYCLE_DETECTED`
AND the error details include the cycle path: `["A", "B", "A"]`

### Scenario 5.3: Deep cycle blocked (A→B→C, attempt C→A)

WHEN A is parent of B, B is parent of C, and a user attempts to set C's parent to A
THEN the server responds 422
AND the error code is `HIERARCHY_CYCLE_DETECTED`

Cycle detection uses materialized path: if the candidate parent's `materialized_path` contains the item's own `id`, a cycle exists. This is O(1) — no recursive query required.

---

## Scenario Group 6: Validator is pure — no I/O side effects

### Scenario 6.1: Validator called with valid combination returns no error

WHEN `HierarchyValidator.validate_parent(child_type=STORY, parent_type=EPIC)` is called
THEN it returns `(True, None)`

### Scenario 6.2: Validator called with invalid combination returns error code

WHEN `HierarchyValidator.validate_parent(child_type=EPIC, parent_type=STORY)` is called
THEN it returns `(False, "HIERARCHY_INVALID_PARENT_TYPE")`

### Scenario 6.3: Validator called with None parent always returns valid (except milestone)

WHEN `HierarchyValidator.validate_parent(child_type=STORY, parent_type=None)` is called
THEN it returns `(True, None)`

WHEN `HierarchyValidator.validate_parent(child_type=MILESTONE, parent_type=None)` is called
THEN it returns `(True, None)`

---

## Error Codes Reference

| Code | HTTP Status | Meaning |
|---|---|---|
| `HIERARCHY_INVALID_PARENT_TYPE` | 422 | Parent type not in allowed set for child type |
| `HIERARCHY_CYCLE_DETECTED` | 422 | Assignment would create a cycle |
| `HIERARCHY_CROSS_WORKSPACE` | 422 | Parent belongs to a different workspace |
| `HIERARCHY_CROSS_PROJECT` | 422 | Parent belongs to a different project (same workspace) |
| `HIERARCHY_PARENT_NOT_FOUND` | 422 | Parent does not exist or is soft-deleted |
| `HIERARCHY_HAS_CHILDREN` | 409 | Delete blocked: item still has children |
