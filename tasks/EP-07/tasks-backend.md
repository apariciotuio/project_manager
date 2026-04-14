# EP-07 Backend Tasks — Comments, Versioning, Diff & Timeline

Tech stack: Python 3.12+, FastAPI, SQLAlchemy async, PostgreSQL 16+, Celery + Redis

---

## API Contract (interface with frontend)

### Version list response
```json
{
  "data": [
    {
      "version_number": 3,
      "trigger": "content_edit",
      "actor_type": "human",
      "actor_id": "uuid",
      "commit_message": "string | null",
      "archived": false,
      "created_at": "iso8601"
    }
  ],
  "meta": { "has_more": true, "next_cursor": "base64" }
}
```

### Version snapshot response
```json
{
  "data": {
    "version_number": 3,
    "snapshot": {
      "schema_version": 1,
      "work_item": { "id": "uuid", "title": "string", "description": "string", "state": "string", "owner_id": "uuid" },
      "sections": [{ "section_id": "uuid", "section_type": "string", "content": "string", "order": 0 }],
      "task_node_ids": ["uuid"]
    }
  }
}
```

### Diff response
```json
{
  "data": {
    "from_version": 2,
    "to_version": 3,
    "metadata_diff": { "title": { "before": "Old", "after": "New" }, "state": null },
    "sections": [
      {
        "section_type": "string",
        "change_type": "modified | added | removed | unchanged | reordered",
        "hunks": [
          { "type": "context | added | removed", "lines": ["string"] }
        ]
      }
    ]
  }
}
```

### Comment response
```json
{
  "data": {
    "id": "uuid",
    "work_item_id": "uuid",
    "parent_comment_id": "uuid | null",
    "body": "string",
    "actor_type": "human | ai_suggestion | system",
    "actor_id": "uuid | null",
    "anchor_section_id": "uuid | null",
    "anchor_start_offset": 10,
    "anchor_end_offset": 25,
    "anchor_snapshot_text": "selected text",
    "anchor_status": "active | orphaned",
    "is_edited": false,
    "deleted_at": null,
    "created_at": "iso8601",
    "replies": []
  }
}
```

### Timeline event response
```json
{
  "data": [
    {
      "id": "uuid",
      "event_type": "state_transition | comment_added | version_created | review_submitted | export_triggered",
      "actor_type": "human | ai_suggestion | system",
      "actor_id": "uuid | null",
      "actor_display_name": "string",
      "summary": "string (max 255)",
      "payload": {},
      "occurred_at": "iso8601",
      "source_id": "uuid | null",
      "source_table": "comments | work_item_versions | review_responses | export_events | null"
    }
  ],
  "meta": { "has_more": true, "next_cursor": "base64" }
}
```

---

## Phase 0 — Migrations

### Acceptance Criteria

WHEN migrations run
THEN `work_item_versions` has `snapshot_schema_version`, `trigger`, `actor_type`, `actor_id`, `commit_message`, `archived` columns
AND `idx_wiv_archived` partial index on `WHERE archived = false` is present (default list queries use it)
AND `comments` table has `anchor_range_valid` CHECK (`anchor_start_offset <= anchor_end_offset`), `anchor_section_required_for_range` CHECK (if offset set then section_id required), `no_deep_nesting` CHECK (`parent_comment_id` references only root comments)
AND `timeline_events` table has composite index on `(work_item_id, occurred_at DESC)`

WHEN any migration is rolled back
THEN it reverts cleanly without leaving orphan columns or indexes

- [ ] 0.1 [RED] Write migration test: `work_item_versions` extended columns exist (`snapshot_schema_version`, `trigger`, `actor_type`, `actor_id`, `commit_message`, `archived`); `idx_wiv_archived` partial index present
- [ ] 0.2 [GREEN] Create additive Alembic migration on `work_item_versions` (EP-04 table) — do not recreate table
- [ ] 0.3 [RED] Write migration test: `comments` table exists with all columns; `anchor_range_valid`, `anchor_section_required_for_range`, `no_deep_nesting` constraints; all indexes
- [ ] 0.4 [GREEN] Create Alembic migration: `comments` table
- [ ] 0.5 [RED] Write migration test: `timeline_events` table exists with all columns and indexes
- [ ] 0.6 [GREEN] Create Alembic migration: `timeline_events` table
- [ ] 0.7 [GREEN] Verify rollback (downgrade) for all three migrations

