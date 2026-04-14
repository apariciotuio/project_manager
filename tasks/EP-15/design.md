# EP-15 — Technical Design: Tags + Labels

## Schema

### Table: `tags`

```sql
CREATE TABLE tags (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    slug        VARCHAR(100) NOT NULL,
    color       CHAR(7) NOT NULL DEFAULT '#6B7280',
    icon        VARCHAR(50) NULL,
    archived    BOOLEAN NOT NULL DEFAULT false,
    created_by  UUID NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Table: `work_item_tags`

```sql
CREATE TABLE work_item_tags (
    work_item_id UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    tag_id       UUID NOT NULL REFERENCES tags(id) ON DELETE RESTRICT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by   UUID NOT NULL REFERENCES users(id),
    PRIMARY KEY (work_item_id, tag_id)
);
```

### Denormalized column on `work_items`

```sql
ALTER TABLE work_items ADD COLUMN tag_ids UUID[] NOT NULL DEFAULT '{}';
```

---

## Constraints and Indexes

### Partial unique index — slug uniqueness per workspace (active tags only)

```sql
CREATE UNIQUE INDEX idx_tags_workspace_slug_active
    ON tags (workspace_id, slug)
    WHERE archived = false;
```

Rationale: archived tags are excluded so a new tag can reuse a previously archived slug, and unarchiving a slug that conflicts returns a 409 rather than silently breaking.

### Active tags index — workspace listing and autocomplete

```sql
CREATE INDEX idx_tags_workspace_active
    ON tags (workspace_id)
    WHERE archived = false;
```

### Reverse lookup — work items by tag

```sql
CREATE INDEX idx_work_item_tags_tag
    ON work_item_tags (tag_id, work_item_id);
```

### GIN index — fast AND/OR filtering on denormalized array

```sql
CREATE INDEX idx_work_items_tag_ids
    ON work_items USING GIN (tag_ids);
```

AND query: `tag_ids @> ARRAY['uuid1', 'uuid2']::uuid[]`
OR query: `tag_ids && ARRAY['uuid1', 'uuid2']::uuid[]`

### Trigram index — autocomplete fuzzy name search

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_tags_name_trgm
    ON tags USING GIN (name gin_trgm_ops)
    WHERE archived = false;
```

---

## Denormalization Decision: `tag_ids UUID[]` on `work_items`

### Option A: Denormalized array (recommended)

Keep `tag_ids UUID[]` on `work_items`, maintained in the service layer (within the same transaction as `work_item_tags` mutations). No trigger — triggers are invisible to the service and complicate testing.

Pros:
- Single-table GIN index scan for filtered list queries — no join needed
- `tag_ids @> ARRAY[...]` is a simple, fast operator
- Eliminates 3-table join (`work_items JOIN work_item_tags JOIN tags`) from every list page load
- OR/AND filter symmetry is clean with `&&` / `@>`

Cons:
- Dual-write must be maintained in service layer; any direct DB mutation bypasses it
- `tag_ids` can drift from `work_item_tags` if a bug skips the sync — requires a reconciliation job
- Schema is denormalized (violates 3NF)

### Option B: Normalized join only

Query via `work_item_tags` with a 3-table join. Use a covering index on `work_item_tags(tag_id, work_item_id)` and rely on the planner.

Pros:
- Single source of truth
- No dual-write risk

Cons:
- AND-mode requires self-join or `HAVING COUNT(DISTINCT tag_id) = N` — expensive at scale
- Every list query pays the join cost even when no tag filter is active
- At 10k work items + 20 tags each = 200k join rows; planner struggles with multiple AND conditions

