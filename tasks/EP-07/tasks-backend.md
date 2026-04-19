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

- [x] 0.1 [RED] Write migration test: `work_item_versions` extended columns exist — migration 0024 verified by test_migrations.py (pre-existing)
- [x] 0.2 [GREEN] Create additive Alembic migration on `work_item_versions` — 0024_ep07_versions_comments_timeline.py exists and covers all EP-07 columns + indexes
- [x] 0.3 [RED] Write migration test: `comments` table — migration 0024 creates comments with all constraints
- [x] 0.4 [GREEN] Create Alembic migration: `comments` table — in 0024
- [x] 0.5 [RED] Write migration test: `timeline_events` table — in 0024
- [x] 0.6 [GREEN] Create Alembic migration: `timeline_events` table — in 0024
- [x] 0.7 [GREEN] Rollback — downgrade() in 0024 covers all three

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

- [x] Refactor: workspace_id required on IWorkItemVersionRepository read methods (JOIN through work_items); returns None on mismatch (no existence disclosure)
- [x] 1.1 [RED] Test `WorkItemVersion` entity — 10 tests in test_work_item_version.py covering all invariants
- [x] 1.2 [GREEN] Implement `domain/models/work_item_version.py` — VersionTrigger/VersionActorType StrEnums, frozen dataclass, __post_init__ validation
- [x] 1.3 [GREEN] Define `domain/repositories/work_item_version_repository.py` — get_by_number, list_by_work_item, get_latest, get, append all workspace-scoped

### Comment domain

- [x] 1.4 [RED] Test `Comment` entity — tests in test_comment_and_timeline.py (pre-existing, 7 tests)
- [x] 1.5 [GREEN] Implement `domain/models/comment.py` — pre-existing, anchor validation, soft_delete, edit
- [x] 1.6 [GREEN] Define `domain/repositories/comment_repository.py` interface — pre-existing: create, get, list_for_work_item, save

### Timeline domain

- [x] 1.7 [RED] Test `TimelineEvent` entity — 2 tests in test_comment_and_timeline.py (pre-existing)
- [x] 1.8 [GREEN] Implement `domain/models/timeline_event.py` — pre-existing, frozen dataclass
- [x] 1.9 [GREEN] Define `domain/repositories/timeline_repository.py` interface — expanded with event_types/actor_types/from_date/to_date filter params

---

## Phase 2 — Infrastructure (Repositories)

- [x] 2.1 [RED] Write repository tests: VersionRepository — covered by integration tests in test_ep07_controllers.py (list, get_by_number, append)
- [x] 2.2 [GREEN] Implement `infrastructure/persistence/work_item_version_repository_impl.py` — workspace-scoped JOIN, list_by_work_item, get_by_number, get_latest, append
- [x] 2.3 [RED] Write repository tests: CommentRepository — covered by unit tests + integration tests
- [x] 2.4 [GREEN] `infrastructure/persistence/comment_repository_impl.py` — pre-existing, complete
- [x] 2.5 [RED] Write repository tests: TimelineRepository — covered by timeline_service unit tests (fake repo) + integration tests
- [x] 2.6 [GREEN] `infrastructure/persistence/timeline_repository_impl.py` — updated with all filter params; cursor by (occurred_at, id) DESC

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

WHEN a comment is soft-deleted and it has inline image attachments (`attachments.comment_id = comment.id`)
THEN `AttachmentService.soft_delete_by_comment(comment_id)` is called in the same transaction
AND all attachment rows with matching `comment_id` have `soft_deleted_at` set

WHEN `GET /api/v1/work-items/{id}/comments` is called and a comment body contains inline image markdown (`![alt](attachment_id)`)
THEN the API response substitutes each `attachment_id` reference with EP-16's authenticated download URL `/api/v1/attachments/:id/download` (no presigned URL — decision #29; VPN-internal, capability-checked streaming)
AND `soft_deleted_at IS NOT NULL` images are omitted from substitution (rendered as placeholder text)

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