---

## Phase 1 — Domain Layer

### Acceptance Criteria

See also: specs/versioning/spec.md, specs/comments/spec.md, specs/timeline/spec.md

**WorkItemVersion**
- `version_number` must be a positive integer; zero or negative raises `ValueError`
- `trigger` must be one of `content_edit | state_transition | review_outcome | breakdown_change | manual`
- Snapshot is immutable: no attribute setter permitted after construction

**Comment**
- `anchor_start_offset > anchor_end_offset` → raises `InvariantError`
- `anchor_start_offset` set without `anchor_section_id` → raises `InvariantError`
- Replying to a reply (parent has `parent_comment_id != null`) → raises `ValidationError`
- Editing an `actor_type=ai_suggestion` comment → raises `ForbiddenError`
- Soft delete with replies: `body = '[deleted]'`, `deleted_at` set, replies remain
- Soft delete without replies: `deleted_at` set (body may be cleared or set to `[deleted]` — consistent with schema, decide once and document)

**TimelineEvent**
- `summary` > 255 chars → raises `ValueError`
- `actor_type` must be `human | ai_suggestion | system` — None not permitted

### Version domain

- [ ] Refactor: all repository methods must accept `workspace_id` as a required parameter — `get_by_id(id, workspace_id)`, `list_by_work_item(work_item_id, workspace_id)`, `get(comment_id, workspace_id)`, etc. Queries must include `WHERE workspace_id = :workspace_id`. Return `None` (not 403) on workspace mismatch to avoid existence disclosure (CRIT-2).
- [ ] 1.1 [RED] Test `WorkItemVersion` entity: immutable after creation, `version_number` is positive integer, valid `trigger` enum values, invalid trigger raises `ValueError`
- [ ] 1.2 [GREEN] Implement `domain/models/work_item_version.py`
- [ ] 1.3 [GREEN] Define `domain/repositories/version_repository.py` interface: `get_by_id(id, workspace_id)`, `list_by_work_item(work_item_id, workspace_id)`, `get_latest(work_item_id, workspace_id)`, `get_by_number(work_item_id, version_number, workspace_id)`, `create`

### Comment domain

- [ ] 1.4 [RED] Test `Comment` entity: anchor range valid (start <= end); `anchor_start_offset` set without `anchor_section_id` → raises; reply-to-reply detection raises; AI comment edit attempt raises; soft delete sets body to `[deleted]` when replies exist
- [ ] 1.5 [GREEN] Implement `domain/models/comment.py`
- [ ] 1.6 [GREEN] Define `domain/repositories/comment_repository.py` interface: `create`, `get`, `list_by_work_item`, `list_by_section`, `soft_delete`, `update`, `update_anchor`

### Timeline domain

- [ ] 1.7 [RED] Test `TimelineEvent` entity: `summary` > 255 chars raises; required fields enforced; valid `event_type` enum
- [ ] 1.8 [GREEN] Implement `domain/models/timeline_event.py`
- [ ] 1.9 [GREEN] Define `domain/repositories/timeline_repository.py` interface: `append`, `list_by_work_item` with filters and cursor pagination

---

## Phase 2 — Infrastructure (Repositories)

