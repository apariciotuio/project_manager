# EP-07 — Implementation Checklist

**Status: IN FLIGHT — Backend ~80% / Frontend ~80%**
**Last updated: 2026-04-18**

> The detailed checklist below is the original 2026-04-13 plan and is OUT OF DATE. Authoritative progress now lives in:
> - `tasks/EP-07/tasks-backend.md` — backend progress + DoD
> - `tasks/EP-07/tasks-frontend.md` — frontend Groups 1–7 progress
>
> 2026-04-18 session deltas (FE) — 12 commits in one pass:
> - Groups 1, 2, 3a, 3b shipped (cf06aec — diff viewer + comment hooks)
> - Group 5 (Timeline filters + tab) shipped (386965e + eeb2d21) — TimelineFilters component + useTimeline filter forwarding + i18n + filtered-empty state.
> - Group 6.1 + 6.2 shipped (d242163) — explicit tab-presence assertion.
> - Group 4 partially covered (5691218 + 605da0b) — CommentsTab schema-aligned with new Comment shape (actor_type/actor_id, anchor_status, replies); 4.1/4.2/4.3/4.4/4.5/4.6 marked [~] as functionally covered by inline CommentItem/CommentForm/CommentsTab; 4.3a DEFERRED (blocked on EP-16 v2).
> - Group 6.4 + 6.5 shipped (ecf66a2) — inline DiffContent preview at top of VersionHistoryPanel showing latest-vs-previous diff on initial load.
> - Group 7.1/7.2/7.3/7.4/7.6/7.7 shipped (4cc87aa) — VersionDiffViewerSkeleton + CommentFeedSkeleton extracted into `skeletons.tsx`; useDiffVsPrevious exposes `refetch`; DiffContent error state now has retry button. 7.5 (mobile) DEFERRED.
> - Group 6.3 shipped (8923681) — CommentsProvider + CommentCountBadge with shared useComments instance; optimistic update flows from form submission to trigger badge without page reload.
>
> Remaining FE: 4.7/4.8/4.9/4.10 — AnchoredCommentMarker + AnchoredCommentPopover + integration into SpecificationSectionsEditor (EP-04 component). That's a scope-heavy new feature slice, not a closure; should be re-planned.

---

## Phase 0 — Data Model (Migrations)

- [ ] **[TDD]** Write migration tests: assert `work_item_versions` table exists with correct columns, constraints, indexes
- [ ] Create migration: `work_item_versions` table (snapshot JSONB, version_number unique per work_item, trigger enum, actor fields, archived flag)
- [ ] **[TDD]** Write migration tests: assert `comments` table exists with correct columns, check constraints (anchor_range_valid, no_deep_nesting), indexes
- [ ] Create migration: `comments` table (body, anchor fields, actor fields, soft delete, parent_comment_id)
- [ ] **[TDD]** Write migration tests: assert `timeline_events` table exists with correct columns, indexes
- [ ] Create migration: `timeline_events` table (event_type, actor fields, summary, payload JSONB, occurred_at, source_id, source_table)
- [ ] Run all migrations against a test DB — verify rollback works

---

## Phase 1 — Domain Layer

### Version domain

- [ ] **[TDD-RED]** Test `WorkItemVersion` entity: immutability after creation, version_number scoping, snapshot validation
- [ ] Implement `WorkItemVersion` entity in `domain/models/`
- [ ] **[TDD-RED]** Test `IVersionRepository` interface contract (get_by_id, list_by_work_item, get_latest, get_by_number)
- [ ] Implement `VersionRepository` in `infrastructure/persistence/`

### Comment domain

- [ ] **[TDD-RED]** Test `Comment` entity: anchor constraint validation, soft delete, reply depth enforcement, AI comment immutability
- [ ] Implement `Comment` entity in `domain/models/`
- [ ] **[TDD-RED]** Test `ICommentRepository` interface contract (create, get, list_by_work_item, list_by_section, soft_delete, update_anchor)
- [ ] Implement `CommentRepository` in `infrastructure/persistence/`

### Timeline domain

