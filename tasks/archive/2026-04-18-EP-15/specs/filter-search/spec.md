# Spec: Filter and Search by Tags — US-152

## Scope

Tag-based filtering integrated into existing list endpoints (EP-09), with AND/OR modes and performance constraints.

---

## Scenario: Filter work items by a single tag (OR mode default)

WHEN a user requests `GET /api/v1/work-items?tag_ids=<uuid>&tag_mode=or`
AND the tag belongs to the current workspace
THEN the response contains only work items that have `<uuid>` in their `tag_ids` array
AND standard cursor pagination (EP-09) applies to the filtered result set
AND the response time is under 300ms at p95 for a workspace with up to 10,000 work items

### Scenario: Filter by multiple tags — OR mode

WHEN a user requests `GET /api/v1/work-items?tag_ids=<uuid1>,<uuid2>&tag_mode=or`
THEN the response contains work items that have ANY of `uuid1` or `uuid2` in their `tag_ids` array
AND items matching both tags appear only once (no duplicates)

### Scenario: Filter by multiple tags — AND mode

WHEN a user requests `GET /api/v1/work-items?tag_ids=<uuid1>,<uuid2>&tag_mode=and`
THEN the response contains only work items that have BOTH `uuid1` AND `uuid2` in their `tag_ids` array
AND the query uses the GIN index: `tag_ids @> ARRAY[uuid1, uuid2]` for AND semantics
AND the response time is under 300ms at p95

### Scenario: tag_mode defaults to OR

WHEN `tag_ids` is provided but `tag_mode` is absent
THEN `tag_mode` defaults to `or`

### Scenario: Filter with invalid tag_mode value

WHEN `tag_mode` is set to any value other than `and` or `or`
THEN the API returns `400 Bad Request` with `error.code="invalid_filter_param"` and `param="tag_mode"`

### Scenario: Filter with a tag_id from a different workspace

WHEN a `tag_id` in the filter belongs to a different workspace
THEN that `tag_id` is silently ignored (treated as if no items match it)
AND the query still executes with the remaining valid tag_ids
AND no error is returned (prevents workspace enumeration)

### Scenario: Filter with an archived tag

WHEN a `tag_id` references an archived tag
THEN the filter still works — archived tags can still be used to find items that have them attached
AND the archived tag is included in the filter results (historical filtering must work)

### Scenario: Combine tag filter with other filters

WHEN a user requests `GET /api/v1/work-items?tag_ids=<uuid>&state=open&assigned_to=<user_id>`
THEN all filters are applied together (AND between different filter dimensions)
AND the result is paginated with the existing cursor mechanism (EP-09)

### Scenario: Empty tag_ids parameter

WHEN `tag_ids` is provided as an empty string or empty list
THEN the API returns `400 Bad Request` with `error.code="invalid_filter_param"` and `param="tag_ids"`

### Scenario: More than 20 tag_ids in a single filter

WHEN more than 20 `tag_ids` are provided in the filter
THEN the API returns `400 Bad Request` with `error.code="filter_tag_limit_exceeded"` and `limit=20`

---

## Scenario: Tag filter in kanban board view (EP-09 extension)

WHEN a user applies a tag filter in the kanban board view
THEN only cards with matching tags are shown in each column
AND the column item count reflects the filtered count
AND empty columns remain visible (not hidden) with count=0

---

## Scenario: Tag filter in search results

WHEN a user uses global search (EP-09) and applies a tag filter
THEN the tag filter is applied as an additional constraint on top of full-text search results
AND the response includes the applied filters in the metadata `{ filters_applied: { tag_ids: [...], tag_mode: "and" } }`

---

## Non-Functional

- AND-mode filter uses `tag_ids @> ARRAY[...]::uuid[]` with GIN index — no fallback to 3-table join
- OR-mode filter uses `tag_ids && ARRAY[...]::uuid[]` with GIN index
- `tag_ids` must be indexed with `CREATE INDEX idx_work_items_tag_ids ON work_items USING GIN(tag_ids)`
- Filter parameters are validated and sanitized before query construction (no raw UUID injection)
- Performance target: p95 < 300ms for workspace with 10,000 items and up to 20 tag_ids in filter
- Filter params are additive with existing EP-09 cursor/sort/search params — no breaking changes to existing query interface