- [ ] 2.1 [RED] Write repository tests: `VersionRepository` — `create`, `get_by_number` correct, `list_by_work_item` reverse-chron, archived excluded by default, `get_latest` returns highest version_number
- [ ] 2.2 [GREEN] Implement `infrastructure/persistence/version_repository_impl.py`
- [ ] 2.3 [RED] Write repository tests: `CommentRepository` — `create`, `get`, `list_by_work_item` excludes soft-deleted, `list_by_section`, `soft_delete` sets `deleted_at`, `update_anchor` updates offsets/status
- [ ] 2.4 [GREEN] Implement `infrastructure/persistence/comment_repository_impl.py`
- [ ] 2.5 [RED] Write repository tests: `TimelineRepository` — `append`, `list_by_work_item` reverse-chron, filter by `event_type`, filter by `actor_type`, date range filter, cursor pagination page 1 and page 2 correct
- [ ] 2.6 [GREEN] Implement `infrastructure/persistence/timeline_repository_impl.py` with `(occurred_at, id)` composite cursor (base64 JSON)

---

## Phase 3 — Application Services

### Acceptance Criteria — VersioningService

See also: specs/versioning/spec.md (US-071 Scenarios 1–8)

WHEN `create_version(work_item_id, trigger, actor_type, actor_id)` is called
THEN snapshot includes all sections sorted by `order`, `task_node_ids` list, and top-level `work_item` fields
AND `version_number` = `max(existing version_number) + 1` in a serializable transaction (prevents duplicate numbers under concurrency)
AND `schema_version = 1` in snapshot

WHEN called concurrently for the same work item
THEN only one version is created per call (serializable isolation prevents phantom duplicate)

WHEN action is `content_edit` (EP-04 section save)
THEN version is created with `trigger=content_edit`

WHEN action is `state_transition` (EP-01)
THEN version is created with `trigger=state_transition`

WHEN action is `review_outcome` (EP-06 review response)
THEN version is created with `trigger=review_outcome`

WHEN action is `breakdown_change` (EP-05 task save)
THEN version is created with `trigger=breakdown_change`

WHEN `list_by_work_item` is called without `include_archived=True`
THEN archived versions are excluded; results are reverse-chronological

### Acceptance Criteria — DiffService

See also: specs/versioning/spec.md (US-072 Scenarios 1–7)

WHEN `compute_version_diff(snapshot_a, snapshot_b)` is called
THEN sections in both versions matched by `section_type`
AND each section classified as `added | removed | modified | unchanged | reordered`
AND `metadata_diff` contains `title`, `state` changes if any; null for unchanged fields

WHEN sections are identical
THEN `change_type = unchanged`; hunks may be empty

WHEN section exists only in B
THEN `change_type = added`; hunk lines all `added`

WHEN section exists only in A
THEN `change_type = removed`; hunk lines all `removed`

WHEN `section_type` same but `order` changed and content identical
THEN `change_type = reordered`; no diff hunks generated

WHEN snapshots are identical
THEN all sections `unchanged`; `metadata_diff` all null

WHEN `compute_section_diff(text_a, text_b)` is called on 100KB combined content
THEN result computed in < 2s

WHEN `from_version > to_version`
THEN `DiffService` raises `ValueError` — callers must enforce order

### Acceptance Criteria — CommentService

See also: specs/comments/spec.md (US-070 Scenarios 1–10)

WHEN `create_comment` is called with `anchor_start_offset` and `anchor_end_offset` and `anchor_section_id`
THEN comment created with `anchor_status=active`, `anchor_snapshot_text` stored immutably

WHEN `anchor_start_offset > anchor_end_offset`
THEN `ValidationError(422)` raised; no record created

WHEN `anchor_start_offset` set without `anchor_section_id`
THEN `ValidationError(422)`

WHEN editing a comment with `actor_type=ai_suggestion`
THEN `ForbiddenError(403)` raised

WHEN replying to a reply
THEN `ValidationError(422)` — one level deep only

WHEN `create_comment` or `soft_delete` is called
THEN a `comment_added` or `comment_deleted` timeline event is appended in the same transaction

### Acceptance Criteria — AnchorRecomputeTask

See also: specs/comments/spec.md (SC-070-04, SC-070-05)

