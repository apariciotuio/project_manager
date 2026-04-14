# Spec: Type-Parent Validation Rules
# US-143

## Scope

`HierarchyValidator` is the single authoritative source of type-compatibility truth. Every create and update path calls it. This spec defines the full rule table, rejection behaviour, and edge cases.

---

## Type Compatibility Table

| Child Type | Allowed Parent Types | Notes |
|---|---|---|
| `milestone` | none | Always top-level. Parent assignment rejected unconditionally. |
| `epic` | `milestone` | Maps to `initiative` type in existing enum where applicable. |
| `initiative` | `milestone` | Treated identically to epic in hierarchy rules. |
| `story` | `epic`, `initiative` | User-facing feature. |
| `requirement` | `epic`, `initiative` | Pre-existing type, same parent rules as story. |
| `enhancement` | `epic`, `initiative` | Pre-existing type, same parent rules as story. |
| `task` | any or null | Execution unit. Flexible placement. |
| `bug` | any or null | Same as task. |
| `idea` | any or null | Same as task. |
| `spike` | any or null | Same as task. |
| `business_change` | any or null | Same as task. |

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

## Scenario Group 2: Epic / Initiative parent rules

### Scenario 2.1: Epic created with milestone parent — valid

WHEN a user creates an `epic` with `parent_work_item_id` referencing a `milestone`
THEN the server responds 201
AND `parent_work_item_id` is set

### Scenario 2.2: Epic created with no parent — valid

WHEN a user creates an `epic` with no `parent_work_item_id`
THEN the server responds 201
AND the epic is top-level

### Scenario 2.3: Epic created with epic parent — rejected

WHEN a user creates an `epic` with `parent_work_item_id` referencing another `epic`
THEN the server responds 422
AND the error code is `HIERARCHY_INVALID_PARENT_TYPE`
AND the error details include `{"child_type": "epic", "allowed_parent_types": ["milestone"]}`

### Scenario 2.4: Epic created with story parent — rejected

WHEN a user creates an `epic` with `parent_work_item_id` referencing a `story`
THEN the server responds 422
AND the error code is `HIERARCHY_INVALID_PARENT_TYPE`

### Scenario 2.5: Initiative follows the same rules as epic

WHEN the same scenarios (2.1–2.4) are repeated for `initiative` type
THEN results are identical to epic

---

## Scenario Group 3: Story / Requirement / Enhancement parent rules

### Scenario 3.1: Story created with epic parent — valid

WHEN a user creates a `story` with `parent_work_item_id` referencing an `epic`
THEN the server responds 201

### Scenario 3.2: Story created with initiative parent — valid

WHEN a user creates a `story` with `parent_work_item_id` referencing an `initiative`
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

WHEN the same scenarios (3.1–3.5) are repeated for `requirement` and `enhancement` types
THEN results are identical to story

---

## Scenario Group 4: Flexible types (task, bug, idea, spike, business_change)

### Scenario 4.1: Task with milestone parent — valid

WHEN a user creates a `task` with `parent_work_item_id` referencing a `milestone`
THEN the server responds 201

### Scenario 4.2: Task with epic parent — valid

WHEN a user creates a `task` with `parent_work_item_id` referencing an `epic`
THEN the server responds 201

### Scenario 4.3: Task with story parent — valid

WHEN a user creates a `task` with `parent_work_item_id` referencing a `story`
THEN the server responds 201

### Scenario 4.4: Task with task parent — valid

WHEN a user creates a `task` with `parent_work_item_id` referencing another `task`
THEN the server responds 201

### Scenario 4.5: Task with no parent — valid

WHEN a user creates a `task` without `parent_work_item_id`
THEN the server responds 201

### Scenario 4.6: Bug, idea, spike, business_change follow the same permissive rules as task

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
