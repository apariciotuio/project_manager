# EP-07 — Technical Design: Comments, Versioning, Diff & Timeline

## 1. Version Model

> **Note**: The `work_item_versions` table is defined in EP-04 (base columns: `id`, `work_item_id`, `version_number`, `snapshot`, `created_by`, `created_at`). EP-07 extends it with an additive migration — do not re-create the table here.

### Decision: Full snapshot over delta

**Recommendation: Full snapshot (JSONB per version).**

Delta (change-set) is operationally simpler to write but requires replaying a chain to reconstruct any version — O(n) reconstruction, complex failure modes if a delta is corrupt, and harder to implement cross-version diff. Full snapshot makes reconstruction O(1), diff straightforward (two blobs, compare), and the storage overhead is acceptable for the expected load.

Storage math: A work item with 10 sections averaging 2KB per section = 20KB per snapshot. At 100 versions per item and 10,000 items: 20GB. Manageable with PostgreSQL JSONB + a compression column storage setting (`TOAST`). This is the right call at this scale. Delta can be adopted later if storage becomes a concern — the API contract does not change. ⚠️ originally MVP-scoped — see decisions_pending.md

### EP-07 additive migration on `work_item_versions`

```sql
ALTER TABLE work_item_versions
    ADD COLUMN snapshot_schema_version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN trigger               TEXT NOT NULL DEFAULT 'content_edit',  -- content_edit | state_transition | review_outcome | breakdown_change | manual
    ADD COLUMN actor_type            TEXT NOT NULL DEFAULT 'human',         -- human | ai_suggestion | system
    ADD COLUMN actor_id              UUID,                                   -- NULL for system
    ADD COLUMN commit_message        TEXT,                                   -- optional human label
    ADD COLUMN archived              BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX idx_wiv_archived ON work_item_versions (work_item_id, archived) WHERE archived = false;

-- Per db_review.md IDX-4: GET /work-items/:id/versions orders by version_number DESC.
-- Partial index on archived=false matches the default listing (archived versions hidden).
CREATE INDEX idx_wiv_work_item_version
    ON work_item_versions (work_item_id, version_number DESC)
    WHERE archived = false;
```

**Snapshot schema (v1):**
```json
{
  "schema_version": 1,
  "work_item": {
    "id": "uuid",
    "title": "string",
    "description": "string",
    "state": "string",
    "owner_id": "uuid"
  },
  "sections": [
    {
      "section_id": "uuid",
      "section_type": "string",
      "content": "string",
      "order": 0
    }
  ],
  "task_node_ids": ["uuid"]
}
```

Version number is assigned via `SELECT COALESCE(MAX(version_number), 0) + 1 FROM work_item_versions WHERE work_item_id = $1` inside a serializable transaction to avoid duplicates under concurrent writes.

> **IMPORTANT (Fixed per backend_review.md ALG-2)**: SQLAlchemy async defaults to `READ COMMITTED`. Under `READ COMMITTED`, two concurrent `MAX+1` reads on the same `work_item_id` produce identical numbers, resulting in a UNIQUE constraint violation at commit that surfaces as an unhandled DB error. The implementation MUST explicitly set `SERIALIZABLE` isolation:
> ```python
> async with session.begin():
>     await session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
>     # ... MAX+1 query and INSERT
> ```
> "serializable transaction" in this document means `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE` must be explicitly called — it is NOT the SQLAlchemy default.

---

## 2. Comment Model

> **EP-16 Integration — Inline Images**: Comments support inline images via EP-16's `attachments` table. When an image is pasted or dragged into the comment editor, an attachment row is created with `comment_id` set to the comment's `id`. Comment rendering parses markdown image syntax (`![alt](attachment_id)`) and substitutes signed URLs from EP-16's attachment endpoint at read time.
>
> When a comment is soft-deleted, its inline attachments are also soft-deleted via `CommentService` calling `AttachmentService.soft_delete_by_comment(comment_id)` in the same transaction. This is an application-layer cascade, not a DB cascade, to preserve the full audit trail of attachment metadata.
>
> No new tables are added to EP-07. EP-16's `attachments` table is reused with `comment_id` FK.