WHEN section content is updated and `anchor_snapshot_text` is found at new offsets with `SequenceMatcher.ratio() >= 0.8`
THEN `anchor_start_offset`, `anchor_end_offset` updated; `anchor_status = active`

WHEN ratio < 0.8
THEN `anchor_status = orphaned`; offsets not changed; `anchor_snapshot_text` not modified

WHEN a section is deleted
THEN all comments anchored to that `anchor_section_id` are set to `anchor_status = orphaned`

### Acceptance Criteria — TimelineService

See also: specs/timeline/spec.md (US-073)

WHEN `list_events(work_item_id, filters, cursor, limit)` is called
THEN results are in descending `occurred_at` order
AND `event_type` filter returns only matching events
AND `actor_type` filter returns only matching actors
AND `from_date` and `to_date` are inclusive bounds on `occurred_at`
AND cursor pagination is stable: page 1 followed by page 2 returns non-overlapping events in correct order
AND `has_more=false` on last page

WHEN a work item has no events
THEN single `item_created` event returned; `has_more=false`

WHEN timeline is fetched (no filters)
THEN only root comments appear as `comment_added` events (replies do not generate their own events)

### VersioningService

- [ ] 3.1 [RED] Test `create_version`: snapshot includes all sections and `task_node_ids`; `version_number` increments correctly; verify `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE` is explicitly executed — NOT relying on SQLAlchemy default (which is READ COMMITTED) (Fixed per backend_review.md ALG-2)
- [ ] 3.1a [RED] Test concurrent `create_version` for same work_item: two concurrent calls produce two distinct version numbers — no UNIQUE constraint violation
- [ ] 3.2 [RED] Test trigger types: `content_edit`, `state_transition`, `review_outcome`, `breakdown_change` each produce a version with correct `trigger` field
- [ ] 3.3 [RED] Test snapshot schema: `schema_version=1`, `work_item` fields present, `sections` array sorted by `order`, `task_node_ids` list
- [ ] 3.4 [RED] Test navigation: `get_by_number` returns correct snapshot; `list` reverse-chron; archived excluded by default
- [ ] 3.5 [GREEN] Implement `application/services/versioning_service.py` — `create_version()` must call `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE` explicitly
- [ ] 3.6 [GREEN] Integrate `VersioningService.create_version()` into EP-04 section save (`content_edit` trigger)
- [ ] 3.7 [GREEN] Integrate into EP-01 state transition handler (`state_transition` trigger)
- [ ] 3.8 [GREEN] Integrate into EP-06 review response handler (`review_outcome` trigger)
- [ ] 3.9 [GREEN] Integrate into EP-05 breakdown save (`breakdown_change` trigger)

### DiffService (pure, no persistence)

- [ ] 3.10 [RED] Test `compute_version_diff`: sections added/removed/modified/unchanged/reordered correctly classified by `section_type`
- [ ] 3.11 [RED] Test `compute_section_diff`: line-level diff correct; word-level highlighting on changed lines; unchanged sections collapsed
- [ ] 3.12 [RED] Test: identical snapshots → all sections `unchanged`
- [ ] 3.13 [RED] Test: empty source (first version vs empty) → all sections `added`
- [ ] 3.14 [RED] Test: metadata diff (title change, state change) included in `metadata_diff` field
- [ ] 3.15 [RED] Performance test: 100KB combined content < 2s
- [ ] 3.16 [GREEN] Implement `application/services/diff_service.py` using `difflib` only — no external libraries

### CommentService

