# EP-14 — Technical Design
# Hierarchy Expansion: Milestones, Epics, Stories

---

## 1. Schema Amendment to EP-01's work_items

### Migration: alter work_items + extend type enum

```sql
-- Migration: EP-14_001_hierarchy_columns.sql

-- Step 1: Drop the existing type CHECK constraint (cannot ADD a value inline in Postgres < 12).
-- We use a text column + CHECK — the enum is not a Postgres ENUM type, just a CHECK constraint.
ALTER TABLE work_items DROP CONSTRAINT work_items_type_valid;

-- Step 2: Add new type CHECK constraint including milestone and story.
ALTER TABLE work_items ADD CONSTRAINT work_items_type_valid CHECK (type IN (
    'idea','bug','mejora','tarea','iniciativa','spike','cambio','requisito',
    'milestone','story'
));

-- Step 3: Add parent_work_item_id — nullable (existing items remain top-level).
ALTER TABLE work_items
    ADD COLUMN parent_work_item_id UUID REFERENCES work_items(id) ON DELETE RESTRICT;

-- Step 4: Add materialized_path — empty string for existing items (they are root nodes).
ALTER TABLE work_items
    ADD COLUMN materialized_path TEXT NOT NULL DEFAULT '';

-- Indexes
CREATE INDEX idx_work_items_parent_id
    ON work_items(parent_work_item_id)
    WHERE parent_work_item_id IS NOT NULL AND deleted_at IS NULL;

-- GIN trigram index for materialized path prefix/contains queries.
-- Requires pg_trgm extension (enabled in EP-05 migration already).
CREATE INDEX idx_work_items_mat_path
    ON work_items USING gin(materialized_path gin_trgm_ops)
    WHERE deleted_at IS NULL;

-- Composite: workspace + parent for children-of-parent list queries.
CREATE INDEX idx_work_items_ws_parent
    ON work_items(workspace_id, parent_work_item_id)
    WHERE deleted_at IS NULL;
```

**No backfill required.** Existing items default to `parent_work_item_id = NULL` and `materialized_path = ''`, which correctly represents them as top-level nodes under their project.

### WorkItemType enum (Python)

```python
class WorkItemType(str, Enum):
    IDEA        = "idea"
    BUG         = "bug"
    MEJORA      = "mejora"
    TAREA       = "tarea"
    INICIATIVA  = "iniciativa"
    SPIKE       = "spike"
    CAMBIO      = "cambio"
    REQUISITO   = "requisito"
    MILESTONE   = "milestone"   # NEW
    STORY       = "story"       # NEW
```

---

## 2. Domain Layer

### 2.1 WorkItem entity additions

```python
@dataclass
class WorkItem:
    # ... existing fields unchanged ...
    parent_work_item_id: UUID | None   # NEW
    materialized_path: str             # NEW — "" for root nodes
```

### 2.2 HierarchyValidator

Pure function. No I/O. Lives in `domain/hierarchy/hierarchy_validator.py`.

```python
from domain.models.work_item import WorkItemType

# None = any parent type is acceptable (or no parent)
# frozenset = only these parent types are permitted
VALID_PARENT_TYPES: dict[WorkItemType, frozenset[WorkItemType] | None] = {
    WorkItemType.MILESTONE:  frozenset(),                                 # empty = no parent allowed
    WorkItemType.INICIATIVA: frozenset({WorkItemType.MILESTONE}),
    WorkItemType.STORY:      frozenset({WorkItemType.INICIATIVA}),
    WorkItemType.REQUISITO:  frozenset({WorkItemType.INICIATIVA, WorkItemType.STORY}),
    WorkItemType.MEJORA:     frozenset({WorkItemType.INICIATIVA, WorkItemType.STORY}),
    WorkItemType.TAREA:      None,
    WorkItemType.BUG:        None,
    WorkItemType.IDEA:       None,
    WorkItemType.SPIKE:      None,
    WorkItemType.CAMBIO:     None,
}

def validate_parent(
    child_type: WorkItemType,
    parent_type: WorkItemType | None,
) -> tuple[bool, str | None]:
    """
    Returns (is_valid, error_code).
    error_code is None when valid.
    """
    if parent_type is None:
        return True, None  # detach always valid

    allowed = VALID_PARENT_TYPES.get(child_type)

    if allowed is not None and len(allowed) == 0:
        # empty frozenset = no parent allowed at all
        return False, "HIERARCHY_INVALID_PARENT_TYPE"

    if allowed is not None and parent_type not in allowed:
        return False, "HIERARCHY_INVALID_PARENT_TYPE"

    return True, None
```

