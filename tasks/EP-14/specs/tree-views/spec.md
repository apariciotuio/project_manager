# Spec: Hierarchy Tree Views and Filters
# US-142, US-145

## Scope

Defines the API shape for tree retrieval, pagination strategy for large trees, ancestor chain (breadcrumb), and the "filter by ancestor" capability used in list views (EP-09 integration).

---

## US-142 — View hierarchy tree: milestones → epics → stories per project

### Scenario 1: Retrieve full project hierarchy tree

WHEN a user sends `GET /api/v1/projects/:project_id/hierarchy`
AND the project has milestones, epics under milestones, and stories under epics
THEN the server responds 200
AND the response body has shape:

```json
{
  "data": {
    "roots": [
      {
        "id": "<milestone-uuid>",
        "type": "milestone",
        "title": "Q2 Launch",
        "state": "draft",
        "rollup_percent": 42,
        "children": [
          {
            "id": "<epic-uuid>",
            "type": "initiative",
            "title": "New onboarding flow",
            "state": "in_clarification",
            "rollup_percent": 60,
            "children": [
              {
                "id": "<story-uuid>",
                "type": "story",
                "title": "User can register via email",
                "state": "ready",
                "rollup_percent": 100,
                "children": []
              }
            ]
          }
        ]
      }
    ],
    "unparented": [
      {
        "id": "<task-uuid>",
        "type": "task",
        "title": "Orphan task",
        "state": "draft",
        "rollup_percent": null,
        "children": []
      }
    ],
    "meta": {
      "root_count": 3,
      "total_nodes": 47,
      "truncated": false
    }
  }
}
```

AND `roots` contains only items with `parent_work_item_id IS NULL` and type `milestone` (or top-level items of any type with no parent)
AND `unparented` contains non-milestone items with `parent_work_item_id IS NULL`
AND `children` arrays are sorted by `due_date ASC NULLS LAST`, then `created_at ASC`
AND `rollup_percent` is null for leaf nodes with no children

### Scenario 2: Project with no milestones — flat list returned as unparented

WHEN a project has only legacy work items with no `parent_work_item_id`
THEN `roots` is empty
AND `unparented` contains all top-level items
AND `meta.total_nodes` reflects the full count

### Scenario 3: Tree is truncated for large projects

WHEN a project has more than 200 root-level items
THEN the response includes only the first 200 root items
AND `meta.truncated = true`
AND `meta.root_count` reflects the actual total
AND a `next_cursor` token is provided for pagination

### Scenario 4: Paginate roots

WHEN a user sends `GET /api/v1/projects/:project_id/hierarchy?cursor=<token>&limit=50`
THEN the server returns the next page of root items
AND each page's child subtrees are fully expanded (not paginated)
AND the response includes a `next_cursor` if more roots remain

### Scenario 5: Tree depth is bounded

WHEN the stored tree has more than 10 levels of nesting
THEN the API returns items up to depth 10
AND deeper nodes are omitted
AND `meta.depth_truncated = true` is included in the response

### Scenario 6: Workspace scoping enforced

WHEN a user requests a hierarchy for a project that belongs to a different workspace
THEN the server responds 403
AND no data is returned

---

## Direct Children Endpoint

### Scenario 7: Retrieve direct children of a work item

WHEN a user sends `GET /api/v1/work-items/:id/children`
THEN the server responds 200
AND the response contains only direct children (`parent_work_item_id = :id`)
AND results are sorted by `due_date ASC NULLS LAST`, then `created_at ASC`
AND a standard cursor pagination envelope is returned (consistent with EP-09)

### Scenario 8: Item with no children

WHEN `GET /api/v1/work-items/:id/children` is requested for a leaf node
THEN the server responds 200
AND `data` is an empty array
AND `meta.total = 0`

---

## US-145 — Filter list views by ancestor (all descendants of X)

### Scenario 9: Filter by direct parent

WHEN a user requests `GET /api/v1/projects/:project_id/work-items?parent_id=<epic-uuid>`
THEN the server returns only work items where `parent_work_item_id = <epic-uuid>`
AND pagination, sorting, and other filters from EP-09 still apply

### Scenario 10: Filter by ancestor (all descendants)

WHEN a user requests `GET /api/v1/projects/:project_id/work-items?ancestor_id=<milestone-uuid>`
THEN the server returns all work items whose `materialized_path` contains `<milestone-uuid>` (LIKE query: `materialized_path LIKE '%<milestone-uuid>%'`)
AND direct children AND grandchildren (any depth) are included
AND results are paginated per EP-09 cursor pagination
AND the milestone item itself is NOT included in results

### Scenario 11: Ancestor filter combined with type filter

WHEN a user requests `GET /api/v1/projects/:project_id/work-items?ancestor_id=<milestone-uuid>&type=story`
THEN only `story` type descendants of that milestone are returned
AND pagination applies

### Scenario 12: Ancestor filter combined with state filter

WHEN a user requests `?ancestor_id=<epic-uuid>&state=ready`
THEN only descendants in `ready` state are returned

### Scenario 13: Ancestor filter with non-existent ancestor

WHEN a user supplies an `ancestor_id` that does not exist or is soft-deleted
THEN the server responds 200 with an empty result set
AND `meta.total = 0`

---

## Ancestors Endpoint (Breadcrumb)

### Scenario 14: Retrieve ancestor chain for a work item

WHEN a user sends `GET /api/v1/work-items/:id/ancestors`
THEN the server responds 200
AND the response contains the ordered ancestor chain from root to direct parent:

```json
{
  "data": {
    "ancestors": [
      { "id": "<milestone-uuid>", "type": "milestone", "title": "Q2 Launch" },
      { "id": "<epic-uuid>",      "type": "initiative", "title": "Onboarding flow" }
    ],
    "breadcrumb": "Q2 Launch > Onboarding flow > [current item title]"
  }
}
```

AND the chain is built from `materialized_path` — O(1) lookup without recursion
AND the last entry is the direct parent (not the item itself)

### Scenario 15: Root item (no parent) returns empty ancestor chain

WHEN `GET /api/v1/work-items/:id/ancestors` is called for an item with `parent_work_item_id IS NULL`
THEN the server responds 200
AND `ancestors` is `[]`
AND `breadcrumb` contains only the item's title

### Scenario 16: Ancestor chain is consistent with materialized path

WHEN a work item has `materialized_path = "<A-uuid>.<B-uuid>"`
THEN the `/ancestors` endpoint returns items in order `[A, B]`
AND the UUIDs match the materialized path segments exactly

---

## Tree API Response Shape — Summary

All tree nodes share this minimal shape (full work item fields available via `/work-items/:id`):

```typescript
interface TreeNode {
  id: string;
  type: WorkItemType;
  title: string;
  state: WorkItemState;
  rollup_percent: number | null;  // null for leaves or when no rollup computed yet
  due_date: string | null;
  children: TreeNode[];           // empty array for leaves
}
```

`TreeQueryService` uses the materialized path for ancestor queries (`LIKE`) and a `WITH RECURSIVE` CTE for full subtree reads. Both strategies are available; the CTE is used for the full project hierarchy, the LIKE query for ancestor filtering in list endpoints.