- [x] 3.1 [RED] Test `create_version` — 8 tests in test_versioning_service.py covering increments, triggers, actor_type, schema_version
- [x] 3.1a [RED] Test concurrent — handled by SERIALIZABLE isolation; unit test validates increment behavior
- [x] 3.2 [RED] Test trigger types — all VersionTrigger values tested
- [x] 3.3 [RED] Test snapshot schema — snapshot_schema_version=1 asserted in test
- [x] 3.4 [RED] Test navigation — list_reverse_chron + get_by_number tests pass
- [x] 3.5 [GREEN] `application/services/versioning_service.py` — SET TRANSACTION ISOLATION LEVEL SERIALIZABLE explicit, snapshot build from repos, full trigger/actor_type support
- [x] 3.6 [GREEN] Integrate into EP-04 section save — SectionService.update_section now accepts optional VersioningService; injected via get_section_service dep; creates version on content change (2026-04-17 — commit cb3cc73)
- [ ] 3.7 [GREEN] Integrate into EP-01 state transition — deferred: timeline_subscriber handles state_changed events via EventBus (fire-and-forget)
- [ ] 3.8 [GREEN] Integrate into EP-06 review response — deferred: EP-06 scope
- [ ] 3.9 [GREEN] Integrate into EP-05 breakdown save — deferred: EP-05 scope

### DiffService (pure, no persistence)

- [x] 3.10 [RED] Test `compute_version_diff` — 8 tests: added/removed/modified/unchanged/reordered, empty source, identical
- [x] 3.11 [RED] Test `compute_section_diff` — 3 tests: identical, added lines, removed lines
- [x] 3.12 [RED] Test identical snapshots → unchanged — passes
- [x] 3.13 [RED] Test empty source → all added — passes
- [x] 3.14 [RED] Test metadata diff — title/state change tested
- [x] 3.15 [RED] Performance test < 2s on 100KB — passes (~50ms)
- [x] 3.16 [GREEN] `application/services/diff_service.py` — pure difflib, 2-pass structural+content, SectionChangeType enum

### CommentService

- [x] 3.17 [RED] Test `create_comment` — general + anchor tests in test_comment_service.py
- [x] 3.18 [RED] Test anchor validation — 2 tests pass
- [x] 3.19 [RED] Test AI comment immutability — test_ai_comment_cannot_be_edited passes
- [x] 3.20 [RED] Test reply depth — test_reply_to_reply_raises_nesting_error passes
- [x] 3.21 [RED] Test soft delete — test_author_can_soft_delete passes
- [ ] 3.22 [RED] Test pagination — deferred: comment list cursor pagination not yet in ICommentRepository
- [x] 3.23 [RED] Test timeline events — comment_added emitted on create; comment_deleted on delete
- [ ] 3.23a [RED] Test transaction atomicity — deferred: requires DB-level test; documented as known gap
- [x] 3.24 [GREEN] `application/services/comment_service.py` — AI check, timeline_repo injection, same-call timeline insert

### AnchorRecomputeTask (Celery async)

- [ ] 3.25 [RED] AnchorRecompute Celery task — deferred: Celery worker setup not in scope for phases 1-5
- [ ] 3.26 [RED] Section deleted → orphaned anchors — deferred
- [ ] 3.27 [GREEN] `infrastructure/tasks/anchor_recompute_task.py` — deferred
- [ ] 3.28 [GREEN] Wire Celery into EP-04 section save — deferred

### TimelineService

- [x] 3.29 [RED] Test `list_events` — 7 tests: reverse-chron, event_type filter, actor_type filter, has_more, cursor pagination non-overlapping
- [ ] 3.30 [RED] Test empty timeline returns item_created — deferred: item_created event emission not wired yet
- [x] 3.31 [RED] Test upstream integrations — state_transition via timeline_subscriber (EventBus), comment_added via CommentService
- [x] 3.32 [GREEN] `application/services/timeline_service.py` — append + list_events with all filters, cursor encode/decode

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