**Recommendation: Option A.** The join approach falls apart for AND-mode at any meaningful scale. The dual-write risk is manageable by wrapping all tag mutations in a `TagAttachmentService` that is the single code path. Add a nightly reconciliation job (`SELECT work_item_id FROM work_item_tags GROUP BY work_item_id` vs `work_items.tag_ids`) to catch any drift.

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/tags` | workspace member | List tags; supports `?q=`, `?archived=`, `?limit=` |
| GET | `/api/v1/tags/icons` | workspace member | Return predefined icon catalog |
| POST | `/api/v1/tags` | `tags:admin` | Create tag |
| PATCH | `/api/v1/tags/:id` | `tags:admin` | Rename, recolor, archive/unarchive |
| POST | `/api/v1/tags/:id/merge-into/:target_id` | `tags:admin` | Atomic merge + archive source |
| POST | `/api/v1/work-items/:id/tags` | `work_items:write` | Attach tag(s) |
| DELETE | `/api/v1/work-items/:id/tags/:tag_id` | `work_items:write` | Detach tag |
| POST | `/api/v1/tags/:id/bulk-attach` | `tags:admin` | Bulk attach across work items |

---

## DDD Layer Mapping

### Domain (`domain/`)

- `Tag` entity — holds invariants: slug derivation, color validation, archive state transitions
- `WorkItemTag` value object — (work_item_id, tag_id, created_by, created_at)
- `ITagRepository` interface
- `IWorkItemTagRepository` interface

### Application (`application/services/`)

- `TagService` — create, rename, archive/unarchive, validate workspace cap
- `TagMergeService` — atomic merge in single transaction
- `TagAttachmentService` — attach/detach, enforce 20-tag limit, sync `tag_ids` array

### Infrastructure (`infrastructure/persistence/`)

- `TagRepository` — SQLAlchemy async impl of `ITagRepository`
- `WorkItemTagRepository` — SQLAlchemy async impl; handles `tag_ids` array sync within same session

### Presentation (`presentation/controllers/`)

- `TagController` — routes for tag CRUD, merge, icon catalog
- `WorkItemTagController` — routes for attach/detach, bulk-attach

---

## Frontend Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `TagChip` | `components/tags/TagChip.tsx` | Pill rendering with color, icon, overflow, archived state |
| `TagInput` | `components/tags/TagInput.tsx` | Combobox autocomplete with debounce, on-the-fly create |
| `TagFilter` | `components/tags/TagFilter.tsx` | Multi-select filter panel for list sidebar, AND/OR toggle |
| `TagAdminPanel` | `components/tags/TagAdminPanel.tsx` | Full CRUD table with rename, recolor, archive, merge UI |

Integration points:
- `TagChip` + `TagInput` → work item header / detail view
- `TagFilter` → list sidebar (EP-09 filter extension)
- `TagAdminPanel` → workspace admin settings (EP-10 extension)

---

## Audit Events

| Action | Trigger | Payload fields |
|--------|---------|----------------|
| `tag.created` | Tag created | `name`, `color`, `icon` |
| `tag.renamed` | Name changed | `previous_name`, `new_name` |
| `tag.updated` | Color/icon changed | `fields_changed[]` |
| `tag.archived` | Archived | — |
| `tag.unarchived` | Restored | — |
| `tag.merged` | Merge completed | `source_tag_id`, `target_tag_id`, `items_affected_count` |
| `tag.bulk_attached` | Bulk attach | `tag_id`, `attached_count`, `skipped_count` |

---

## Security Considerations

- All tag queries are scoped by `workspace_id` from JWT auth context — never trust client-supplied workspace_id
- `tag_ids` filter silently drops out-of-workspace UUIDs (prevents workspace enumeration via 404 timing)
- Archived tag attachment is blocked server-side; client hint is UX only
- Merge endpoint is idempotent-safe: re-running after partial failure is safe (ON CONFLICT DO NOTHING on inserts)

---

## Dependencies

- EP-01: `work_items` table, `workspace_id` scoping
- EP-09: list filter param interface (add `tag_ids`, `tag_mode` to existing filter schema)
- EP-10: `audit_events` table, `capability` checks for `tags:admin` and `tags:write`
