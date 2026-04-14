# Spec: Attach / Detach Tags on Work Items — US-151

## Scope

Attaching and detaching tags on individual work items, bulk attach across items (admin), and enforcement of limits and archived-tag guard.

---

## Scenario: Attach a single tag to a work item

WHEN a user POSTs `POST /api/v1/work-items/:id/tags` with `{ tag_ids: ["<uuid>"] }`
AND the work item belongs to the user's workspace
AND the tag is active (not archived) and belongs to the same workspace
AND the work item currently has fewer than 20 tags
THEN a `work_item_tags` row is inserted with `work_item_id`, `tag_id`, `created_at`, `created_by`
AND the `tag_ids` array on the `work_items` row is updated to include the new `tag_id`
AND the response returns `200 OK` with the updated tag list for the work item

### Scenario: Attach multiple tags in one request

WHEN a user POSTs with `{ tag_ids: ["<uuid1>", "<uuid2>", "<uuid3>"] }`
AND attaching all of them would not exceed the 20-tag limit
THEN all tags are attached atomically in a single operation
AND the response returns `200 OK` with the full updated tag list

WHEN attaching all of them would push the total beyond 20
THEN the API returns `422 Unprocessable Entity` with `error.code="work_item_tag_limit_exceeded"` and `current_count`, `attempted_count`, `limit`
AND no tags are attached (all-or-nothing)

### Scenario: Attach an already-attached tag (idempotent)

WHEN a user attaches a tag that is already attached to the work item
THEN the API returns `200 OK` with the current tag list unchanged
AND no duplicate row is inserted (ON CONFLICT DO NOTHING semantics)
AND no audit event is written for the no-op

### Scenario: Attach an archived tag

WHEN a user attempts to attach a tag with `archived=true`
THEN the API returns `422 Unprocessable Entity` with `error.code="tag_archived"`
AND no row is inserted

### Scenario: Attach a tag from a different workspace

WHEN the requested `tag_id` belongs to a different workspace than the work item
THEN the API returns `404 Not Found` (tag not found in scope)
AND no row is inserted

### Scenario: Attach to a work item in a different workspace

WHEN the `work_item_id` does not belong to the current workspace
THEN the API returns `404 Not Found`

---

## Scenario: Detach a tag from a work item

WHEN a user DELETEs `DELETE /api/v1/work-items/:id/tags/:tag_id`
AND the `work_item_tags` row exists
THEN the row is deleted
AND the `tag_ids` array on `work_items` is updated to remove `tag_id`
AND the response returns `204 No Content`

### Scenario: Detach a tag that is not currently attached (idempotent)

WHEN the `work_item_tags` row does not exist
THEN the API returns `204 No Content` with no error
AND no changes are made

### Scenario: Detach from a work item in a different workspace

WHEN the `work_item_id` does not belong to the current workspace
THEN the API returns `404 Not Found`

---

## Scenario: Bulk attach a tag across multiple work items (admin)

WHEN an admin POSTs `POST /api/v1/tags/:tag_id/bulk-attach` with `{ work_item_ids: ["<uuid1>", ..., "<uuidN>"] }`
AND the tag is active and belongs to the workspace
AND `work_item_ids` contains at most 100 items
THEN for each work item:
  - IF attaching would not exceed the 20-tag limit: attach the tag
  - IF attaching would exceed the limit: skip that item and record it in `skipped`
AND the response returns `200 OK` with `{ attached_count, skipped: [{ work_item_id, reason }] }`
AND an `audit_events` record is written with `action=tag.bulk_attached`, `tag_id`, `attached_count`, `skipped_count`

WHEN `work_item_ids` contains more than 100 items
THEN the API returns `422 Unprocessable Entity` with `error.code="bulk_limit_exceeded"`

WHEN the requesting user does not have `capability=tags:admin`
THEN the API returns `403 Forbidden`

---

## Non-Functional

- All attach/detach operations must keep `work_items.tag_ids` array in sync within the same transaction
- Attach endpoint accepts `tag_ids` array (not a single ID) to enable multi-tag attach in one round trip
- Workspace scoping enforced at service layer, not just query filter
- Max payload for `tag_ids` in a single attach: 20 items (matches per-item limit)