**Rationale**: a plain dict + function. No class hierarchy, no strategy pattern, no DI. The rule table is 11 lines. Anyone can read and modify it in 30 seconds.

---

## 3. Application Layer

### 3.1 MaterializedPathService

`application/services/materialized_path_service.py`

Responsibilities:
- Compute the correct path for a new or reparented item
- Update the subtree (item + all descendants) in a single transaction
- Called from `WorkItemService.create_work_item` and `WorkItemService.update_work_item` (parent change)

```python
class MaterializedPathService:
    def __init__(self, work_item_repo: IWorkItemRepository) -> None:
        self._repo = work_item_repo

    async def compute_path(
        self,
        parent_work_item_id: UUID | None,
        session: AsyncSession,
    ) -> str:
        """Returns the materialized_path for a new child of parent_work_item_id."""
        if parent_work_item_id is None:
            return ""
        parent = await self._repo.get_by_id(parent_work_item_id, session)
        if parent.materialized_path:
            return f"{parent.materialized_path}.{parent_work_item_id}"
        return str(parent_work_item_id)

    async def update_subtree_paths(
        self,
        item_id: UUID,
        new_path: str,
        session: AsyncSession,
    ) -> None:
        """
        Updates materialized_path for item and all descendants.
        Single SQL UPDATE via recursive CTE — no Python-level N+1.

        Strategy: fetch all descendants by CTE, compute new path per node,
        bulk UPDATE in one statement.
        """
        await self._repo.bulk_update_materialized_paths(
            root_id=item_id,
            new_root_path=new_path,
            session=session,
        )
```

The repository implements `bulk_update_materialized_paths` as a `WITH RECURSIVE` CTE that:
1. Fetches all descendants of `root_id`
2. Replaces the old path prefix with the new path prefix in a single `UPDATE ... FROM (CTE)`

This is one SQL statement. No row-by-row Python loop.

### 3.2 CompletionRollupService

`application/services/completion_rollup_service.py`

```python
STATE_WEIGHTS: dict[WorkItemState, float] = {
    WorkItemState.DRAFT:                     0.0,
    WorkItemState.IN_CLARIFICATION:          0.1,
    WorkItemState.CHANGES_REQUESTED:         0.1,
    WorkItemState.IN_REVIEW:                 0.25,
    WorkItemState.PARTIALLY_VALIDATED:       0.5,
    WorkItemState.READY:                     1.0,
    WorkItemState.EXPORTED:                  1.0,
}

CACHE_KEY = "rollup:{work_item_id}"
CACHE_TTL_SECONDS = 86_400  # 24h

class CompletionRollupService:
    def __init__(
        self,
        work_item_repo: IWorkItemRepository,
        redis: Redis,
    ) -> None: ...

    async def get_rollup(self, work_item_id: UUID) -> int | None:
        """Returns cached value or computes fresh. Returns None for leaf nodes."""
        cached = await self._redis.get(CACHE_KEY.format(work_item_id=work_item_id))
        if cached is not None:
            return int(cached)
        return await self._compute_and_cache(work_item_id)

    async def invalidate(self, work_item_id: UUID, materialized_path: str) -> None:
        """
        Deletes rollup cache for this item's parent and all ancestors.
        Called from Celery task on work_item.state_changed / parent_changed / deleted.
        """
        parent_ids = [p for p in materialized_path.split(".") if p]
        if parent_ids:
            await self._redis.delete(*[
                CACHE_KEY.format(work_item_id=pid) for pid in parent_ids
            ])

    async def _compute_and_cache(self, work_item_id: UUID) -> int | None:
        children = await self._work_item_repo.get_direct_children(work_item_id)
        if not children:
            return None
        # children with their own children use their cached rollup_percent
        # leaves use their state weight
        total = 0.0
        for child in children:
            child_rollup = await self.get_rollup(child.id)
            if child_rollup is not None:
                total += child_rollup / 100.0
            else:
                total += STATE_WEIGHTS.get(child.state, 0.0)
        result = round((total / len(children)) * 100)
        await self._redis.setex(
            CACHE_KEY.format(work_item_id=work_item_id),
            CACHE_TTL_SECONDS,
            result,
        )
        return result
```

