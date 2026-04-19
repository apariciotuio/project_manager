# Spec: Completion Rollup
# US-144

## Scope

`CompletionRollupService` computes a percentage-complete figure for any work item based on the states of its direct children. The result is cached in Redis and invalidated whenever a descendant's state changes. This spec defines the formula, cache behaviour, and display rules.

---

## Rollup Formula

Completion is computed over **direct children only** per level; each parent's rollup aggregates its children's rollup values (recursive by nature, cached bottom-up).

State weights:

| State | Contribution |
|---|---|
| `ready` | 1.0 (100%) |
| `exported` | 1.0 (100%) |
| `partially_validated` | 0.5 (50%) |
| `in_review` | 0.25 (25%) |
| `in_clarification` | 0.1 (10%) |
| `changes_requested` | 0.1 (10%) |
| `draft` | 0.0 (0%) |

Formula:

```
rollup_percent = round(
    (sum(weight(child.state) for child in direct_children) / len(direct_children)) * 100
)
```

If a child itself has children, its effective contribution uses its own cached `rollup_percent` instead of its raw state weight (parent rollup = average of children rollups). This enables bottom-up propagation without full tree traversal on every update.

---

## Scenario Group 1: Basic rollup computation

### Scenario 1.1: All children in draft

WHEN an epic has 3 children all in `draft` state
THEN `GET /api/v1/work-items/:id/rollup` returns `{"rollup_percent": 0}`

### Scenario 1.2: All children in ready

WHEN an epic has 3 children all in `ready` state
THEN the rollup returns `{"rollup_percent": 100}`

### Scenario 1.3: Mixed states

WHEN an epic has 4 children:
- 2 in `ready` (weight 1.0 each)
- 1 in `in_clarification` (weight 0.1)
- 1 in `draft` (weight 0.0)
THEN rollup = round((1.0 + 1.0 + 0.1 + 0.0) / 4 * 100) = round(52.5) = 53
AND the rollup returns `{"rollup_percent": 53}`

### Scenario 1.4: Single child

WHEN a milestone has exactly one child epic in `in_review`
THEN rollup = round(0.25 * 100) = 25
AND the rollup returns `{"rollup_percent": 25}`

### Scenario 1.5: No children (leaf node)

WHEN a work item has no children
THEN `GET /api/v1/work-items/:id/rollup` returns `{"rollup_percent": null}`
AND the API does not error

### Scenario 1.6: Rollup for milestone aggregates child epics' rollups

WHEN a milestone has 2 child epics:
- Epic A has `rollup_percent = 80`
- Epic B has `rollup_percent = 20`
THEN the milestone rollup = round((80 + 20) / 2) = 50
AND the rollup returns `{"rollup_percent": 50}`

---

## Scenario Group 2: Cache behaviour

### Scenario 2.1: Rollup is served from Redis cache on repeat read

WHEN `GET /api/v1/work-items/:id/rollup` is called twice in succession
THEN the second call is served entirely from Redis cache key `rollup:{work_item_id}`
AND no database query is made for the second call
AND both calls return the same value

### Scenario 2.2: Cache is invalidated when a direct child changes state

WHEN a child work item transitions state (via `POST /work-items/:id/transitions`)
THEN the domain event `work_item.state_changed` triggers a Celery task `invalidate_rollup_cache`
AND the Celery task deletes Redis key `rollup:{parent_work_item_id}`
AND the Celery task also deletes keys for all ancestors: `rollup:{grandparent_id}`, etc., up the materialized path chain
AND the next read recomputes and re-caches

### Scenario 2.3: Cache is invalidated when a child is added or removed

WHEN a new work item is created with `parent_work_item_id = X`
THEN Redis key `rollup:{X}` and all ancestor keys are invalidated immediately (same Celery task pattern)

WHEN a work item's parent is changed (reparented)
THEN Redis keys for both the old parent and the new parent (and their respective ancestor chains) are invalidated

WHEN a work item is soft-deleted
THEN Redis keys for its former parent and all ancestors are invalidated

### Scenario 2.4: Cache TTL

WHEN a rollup is computed and cached
THEN the Redis key TTL is 24 hours
AND the key is invalidated before TTL expiry whenever state changes (Scenario 2.2)

### Scenario 2.5: Cache miss — rollup is recomputed on demand

WHEN the Redis key `rollup:{work_item_id}` does not exist (first access or post-invalidation)
THEN `CompletionRollupService.compute(work_item_id)` queries direct children from DB
AND aggregates their cached rollup values (or their state weights for leaves)
AND writes the result to Redis
AND returns the computed value

---

## Scenario Group 3: API endpoint

### Scenario 3.1: GET rollup for a work item

WHEN a user sends `GET /api/v1/work-items/:id/rollup`
THEN the server responds 200 with:

```json
{
  "data": {
    "work_item_id": "<uuid>",
    "rollup_percent": 67,
    "child_count": 9,
    "computed_at": "2026-04-13T10:00:00Z",
    "cached": true
  }
}
```

AND `cached = false` when the value was freshly computed
AND `computed_at` reflects the cache write time

### Scenario 3.2: Rollup included in tree node response

WHEN `GET /api/v1/projects/:project_id/hierarchy` is called
THEN each tree node's `rollup_percent` field reflects the cached rollup
AND nodes with no children have `rollup_percent: null`

### Scenario 3.3: Rollup endpoint respects workspace scoping

WHEN a user requests rollup for a work item in a different workspace
THEN the server responds 403
AND no data is returned

---

## Scenario Group 4: Display rules (frontend contract)

### Scenario 4.1: Display threshold for RollupBadge

WHEN `rollup_percent` is null (leaf node or never computed)
THEN the RollupBadge component is not rendered

WHEN `rollup_percent` is 0
THEN the badge shows "0%" with a neutral colour (gray)

WHEN `rollup_percent` is between 1 and 99
THEN the badge shows the percentage with an in-progress colour (blue)

WHEN `rollup_percent` is 100
THEN the badge shows "100%" with a completion colour (green)

### Scenario 4.2: Stale rollup display

WHEN the cache has been invalidated and a fresh value has not yet been computed (async Celery lag)
THEN the UI shows the last known value with a "recalculating" indicator
AND the frontend polls `GET /work-items/:id/rollup` every 5 seconds until `cached = true` with a fresh `computed_at`
AND polling stops after 3 attempts (fail-silent: show last known value)

---

## Rollup Invalidation Chain

Given the materialized path `"<A>.<B>.<C>"` on item C (A is root, B is mid, C is leaf):

WHEN C's state changes
THEN invalidate: `rollup:{C's parent id}` → traverse materialized path → invalidate `rollup:{B}`, `rollup:{A}`
AND the invalidation reads the materialized path segments from the event payload (no additional DB query required)
AND invalidation is idempotent (deleting a non-existent key is a no-op)