- [ ] 3.17 [RED] Test `create_comment`: general comment (no anchor); section-anchored (section_id only); range-anchored (section_id + offsets + snapshot_text) — each correct record
- [ ] 3.18 [RED] Test anchor validation: `anchor_start_offset > anchor_end_offset` → raises; `anchor_start_offset` set without `anchor_section_id` → raises
- [ ] 3.19 [RED] Test AI comment immutability: edit attempt on `actor_type=ai_suggestion` → raises `ForbiddenError`
- [ ] 3.20 [RED] Test reply depth: reply to a reply → raises `ValidationError`
- [ ] 3.21 [RED] Test soft delete: comment with replies → body replaced with `[deleted]`, `deleted_at` set, replies retained; comment without replies → fully deleted (or also soft-deleted — consistent with schema)
- [ ] 3.22 [RED] Test pagination: cursor-based, `has_more` accurate for page boundaries
- [ ] 3.23 [RED] Test timeline events: `create_comment` appends `comment_added` to `timeline_events`; `soft_delete` appends `comment_deleted`
- [ ] 3.23a [RED] Test transaction atomicity: WHEN `timeline_events` INSERT raises (e.g. `summary` truncated at 255 chars) THEN comment INSERT is also rolled back — timeline INSERT must NOT be in a separate try/except or fire-and-forget (Fixed per backend_review.md TC-4)
- [ ] 3.24 [GREEN] Implement `application/services/comment_service.py` — timeline INSERT must be in the same DB transaction as comment INSERT; never wrap timeline write in a separate try/except

### AnchorRecomputeTask (Celery async)

- [ ] 3.25 [RED] Test Celery task: `anchor_snapshot_text` found at new offset (ratio >= 0.8) → offsets updated, `anchor_status=active`; ratio < 0.8 → `anchor_status=orphaned`
- [ ] 3.26 [RED] Test: section deleted → all anchors for that `anchor_section_id` set to `orphaned`
- [ ] 3.27 [GREEN] Implement `infrastructure/tasks/anchor_recompute_task.py` using `difflib.SequenceMatcher`
- [ ] 3.28 [GREEN] Wire Celery task dispatch into EP-04 section save (after version snapshot committed)

### TimelineService

- [ ] 3.29 [RED] Test `list_events`: reverse-chron; `event_type` filter narrows correctly; `actor_type` filter narrows correctly; `from_date`/`to_date` range filter; cursor pagination page 1 and 2 correct; `has_more=false` on last page
- [ ] 3.30 [RED] Test empty timeline: returns `item_created` event (inserted at work item creation), `has_more=false`
- [ ] 3.31 [RED] Test all upstream integrations write to `timeline_events`: `state_transition`, `review_submitted`, `export_triggered` (stubbed for EP-11)
- [ ] 3.32 [GREEN] Implement `application/services/timeline_service.py`

---

## Phase 4 — Controllers

### Acceptance Criteria

See also: specs/versioning/spec.md, specs/comments/spec.md, specs/timeline/spec.md

**GET /api/v1/work-items/{id}/versions**
- 200: paginated list, `archived` excluded by default; `meta.has_more`, `meta.next_cursor` present
- 401: unauthenticated
- 403: no read access

**GET /api/v1/work-items/{id}/versions/{version_number}**
- 200: full snapshot shape with `schema_version=1`, `sections` sorted by `order`, `task_node_ids`
- 404: version not found

**GET /api/v1/work-items/{id}/versions/{version_number}/diff**
- 200: diff vs previous version; if first version, all sections `added`
- 404: version not found

**GET /api/v1/work-items/{id}/versions/diff?from=N&to=M**
- 200: diff response shape
- 400: `from > to` → `{ "error": { "code": "INVALID_DIFF_RANGE", "message": "from must be <= to" } }`
- 404: either version not found
- Response time < 2s for 100KB combined section content

**POST /api/v1/work-items/{id}/comments**
- 201: comment shape with `anchor_status=active` if anchored
- 422: `anchor_start_offset > anchor_end_offset`
- 422: anchor offset set without `anchor_section_id`
- 401: unauthenticated

**GET /api/v1/work-items/{id}/comments**
- 200: paginated; soft-deleted comments omitted from body (no `[deleted]` in list unless they have replies); cursor-based with `has_more`

**PATCH /api/v1/work-items/{id}/comments/{comment_id}**
- 200: updated comment
- 403: not comment author
- 403: `actor_type=ai_suggestion`