### 3.3 TreeQueryService

`application/services/tree_query_service.py`

Two read strategies:

| Strategy | When Used | SQL |
|---|---|---|
| `WITH RECURSIVE` CTE | Full project hierarchy (`/hierarchy`) | Walks entire subtree from project root |
| `LIKE` on materialized_path | Ancestor-filter in list views (`?ancestor_id=`) | `materialized_path LIKE '%<uuid>%'` |

```python
class TreeQueryService:
    async def get_project_hierarchy(
        self,
        project_id: UUID,
        workspace_id: UUID,
        cursor: str | None,
        limit: int,
        session: AsyncSession,
    ) -> HierarchyPage: ...

    async def get_children(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        pagination: CursorPagination,
        session: AsyncSession,
    ) -> Page[WorkItemSummary]: ...

    async def get_ancestors(
        self,
        work_item_id: UUID,
        session: AsyncSession,
    ) -> list[WorkItemSummary]: ...
        # Reads materialized_path, splits by ".", bulk-fetches UUIDs in order.
        # O(1) path read + 1 DB query (SELECT WHERE id IN (...)).

    async def get_descendants_by_ancestor(
        self,
        ancestor_id: UUID,
        workspace_id: UUID,
        filters: WorkItemFilters,
        pagination: CursorPagination,
        session: AsyncSession,
    ) -> Page[WorkItemSummary]: ...
        # Uses: WHERE materialized_path LIKE '%<ancestor_id>%'
        # + standard filter predicates
```

### 3.4 WorkItemService amendments