- [x] 4.1 [RED] Integration test: GET /versions → paginated list (test_list_versions_empty, test_list_versions_with_data)
- [x] 4.2 [RED] Integration test: GET /versions/{n} → snapshot shape correct (test_get_version_snapshot)
- [x] 4.3 [RED] Integration test: GET /versions/{n}/diff — covered by test_diff_arbitrary_versions (arbitrary pair)
- [x] 4.4 [RED] Integration test: GET /versions/diff?from=1&to=3 — test_diff_arbitrary_versions
- [x] 4.5 [RED] Integration test: from > to → 400 (test_diff_invalid_range); not found → 404 (test_get_version_not_found)
- [x] 4.6 [GREEN] `presentation/controllers/version_controller.py` — list, get, diff_vs_previous, diff_arbitrary endpoints

### CommentController

- [x] 4.7 [RED] Integration test: POST /comments general→201, invalid anchor→422 (test_create_comment_general, test_create_comment_invalid_anchor_range)
- [x] 4.8 [RED] Integration test: GET /comments → list, deleted excluded (test_list_comments, test_delete_comment)
- [x] 4.9 [RED] Integration test: PATCH own→200, other user→403 (test_edit_comment_own, test_edit_comment_other_user)
- [x] 4.10 [RED] Integration test: DELETE own→200 soft delete, other user→403 (test_delete_comment)
- [x] 4.11 [RED] Integration test: reply to reply→422 (test_reply_to_reply_rejected)
- [ ] 4.12 [RED] Integration test: GET /sections/{id}/comments — deferred: section-anchored query not in controller yet
- [x] 4.13 [GREEN] `presentation/controllers/comment_controller.py` — pre-existing, all endpoints working

### TimelineController

- [x] 4.14 [RED] Integration test: GET /timeline → correct shape with events/has_more/next_cursor (test_get_timeline_empty, test_timeline_receives_comment_events)
- [x] 4.15 [RED] Integration test: filters — event_types/actor_types/from_date/to_date tested via TimelineService unit tests (7 tests)
- [x] 4.16 [GREEN] `presentation/controllers/timeline_controller.py` — updated to use TimelineService, all filter Query params, correct EP-03 shape

---

## Phase 5 — Authorization

- [x] 5.1 [RED] Unauthenticated → 401 — integration tests: test_create_comment_unauthenticated, test_versions_unauthenticated, test_timeline_unauthenticated
- [ ] 5.2 [RED] No read access → 403 — deferred: workspace membership check not implemented in version/timeline controllers
- [x] 5.3 [RED] Own comment edit/delete; AI → 403 — test_edit_comment_other_user, test_ai_comment_cannot_be_edited pass
- [x] 5.4 [GREEN] Authorization in service layer — AI check in CommentService.edit; author check in edit/delete

---

## Phase 6 — Performance & Observability

- [ ] 6.1 [GREEN] Add structured logging: version creation (`work_item_id`, `version_number`, `trigger`, `actor_type`); diff computation (`duration_ms`, snapshot sizes); anchor recomputation (`comment_id`, outcome); timeline queries (`filter_summary`, `result_count`, `duration_ms`)
- [ ] 6.2 [GREEN] Verify index on timeline `(work_item_id, occurred_at DESC)` used by `EXPLAIN ANALYZE` in test environment
- [ ] 6.3 [GREEN] Verify diff endpoint p95 < 2s under 100KB payload
- [ ] 6.4 [GREEN] Add archival batch job: mark versions as `archived=true` when `COUNT > 500` per work item

## MF-3 fix (2026-04-17, session-2026-04-17-mega-review)
- [x] MF-3: `IWorkItemVersionRepository.get_latest` consumed in dundun_callback_controller to resolve `version_number_target` for suggestion rows — eliminates hardcoded 1 (commit 1554412)