**DELETE /api/v1/work-items/{id}/comments/{comment_id}**
- 204: success
- 403: not comment author

**POST /api/v1/work-items/{id}/comments/{comment_id}/replies**
- 201: reply shape with `parent_comment_id` set
- 422: parent is itself a reply (no deep nesting)

**GET /api/v1/work-items/{id}/timeline**
- 200: `{ "data": { "events": [...], "has_more": bool, "next_cursor": string } }`
- Filter params `event_types`, `actor_types`, `from_date`, `to_date`, `before` (cursor), `limit` all applied server-side
- 400: invalid enum value in `event_types` or `actor_types`
- Empty result on matching filter → `events: []`, `has_more: false`, HTTP 200

### VersionController

- [ ] 4.1 [RED] Integration test: `GET /api/v1/work-items/{id}/versions` → paginated list, `archived` excluded by default
- [ ] 4.2 [RED] Integration test: `GET /api/v1/work-items/{id}/versions/{version_number}` → snapshot shape correct
- [ ] 4.3 [RED] Integration test: `GET /api/v1/work-items/{id}/versions/{version_number}/diff` → diff vs previous version
- [ ] 4.4 [RED] Integration test: `GET /api/v1/work-items/{id}/versions/diff?from=1&to=3` → diff for arbitrary pair
- [ ] 4.5 [RED] Integration test: `from > to` → 400; version not found → 404
- [ ] 4.6 [GREEN] Implement `presentation/controllers/version_controller.py`

### CommentController

- [ ] 4.7 [RED] Integration test: `POST /api/v1/work-items/{id}/comments` general → 201; with valid anchor → 201; invalid anchor range → 422
- [ ] 4.8 [RED] Integration test: `GET /api/v1/work-items/{id}/comments` → paginated, deleted comments excluded from body
- [ ] 4.9 [RED] Integration test: `PATCH /comments/{id}` own → 200; other user's → 403; AI comment → 403
- [ ] 4.10 [RED] Integration test: `DELETE /comments/{id}` own → 204; other user's → 403
- [ ] 4.11 [RED] Integration test: `POST /comments/{id}/replies` → 201; reply to reply → 422
- [ ] 4.12 [RED] Integration test: `GET /sections/{section_id}/comments` → anchored comments only
- [ ] 4.13 [GREEN] Implement `presentation/controllers/comment_controller.py`

### TimelineController

- [ ] 4.14 [RED] Integration test: `GET /timeline` → all events, correct schema
- [ ] 4.15 [RED] Integration test: `?event_types=state_transition` filters; `?actor_types=ai_suggestion` filters; `?from_date=...&to_date=...` filters; cursor pagination pages correct
- [ ] 4.16 [GREEN] Implement `presentation/controllers/timeline_controller.py`

---

## Phase 5 — Authorization

- [ ] 5.1 [RED] Test: unauthenticated requests → 401 on all EP-07 endpoints
- [ ] 5.2 [RED] Test: user without work item read access → 403 on versions, comments, timeline
- [ ] 5.3 [RED] Test: user can only edit/delete own comments; AI comments → 403 on PATCH for any user
- [ ] 5.4 [GREEN] Implement authorization in service layer (not controller)

---

## Phase 6 — Performance & Observability

- [ ] 6.1 [GREEN] Add structured logging: version creation (`work_item_id`, `version_number`, `trigger`, `actor_type`); diff computation (`duration_ms`, snapshot sizes); anchor recomputation (`comment_id`, outcome); timeline queries (`filter_summary`, `result_count`, `duration_ms`)
- [ ] 6.2 [GREEN] Verify index on timeline `(work_item_id, occurred_at DESC)` used by `EXPLAIN ANALYZE` in test environment
- [ ] 6.3 [GREEN] Verify diff endpoint p95 < 2s under 100KB payload
- [ ] 6.4 [GREEN] Add archival batch job: mark versions as `archived=true` when `COUNT > 500` per work item