`WorkItemService.create_work_item`:
1. Call `HierarchyValidator.validate_parent(child_type, parent_type)` — raises `HierarchyValidationError` on failure
2. Verify parent is in same workspace + project — raises appropriate error
3. Verify no cycle (parent's `materialized_path` must not contain `item.id` — not possible on create, only on reparent)
4. Call `MaterializedPathService.compute_path(parent_work_item_id)` to get `materialized_path`
5. Persist

`WorkItemService.update_work_item` (when `parent_work_item_id` changes):
1. Same validation steps 1–3
2. Step 3 (cycle check): new parent's `materialized_path` must not contain this item's `id`
3. `MaterializedPathService.update_subtree_paths(item_id, new_path, session)` — subtree update in same transaction
4. Emit `work_item.parent_changed` event

`WorkItemService.delete_work_item`:
1. Check `has_children(item_id)` — if true, raise `HierarchyHasChildrenError`
2. Proceed with existing soft-delete logic

---

## 4. API Endpoints

| Method | Path | Description | Notes |
|---|---|---|---|
| GET | `/api/v1/projects/:id/hierarchy` | Full tree, paginated by root count | Limit 200 roots/page, cursor pagination |
| GET | `/api/v1/work-items/:id/children` | Direct children | Cursor pagination, EP-09 compatible |
| GET | `/api/v1/work-items/:id/ancestors` | Parent chain + breadcrumb | Built from materialized_path |
| GET | `/api/v1/work-items/:id/rollup` | Completion % (cached) | Returns null for leaves |

Existing endpoints amended:
- `POST /api/v1/work-items` — accepts `parent_work_item_id` (optional)
- `PATCH /api/v1/work-items/:id` — accepts `parent_work_item_id` (optional, triggers subtree update)
- `GET /api/v1/projects/:id/work-items` — accepts `parent_id` and `ancestor_id` query params (EP-09 filter extension)

---

## 5. Domain Events

| Event | Payload | Handler |
|---|---|---|
| `work_item.parent_changed` | `item_id, old_parent_id, new_parent_id, old_path, new_path` | Celery: `invalidate_rollup_cache` for old and new parent chains |
| `work_item.state_changed` (existing) | + `materialized_path` added to payload | Celery: `invalidate_rollup_cache` for ancestor chain |
| `work_item.created` (existing) | + `parent_work_item_id, materialized_path` added | Celery: `invalidate_rollup_cache` if parent present |
| `work_item.deleted` (existing) | + `parent_work_item_id, materialized_path` added | Celery: `invalidate_rollup_cache` for former parent chain |

**Celery task `invalidate_rollup_cache`**: reads `materialized_path` from event payload, splits by `.`, bulk-deletes all `rollup:{id}` keys. Idempotent.

---

## 6. Cycle Prevention

Detection is O(1) via materialized path. No CTE or DFS required.

```python
def would_create_cycle(
    item_id: UUID,
    new_parent_materialized_path: str,
) -> bool:
    """True if the new parent is a descendant of item_id."""
    return str(item_id) in new_parent_materialized_path.split(".")
```

Additionally: `item_id == new_parent_id` is a self-reference, rejected before this check.

The DB `ON DELETE RESTRICT` on `parent_work_item_id` is a last line of defence only. All business validation happens in the application layer before the DB write.

---

## 7. Layer Structure

```
domain/
  models/
    work_item.py                     # +parent_work_item_id, +materialized_path fields
  hierarchy/
    hierarchy_validator.py           # VALID_PARENT_TYPES dict + validate_parent()
  repositories/
    work_item_repository.py          # +bulk_update_materialized_paths, +get_direct_children, +has_children

application/
  services/
    materialized_path_service.py     # compute_path, update_subtree_paths
    completion_rollup_service.py     # get_rollup, invalidate, _compute_and_cache
    tree_query_service.py            # get_project_hierarchy, get_children, get_ancestors, get_descendants_by_ancestor
    work_item_service.py             # amended: create, update, delete

infrastructure/
  persistence/
    work_item_repository_impl.py     # implements bulk_update_materialized_paths (recursive CTE UPDATE)
  cache/
    rollup_cache.py                  # thin Redis wrapper; key formatting, TTL constants
  events/
    handlers/
      rollup_invalidation_handler.py # Celery task consuming work_item.state_changed / parent_changed / created / deleted

presentation/
  controllers/
    hierarchy_controller.py          # GET /hierarchy, GET /children, GET /ancestors, GET /rollup
    work_item_controller.py          # amended: create + update accept parent_work_item_id
```

---

## 8. Frontend Components

| Component | Location | Purpose |
|---|---|---|
| `TreeView` | `components/hierarchy/TreeView.tsx` | Collapsible tree of nodes; virtualized via `@tanstack/virtual` for large trees |
| `TreeNode` | `components/hierarchy/TreeNode.tsx` | Single tree row: type badge, title, state, rollup, expand/collapse |
| `ParentPicker` | `components/hierarchy/ParentPicker.tsx` | Typeahead select; filters candidates to valid parent types only; workspace+project scoped |
| `Breadcrumb` | `components/hierarchy/Breadcrumb.tsx` | Renders ancestor chain from `/ancestors` response |
| `RollupBadge` | `components/hierarchy/RollupBadge.tsx` | % complete badge; null = hidden; colour: gray/blue/green by threshold |
| Hierarchy Page | `app/projects/[id]/hierarchy/page.tsx` | Full project tree view using `TreeView` |

`ParentPicker` filters the typeahead search to only return work items whose type is in `VALID_PARENT_TYPES[childType]`. This validation mirrors the server-side rules so users see only valid options before submitting.

---

## 9. Alternatives Considered

### Postgres ENUM type instead of CHECK constraint

Rejected. EP-01 already uses a `VARCHAR + CHECK` pattern. Adding a new value to a Postgres `ENUM` type requires `ALTER TYPE ... ADD VALUE` which is not transactional in older Postgres versions. CHECK constraint on VARCHAR is transactional, consistent with EP-01, and trivially altered.

### Trigger-maintained materialized path

Rejected. EP-05 explicitly rejected this approach. Application-layer maintenance keeps side effects co-located with business logic and visible in the service layer. Triggers are invisible during code review and debugging.

### Separate `hierarchy` table (adjacency list separate from work_items)

Rejected. The hierarchy IS a property of work items, not a separate domain concept. Adding columns to `work_items` is the minimal change. A separate table would require joins on every list query and add a consistency surface (what if a work item is deleted but the hierarchy row remains?).

### Full tree in a single response (no pagination)

Rejected for large projects. A project could have hundreds of milestones and thousands of stories. Root-count pagination with fully expanded subtrees per root is the pragmatic balance: each root's subtree is bounded, root count is paginated.

### Async rollup computation only (never synchronous)

Rejected. The `/rollup` endpoint serves the cached value synchronously. Async Celery task only handles cache invalidation. First-read cache miss is accepted as a latency trade-off (typically <50ms for a shallow tree). Fully async with polling adds UI complexity for no benefit at current tree depths.
