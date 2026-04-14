# Spec: Hierarchy Model — Types and Parent Assignment
# US-140, US-141

## Scope

Introduces `milestone` and `story` as first-class `WorkItemType` enum values, and adds `parent_work_item_id` to `work_items` so any work item can be hierarchically linked to a parent of a compatible type. `HierarchyValidator` enforces the type-compatibility rules at the domain layer before any persistence.

---

## US-140 — Add milestone and story as first-class work item types

### Scenario 1: Create a work item of type milestone

WHEN a user submits `POST /api/v1/work-items` with `"type": "milestone"`
THEN the server responds 201
AND the returned work item has `type = "milestone"`
AND `parent_work_item_id` is `null`
AND the item is persisted with `materialized_path = ""`

### Scenario 2: Create a work item of type story

WHEN a user submits `POST /api/v1/work-items` with `"type": "story"` and no `parent_work_item_id`
THEN the server responds 201
AND the returned work item has `type = "story"`
AND `parent_work_item_id` is `null`
AND `materialized_path = ""`

### Scenario 3: Legacy types remain valid after migration

WHEN a work item with type `idea`, `bug`, `enhancement`, `task`, `initiative`, `spike`, `business_change`, or `requirement` already exists in the database
THEN no migration alters its `type` value
AND reading that item returns the original type unchanged
AND all existing FSM transitions continue to work on legacy types

### Scenario 4: type enum constraint is enforced at DB level

WHEN a database INSERT is attempted with `type = "invalid_type"`
THEN the DB CHECK constraint `work_items_type_valid` rejects the row
AND no partial write occurs

---

## US-141 — Set parent work item when creating or editing a story/epic

### Scenario 1: Create a story with a valid epic parent

WHEN a user submits `POST /api/v1/work-items` with `"type": "story"` and `"parent_work_item_id": "<epic-uuid>"`
AND the referenced epic belongs to the same workspace and project
THEN the server responds 201
AND `parent_work_item_id` is set to the epic's UUID
AND `materialized_path` is computed as `"<epic-uuid>"` (single ancestor)
AND the epic's direct children count increases by 1

### Scenario 2: Create an epic with a milestone parent

WHEN a user submits `POST /api/v1/work-items` with `"type": "epic"` (mapped from `initiative`) and `"parent_work_item_id": "<milestone-uuid>"`
AND the referenced milestone belongs to the same workspace and project
THEN the server responds 201
AND `parent_work_item_id` is set to the milestone's UUID
AND `materialized_path` is `"<milestone-uuid>"`

### Scenario 3: Create a story as a child of an epic that is already a child of a milestone

WHEN a user creates a story whose parent epic has `materialized_path = "<milestone-uuid>"`
THEN the story's `materialized_path` is set to `"<milestone-uuid>.<epic-uuid>"`

### Scenario 4: Edit a work item to assign a parent (reparenting)

WHEN a user submits `PATCH /api/v1/work-items/:id` with `"parent_work_item_id": "<new-parent-uuid>"`
AND the new parent type is compatible per `HierarchyValidator`
AND the new parent is not the item itself or a descendant of the item
THEN the server responds 200
AND `parent_work_item_id` is updated
AND `materialized_path` is recomputed for the item and all its descendants atomically within a single transaction
AND domain event `work_item.parent_changed` is emitted

### Scenario 5: Edit a work item to remove its parent (detach)

WHEN a user submits `PATCH /api/v1/work-items/:id` with `"parent_work_item_id": null`
THEN the server responds 200
AND `parent_work_item_id` is set to null
AND `materialized_path` is reset to `""`
AND all descendants have their `materialized_path` recomputed to reflect the detachment

### Scenario 6: Parent must be in the same workspace

WHEN a user supplies a `parent_work_item_id` that exists in a different workspace
THEN the server responds 422
AND the error code is `HIERARCHY_CROSS_WORKSPACE`
AND no changes are persisted

### Scenario 7: Parent must exist (not soft-deleted)

WHEN a user supplies a `parent_work_item_id` pointing to a soft-deleted work item
THEN the server responds 422
AND the error code is `HIERARCHY_PARENT_NOT_FOUND`

### Scenario 8: Delete blocked when item has children

WHEN a user submits `DELETE /api/v1/work-items/:id`
AND the item has one or more children (`parent_work_item_id = id`)
THEN the server responds 409
AND the error code is `HIERARCHY_HAS_CHILDREN`
AND the error details include the count of direct children
AND no deletion occurs (`ON DELETE RESTRICT` at DB level enforces this as a last line of defence)

### Scenario 9: Parent assignment is workspace-scoped — cross-project parent within same workspace

WHEN a user supplies a `parent_work_item_id` that belongs to the same workspace but a different project
THEN the server responds 422
AND the error code is `HIERARCHY_CROSS_PROJECT`
AND no changes are persisted

---

## HierarchyValidator Contract

Pure function, no I/O.

```python
# domain/hierarchy/hierarchy_validator.py

VALID_PARENT_TYPES: dict[WorkItemType, frozenset[WorkItemType] | None] = {
    WorkItemType.MILESTONE:       None,           # no parent allowed
    WorkItemType.EPIC:            frozenset({WorkItemType.MILESTONE}),
    WorkItemType.INITIATIVE:      frozenset({WorkItemType.MILESTONE}),
    WorkItemType.STORY:           frozenset({WorkItemType.EPIC, WorkItemType.INITIATIVE}),
    WorkItemType.REQUIREMENT:     frozenset({WorkItemType.EPIC, WorkItemType.INITIATIVE}),
    WorkItemType.ENHANCEMENT:     frozenset({WorkItemType.EPIC, WorkItemType.INITIATIVE}),
    WorkItemType.TASK:            None,           # None = any type or no parent
    WorkItemType.BUG:             None,
    WorkItemType.IDEA:            None,
    WorkItemType.SPIKE:           None,
    WorkItemType.BUSINESS_CHANGE: None,
}

def validate_parent(
    child_type: WorkItemType,
    parent_type: WorkItemType | None,
) -> tuple[bool, str | None]:
    """Returns (is_valid, error_code | None)."""
```

`None` in `VALID_PARENT_TYPES` means the type accepts any parent type (or no parent).
`frozenset` means only those specific parent types are permitted.
Passing `parent_type=None` is always valid (detach is permitted for all types, except milestone where parent is already None).