```sql
CREATE TABLE comments (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id          UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    parent_comment_id     UUID REFERENCES comments(id) ON DELETE SET NULL,
    body                  TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 10000),
    actor_type            TEXT NOT NULL,  -- human | ai_suggestion | system
    actor_id              UUID,
    -- Anchor fields
    anchor_section_id     UUID REFERENCES work_item_sections(id) ON DELETE SET NULL,
    anchor_start_offset   INTEGER,
    anchor_end_offset     INTEGER,
    anchor_snapshot_text  TEXT,           -- immutable copy of selected text at anchor time
    anchor_status         TEXT NOT NULL DEFAULT 'active',  -- active | orphaned
    -- Lifecycle
    is_edited             BOOLEAN NOT NULL DEFAULT false,
    edited_at             TIMESTAMPTZ,
    deleted_at            TIMESTAMPTZ,    -- soft delete
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT anchor_range_valid CHECK (
        (anchor_start_offset IS NULL AND anchor_end_offset IS NULL)
        OR (anchor_start_offset >= 0 AND anchor_end_offset >= anchor_start_offset)
    ),
    CONSTRAINT anchor_section_required_for_range CHECK (
        anchor_start_offset IS NULL OR anchor_section_id IS NOT NULL
    )
    -- NOTE: PostgreSQL does NOT allow subqueries inside CHECK constraints
    -- (`ERROR: cannot use subquery in check constraint`). The two invariants below
    -- are therefore enforced at the application layer, not at the DB:
    --
    -- 1. Max nesting depth = 1 (no nested replies). CommentService.create_reply
    --    refuses to create a reply when the parent_comment already has a non-NULL
    --    parent_comment_id. Rejected with 422 + code=COMMENT_NESTING_EXCEEDED.
    --
    -- 2. Anchor validation (anchor_section_id belongs to the same work_item as
    --    this comment). CommentService.create loads the section and verifies
    --    section.work_item_id == comment.work_item_id before INSERT. Rejected
    --    with 422 + code=COMMENT_ANCHOR_INVALID.
    --
    -- Rejected alternative: BEFORE INSERT trigger. Adds a DB-level side effect
    -- that is invisible from the service layer and makes tests require a live
    -- PostgreSQL instance. Application-layer checks keep the invariant in one
    -- place with the rest of the comment service logic.
);

CREATE INDEX idx_comments_work_item ON comments (work_item_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_comments_section ON comments (anchor_section_id) WHERE anchor_section_id IS NOT NULL;
CREATE INDEX idx_comments_parent ON comments (parent_comment_id) WHERE parent_comment_id IS NOT NULL;
```

---

## 3. Anchor Stability Strategy

Anchor stability is best-effort. The contract:

1. `anchor_section_id` (UUID) is the stable primary reference. Section UUIDs never change (sections are soft-deleted, not re-created).
2. `anchor_snapshot_text` is immutable — the exact text selected at anchor time.
3. On every section `content` update, a background task (Celery) re-locates all active anchors for that section:
   - Use `difflib.SequenceMatcher` to find the best match for `anchor_snapshot_text` in the new content.
   - If match ratio >= 0.8: update `anchor_start_offset` / `anchor_end_offset` silently.
   - If match ratio < 0.8: set `anchor_status = 'orphaned'`.
4. Section deletion triggers a bulk update: all anchors with `anchor_section_id = deleted_section_id` → `anchor_status = 'orphaned'`.

This runs asynchronously — the save operation does not block on anchor re-computation.

---

## 4. Diff Service

**Architecture: pure service layer, no persistence.**

```
DiffService
  .compute_version_diff(version_a_id, version_b_id) -> VersionDiff
  .compute_section_diff(section_a_content, section_b_content) -> SectionDiff
```

Two-pass diff:

**Pass 1 — structural (section-level):**
- Match sections between snapshot A and snapshot B by `section_type`.
- Classify each section as: `added`, `removed`, `modified`, `unchanged`, `reordered`.
- Use `section_type` as the match key (stable from EP-04). If `section_type` is duplicated (unlikely but possible), fall back to `section_id`.

**Pass 2 — content-level (per modified section):**
- Apply `difflib.unified_diff` (Python stdlib) on a line-by-line split of the section content.
- For character-level highlighting within changed lines, apply a second-pass word diff using `difflib.SequenceMatcher` on the changed lines only.
- Output format: list of `DiffHunk` objects (context lines, added lines, removed lines) — serialized to JSON for the API response.

