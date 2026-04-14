# Spec: Tag Catalog Management — US-150, US-154

## Scope

Admin CRUD for workspace-scoped tag catalog, including rename, archive, merge, and uniqueness enforcement.

---

## US-150 — Create / Edit / Delete Tags

### Scenario: Create a new tag

WHEN an admin POSTs to `POST /api/v1/tags` with `{ name, color?, icon? }`
THEN a new tag record is created with a `slug` derived as `LOWER(TRIM(name))` with spaces replaced by `-`
AND the tag is scoped to the current workspace (`workspace_id` from auth context)
AND the response returns `201 Created` with the full tag object including generated `id`, `slug`, `created_at`, `created_by`
AND an `audit_events` record is written with `action=tag.created`, `actor_id`, `workspace_id`, `payload={name, color, icon}`

### Scenario: Create tag — name uniqueness (case-insensitive, per workspace)

WHEN an admin creates a tag with `name="Security Review"`
AND a non-archived tag with `slug="security-review"` already exists in the same workspace
THEN the API returns `409 Conflict` with `error.code="tag_slug_conflict"`
AND no record is inserted

WHEN the same `slug` exists in a different workspace
THEN the tag is created successfully (workspace isolation is enforced)

WHEN the same `slug` exists but its existing record has `archived=true`
THEN the tag is created successfully (partial unique index excludes archived rows)

### Scenario: Workspace tag cap

WHEN an admin attempts to create a tag
AND the workspace already has 200 non-archived tags
THEN the API returns `422 Unprocessable Entity` with `error.code="workspace_tag_limit_exceeded"`
AND no record is inserted

### Scenario: Rename a tag

WHEN an admin PATCHes `PATCH /api/v1/tags/:id` with `{ name: "New Name" }`
THEN the tag `name` and `slug` are updated atomically
AND the `slug` is re-derived from the new `name`
AND if the new slug conflicts with an existing non-archived tag in the workspace THEN `409 Conflict` is returned and the tag is unchanged
AND an `audit_events` record is written with `action=tag.renamed`, `previous_name`, `new_name`

### Scenario: Rename — no-op if name unchanged

WHEN an admin PATCHes with the same name (case-insensitive match)
THEN the API returns `200 OK` with the unchanged tag
AND no audit event is written

### Scenario: Update color or icon only

WHEN an admin PATCHes `{ color: "#FF5733" }` without changing `name`
THEN only `color` is updated; `slug` and `name` are unchanged
AND an `audit_events` record is written with `action=tag.updated`, `fields_changed=["color"]`

### Scenario: Delete a tag (hard delete — not exposed in initial MVP)

WHEN a non-admin attempts to DELETE a tag
THEN the API returns `403 Forbidden`

Note: Hard delete is intentionally omitted. Archive is the supported workflow. This prevents orphaned `work_item_tags` rows.

---

## US-154 — Archive and Merge Tags

### Scenario: Archive a tag

WHEN an admin PATCHes `PATCH /api/v1/tags/:id` with `{ archived: true }`
THEN `archived` is set to `true` on the tag record
AND `work_item_tags` rows referencing this tag are NOT deleted (existing attachments are preserved)
AND the tag is excluded from autocomplete and tag creation flows
AND an `audit_events` record is written with `action=tag.archived`

WHEN an admin attempts to archive an already-archived tag
THEN the API returns `200 OK` with no change and no audit event

### Scenario: Unarchive a tag

WHEN an admin PATCHes `{ archived: false }` on an archived tag
AND no non-archived tag with the same `slug` exists in the workspace
THEN the tag is restored (`archived=false`)
AND an `audit_events` record is written with `action=tag.unarchived`

WHEN unarchiving would create a slug conflict (another non-archived tag has the same slug)
THEN the API returns `409 Conflict` with `error.code="tag_slug_conflict_on_unarchive"`

### Scenario: Merge tag A into tag B

WHEN an admin POSTs `POST /api/v1/tags/:source_id/merge-into/:target_id`
THEN the operation executes in a single database transaction:
  1. All `work_item_tags` rows with `tag_id = source_id` that do not already have `tag_id = target_id` on the same `work_item_id` are updated to `tag_id = target_id`
  2. Duplicate rows (items already tagged with both source and target) are deleted from `work_item_tags` (not duplicated)
  3. The denormalized `tag_ids` arrays on affected `work_items` are updated (remove source_id, ensure target_id present)
  4. The source tag is archived (`archived=true`)
AND an `audit_events` record is written with `action=tag.merged`, `source_tag_id`, `target_tag_id`, `items_affected_count`
AND the response returns `200 OK` with `{ target_tag, items_affected_count }`

### Scenario: Merge — source equals target

WHEN an admin attempts to merge a tag into itself (`source_id == target_id`)
THEN the API returns `400 Bad Request` with `error.code="merge_same_tag"`

### Scenario: Merge — target is archived

WHEN the target tag is archived
THEN the API returns `422 Unprocessable Entity` with `error.code="merge_target_archived"`

### Scenario: Merge — source does not exist in workspace

WHEN either `source_id` or `target_id` does not belong to the current workspace
THEN the API returns `404 Not Found`
AND no changes are made

---

## Non-Functional

- Merge operation must complete within a single transaction; partial merges are not acceptable
- All mutating operations require `capability=tags:admin` (from EP-10)
- All mutating operations produce an `audit_events` row (EP-10 dependency)
- Slug generation: `LOWER(TRIM(name))` → replace whitespace sequences with `-` → strip non-alphanumeric except `-`