- [ ] **[TDD-RED]** Test `TimelineEvent` entity: required fields, summary length constraint, valid event_type enum
- [ ] Implement `TimelineEvent` entity in `domain/models/`
- [ ] **[TDD-RED]** Test `ITimelineRepository` interface contract (append, list_by_work_item with filters and cursor pagination)
- [ ] Implement `TimelineRepository` in `infrastructure/persistence/`

---

## Phase 2 — Application Services

### Versioning service

- [ ] **[TDD-RED]** Test `VersioningService.create_version()`: correct snapshot content, version_number increments, idempotency under concurrent calls (serializable tx)
- [ ] **[TDD-RED]** Test version triggers: content_edit, state_transition, review_outcome, breakdown_change each produce a version
- [ ] **[TDD-RED]** Test snapshot schema: all required fields present, sections array correct, task_node_ids included
- [ ] Implement `VersioningService` in `application/services/`
- [ ] **[TDD-RED]** Test version navigation: get_by_number returns correct snapshot, list returns reverse-chron order, archived excluded by default
- [ ] Integrate `VersioningService.create_version()` call into EP-04 section save path (content_edit trigger)
- [ ] Integrate into EP-01 state transition handler (state_transition trigger)
- [ ] Integrate into EP-06 review response handler (review_outcome trigger)
- [ ] Integrate into EP-05 breakdown save path (breakdown_change trigger)

### Diff service

- [ ] **[TDD-RED]** Test `DiffService.compute_version_diff()`: sections added/removed/modified/unchanged/reordered correctly classified
- [ ] **[TDD-RED]** Test `DiffService.compute_section_diff()`: line-level diff correct, word-level highlighting on changed lines, unchanged sections collapsed
- [ ] **[TDD-RED]** Test diff with identical snapshots: all sections marked unchanged
- [ ] **[TDD-RED]** Test diff with empty source (first version): all sections marked added
- [ ] **[TDD-RED]** Test diff performance: 100KB combined content < 2s
- [ ] Implement `DiffService` in `application/services/` using `difflib`
- [ ] **[TDD-RED]** Test metadata diff: title, description, state changes appear in metadata diff panel

### Comment service

- [ ] **[TDD-RED]** Test `CommentService.create_comment()`: general comment, section-anchored comment, range-anchored comment each produce correct records
- [ ] **[TDD-RED]** Test anchor validation: start > end rejected, section_id required when range provided, offset > section length rejected
- [ ] **[TDD-RED]** Test AI comment immutability: edit attempt on ai_suggestion comment raises error
- [ ] **[TDD-RED]** Test reply depth: reply to reply rejected
- [ ] **[TDD-RED]** Test soft delete: body replaced with "[deleted]" on parent with replies, replies retained
- [ ] **[TDD-RED]** Test pagination: cursor-based, page size respected, has_more accurate
- [ ] Implement `CommentService` in `application/services/`
- [ ] **[TDD-RED]** Test `CommentService` appends `comment_added` event to `timeline_events` on create
- [ ] **[TDD-RED]** Test `CommentService` appends `comment_deleted` event to `timeline_events` on soft delete

### Anchor re-computation (async)

- [ ] **[TDD-RED]** Test `AnchorRecomputeTask`: snapshot_text found at new offset → offsets updated, anchor_status = active
- [ ] **[TDD-RED]** Test `AnchorRecomputeTask`: snapshot_text not found (ratio < 0.8) → anchor_status = orphaned
- [ ] **[TDD-RED]** Test `AnchorRecomputeTask`: section deleted → all anchors to that section orphaned
- [ ] Implement `AnchorRecomputeTask` as Celery task in `infrastructure/tasks/`
- [ ] Wire Celery task dispatch into EP-04 section save (after version snapshot is written)

### Timeline service

- [ ] **[TDD-RED]** Test `TimelineService.list_events()`: returns all event types in reverse-chron order
- [ ] **[TDD-RED]** Test filtering: event_type filter, actor_type filter, date range filter — each narrows results correctly
- [ ] **[TDD-RED]** Test cursor pagination: correct results for page 1 and page 2, has_more=false on last page
- [ ] **[TDD-RED]** Test empty timeline: returns item_created event, has_more=false
- [ ] **[TDD-RED]** Test all upstream integrations write to timeline_events (state_transition, review_submitted, export_triggered)
- [ ] Implement `TimelineService` in `application/services/`