**Markdown-aware diff (resolution #22)**: the diff viewer parses both snapshots with `remark` (Markdown AST) and aligns block nodes, then runs `diff-match-patch` on the inline text of each pair to produce a rich, granular diff suitable for the dual-pane accept/reject viewer (EP-03 diff UX). Fallback plain-text `difflib` path retained for non-Markdown fields.

Performance target: <= 2s for 100KB combined content. `difflib` on 100KB of text in CPython is well under 500ms. No async needed for the diff endpoint.

---

## 5. Timeline

### Decision: Unified query over source tables (no separate `timeline_events` table)

**Recommendation: Separate `timeline_events` table.**

A pure fan-out query over `audit_events + comments + review_responses + work_item_versions + export_events` with UNION ALL is tempting but produces an unmaintainable query, fragile ordering across mismatched schemas, and poor pagination (UNION ALL + cursor pagination is painful). It also couples timeline reads to the write schemas of every upstream table.

A `timeline_events` table is a write-side fan-in: each domain action writes to its own table AND appends a denormalized event to `timeline_events`. This is a simple append-only log. Reads are trivial. Pagination is a single `WHERE work_item_id = $1 AND occurred_at < $cursor ORDER BY occurred_at DESC LIMIT $n`. Adding new event types is a migration + one new writer — no query changes.

**Outbox pattern (resolution #22)**: the domain write and the timeline event are written in the same DB transaction, but the timeline-event row is inserted into a `timeline_events_outbox` table; a Celery worker consumes the outbox and publishes to the in-process event bus + Puppet index pipeline. This decouples the request path from fan-out and guarantees exactly-once delivery via the outbox.

```sql
CREATE TABLE timeline_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Per db_review.md DI-6: timeline is audit-like and must NOT be destroyed by
    -- work_item deletion. Work items are soft-deleted (deleted_at IS NOT NULL), never
    -- hard-deleted. RESTRICT blocks accidental hard-delete that would erase history.
    work_item_id    UUID NOT NULL REFERENCES work_items(id) ON DELETE RESTRICT,
    -- Per db_review.md SD-9: workspace_id denormalized to avoid JOIN through work_items
    -- on every timeline query. Hot path — justified denormalization.
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    actor_type      TEXT NOT NULL,
    actor_id        UUID,
    actor_display_name TEXT,
    summary         TEXT NOT NULL CHECK (char_length(summary) <= 255),
    payload         JSONB NOT NULL DEFAULT '{}',
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Back-references for joins (optional, populated at write time)
    source_id       UUID,   -- ID of the source record (comment_id, version_id, etc.)
    source_table    TEXT    -- 'comments' | 'work_item_versions' | 'review_responses' | 'export_events'
);

CREATE INDEX idx_timeline_work_item ON timeline_events (work_item_id, occurred_at DESC);
CREATE INDEX idx_timeline_event_type ON timeline_events (work_item_id, event_type);
CREATE INDEX idx_timeline_actor_type ON timeline_events (work_item_id, actor_type);
-- Per db_review.md IDX-5: stable cursor pagination needs id as tiebreaker within same occurred_at.
CREATE INDEX idx_timeline_cursor ON timeline_events (work_item_id, occurred_at DESC, id DESC);
-- Workspace-scoped timeline queries (admin views, audit listings).
CREATE INDEX idx_timeline_workspace_occurred ON timeline_events (workspace_id, occurred_at DESC);
```

Cursor pagination uses `(occurred_at, id)` composite cursor (serialize as base64 JSON) to handle ties at the same timestamp.

---

## 6. API Endpoints

All endpoints under `/api/v1/work-items/{work_item_id}/`.

### Comments

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/comments` | List comments (paginated, cursor-based) |
| `POST` | `/comments` | Create comment (general or anchored) |
| `GET` | `/comments/{comment_id}` | Get single comment with replies |
| `PATCH` | `/comments/{comment_id}` | Edit own comment body |
| `DELETE` | `/comments/{comment_id}` | Soft-delete own comment |
| `POST` | `/comments/{comment_id}/replies` | Add reply to comment |
| `GET` | `/sections/{section_id}/comments` | Comments anchored to a specific section |

### Versions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/versions` | List versions (reverse-chron, pagination) |
| `GET` | `/versions/{version_number}` | Get snapshot for a specific version |
| `GET` | `/versions/{version_number}/diff` | Diff this version against previous |
| `GET` | `/versions/diff?from={vn}&to={vn}` | Diff any two versions |

### Timeline

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/timeline` | Unified timeline for a work item (filtered, paginated). |
| `GET` | `/timeline/export?format=json|csv` | Export timeline (resolution #22). |
| `GET` | `/api/v1/users/:id/timeline` | Per-user timeline across all work items they interacted with (resolution #22). |

Query params: `event_types`, `actor_types`, `from_date`, `to_date`, `before` (cursor), `limit`.

Real-time push: new timeline events are streamed to subscribers via the shared SSE channel (same one used by presence + notifications, EP-17/EP-08).

Search: timeline entries are indexed in Puppet (EP-13) via the push-on-write pipeline and searchable from the main searchbar.

### Reactions and @mentions on comments (resolution #22)

```sql
CREATE TABLE comment_reactions (
    comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emoji      TEXT NOT NULL CHECK (char_length(emoji) BETWEEN 1 AND 16),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (comment_id, user_id, emoji)
);

CREATE TABLE comment_versions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    edited_by  UUID NOT NULL REFERENCES users(id),
    edited_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_comment_versions_comment ON comment_versions (comment_id, edited_at DESC);
```

- `@mentions` in comment bodies are parsed at write time; each mention emits a `notification` to the mentioned user via EP-08.
- Comment search is delegated to Puppet with tag `wm_comment` + workspace tag.

Endpoints:

| Method | Path | Description |
|---|---|---|
| POST | `/comments/:id/reactions` | Add a reaction `{ emoji }`. |
| DELETE | `/comments/:id/reactions/:emoji` | Remove own reaction. |
| GET | `/comments/:id/versions` | List edit history of a comment. |

### Version tagging (resolution #22)

```sql
CREATE TABLE version_tags (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES work_item_versions(id) ON DELETE CASCADE,
    label      TEXT NOT NULL CHECK (char_length(label) BETWEEN 1 AND 64),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (version_id, label)
);
```

Endpoint: `POST /versions/:version_number/tags` `{ label }`; `DELETE /versions/:version_number/tags/:label`.

### User-authored versions

Manual snapshots: `POST /versions/manual` with optional `{ commit_message }`. Creates a version with `trigger='manual'` and the provided message.

### Permanent version delete (resolution #22)

`DELETE /versions/:version_number` — Workspace Admin only; hard-deletes the row and any tags/diffs. Audited (`audit_events`). No cascade into other versions.

### No branch / fork / merge

Out of scope per resolution #22.

---

## 7. Storage Considerations

**Snapshot bloat mitigation (current approach):** ⚠️ originally MVP-scoped — see decisions_pending.md
- PostgreSQL TOAST compression handles JSONB > 2KB automatically. No action needed.
- `archived = true` flag excludes old versions from default queries without deleting data.

**Deferred options if storage becomes critical:**
1. Delta compression: store only changed sections in snapshot, reconstruct on read.
2. Cold storage: move `archived = true` snapshots to S3 as compressed JSON blobs; retain row with `snapshot = NULL, storage_url = 's3://...'`.
3. Retention policy: hard-delete versions older than N days for non-Ready/Archived items.

**Comment storage:** Negligible. Text rows, no blobs.

**Timeline storage:** One row per event. At 100 events/item × 10,000 items = 1M rows. Trivial.

---

## 8. Integration Points

| Dependency | Integration |
|------------|-------------|
| EP-01 | `state_transition` triggers version + timeline event. `audit_events` table is the authoritative write path — timeline mirrors it. EP-01's `TransitionService` calls `VersioningService.create_version(trigger='state_transition')`. |
| EP-04 | Section save triggers `content_edit` version + async anchor re-computation. `work_item_sections.id` is the stable anchor reference. EP-04's `SectionService` calls `VersioningService.create_version(trigger='section_edit')` — it does NOT INSERT to `work_item_versions` directly. |
| EP-05 | Breakdown save triggers `breakdown_change` version. EP-05's `TaskService` calls `VersioningService.create_version(trigger='breakdown_change')`. |
| EP-06 | Review submission triggers `review_outcome` version + `review_submitted` timeline event. EP-06 calls `VersioningService.create_version(trigger='review_outcome')`. |
| EP-11 | Export triggers `export_triggered` timeline event. EP-11 writes the event; EP-07 reads it via `timeline_events`. |

### Single-Writer Contract

`VersioningService` is the **sole owner** of all writes to `work_item_versions`. No service outside this epic may INSERT into that table directly. All callers inject `IVersioningService` (domain interface defined in EP-07) and call `create_version(work_item_id, trigger, actor_id, actor_type, commit_message=None)`. The interface is defined in `domain/ports/versioning_service.py` and injected via constructor DI into any service that needs it.

---

## 9. Non-functional Requirements

| Concern | Target | Approach |
|---------|--------|----------|
| Diff latency | <= 2s at 100KB | Synchronous, in-process `difflib` |
| Timeline query | <= 200ms p99 | Index on `(work_item_id, occurred_at DESC)`, cursor pagination |
| Snapshot write | <= 100ms overhead | Single INSERT inside existing transaction |
| Anchor re-computation | Async, best-effort | Celery task, no SLA |
| Concurrent version writes | No duplicate version numbers | Serializable transaction for version number assignment |