---

## Phase 3 — Controllers & API

### Version endpoints

- [ ] **[TDD-RED]** Integration test: `GET /versions` returns paginated list, correct schema
- [ ] **[TDD-RED]** Integration test: `GET /versions/{version_number}` returns correct snapshot
- [ ] **[TDD-RED]** Integration test: `GET /versions/{version_number}/diff` returns structured diff vs previous
- [ ] **[TDD-RED]** Integration test: `GET /versions/diff?from=1&to=3` returns diff for arbitrary pair
- [ ] **[TDD-RED]** Integration test: `GET /versions/diff` with from > to returns 400
- [ ] Implement `VersionController` in `presentation/controllers/`

### Comment endpoints

- [ ] **[TDD-RED]** Integration test: `POST /comments` creates general comment, returns 201
- [ ] **[TDD-RED]** Integration test: `POST /comments` with section anchor creates anchored comment, returns 201
- [ ] **[TDD-RED]** Integration test: `POST /comments` with invalid anchor range returns 422
- [ ] **[TDD-RED]** Integration test: `GET /comments` returns paginated list
- [ ] **[TDD-RED]** Integration test: `PATCH /comments/{id}` edits own comment, returns 200; editing other's comment returns 403
- [ ] **[TDD-RED]** Integration test: `DELETE /comments/{id}` soft-deletes, returns 204
- [ ] **[TDD-RED]** Integration test: `POST /comments/{id}/replies` creates reply, rejects reply-to-reply with 422
- [ ] **[TDD-RED]** Integration test: `GET /sections/{section_id}/comments` returns anchored comments for section
- [ ] Implement `CommentController` in `presentation/controllers/`

### Timeline endpoint

- [ ] **[TDD-RED]** Integration test: `GET /timeline` returns all events, correct schema
- [ ] **[TDD-RED]** Integration test: `GET /timeline?event_types=state_transition` filters correctly
- [ ] **[TDD-RED]** Integration test: `GET /timeline?actor_types=ai_suggestion` filters correctly
- [ ] **[TDD-RED]** Integration test: `GET /timeline?from_date=...&to_date=...` filters correctly
- [ ] **[TDD-RED]** Integration test: `GET /timeline` cursor pagination returns correct pages, has_more accurate
- [ ] Implement `TimelineController` in `presentation/controllers/`

---

## Phase 4 — Authorization

- [ ] **[TDD-RED]** Test: unauthenticated requests to all EP-07 endpoints return 401
- [ ] **[TDD-RED]** Test: users without work_item read access cannot read versions, comments, or timeline (403)
- [ ] **[TDD-RED]** Test: users can only edit/delete their own comments (not other users' comments)
- [ ] **[TDD-RED]** Test: AI comments cannot be edited by any user (403 on PATCH)
- [ ] Implement authorization checks in service layer (not controller)

---

## Phase 5 — End-to-End Scenarios

- [ ] E2E test: full content edit cycle — edit section → version created → diff readable → timeline shows content_edit event
- [ ] E2E test: anchor comment → edit section → anchor re-computed (Celery task runs) → comment still active with updated offsets
- [ ] E2E test: anchor comment → delete section → comment marked orphaned → visible in general feed
- [ ] E2E test: state transition → version created → timeline shows state_transition event
- [ ] E2E test: review submitted → version created → timeline shows review_submitted event with outcome in payload

---

## Phase 6 — Performance & Observability

- [ ] Add structured logging for: version creation (work_item_id, version_number, trigger, actor_type), diff computation (duration_ms, snapshot_sizes), anchor re-computation (comment_id, outcome), timeline queries (work_item_id, filter summary, result_count, duration_ms)
- [ ] Verify index usage on timeline query via `EXPLAIN ANALYZE` in test environment
- [ ] Verify diff endpoint p95 latency < 2s under 100KB payload in load test
- [ ] Add `archived` batch job: mark versions as archived when count > 500 per work_item

---

## Completion Criteria

All checkboxes above marked. No `[ ]` remaining. Each phase verified by running full test suite before moving to next.

**Status: IN PROGRESS / COMPLETED** — update when phases complete.
