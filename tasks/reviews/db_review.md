# Database Review

**Date**: 2026-04-13
**Scope**: ~30 tables across 13 epics, PostgreSQL 16+
**Reviewer**: db-reviewer agent

---

## Schema Design Issues

### SD-1. `workspace_memberships` Missing `state` and `capabilities` Columns (CRITICAL)

EP-00 `workspace_memberships` has no `state` column. Every middleware checks `member.state == 'active'`. EP-10 adds `capabilities` via ALTER but `state` is never defined anywhere. The table is also named `workspace_memberships` in EP-00 but `workspace_members` in `tech_info.md`.

**Impact**: All authenticated requests will crash on the member state check.

**Fix**: Add to EP-00 CREATE TABLE:
```sql
state VARCHAR(50) NOT NULL DEFAULT 'active',
capabilities TEXT[] NOT NULL DEFAULT '{}'
```
Remove EP-10's ALTER for capabilities. Standardize the table name.

### SD-2. `projects` Table Referenced Before Creation

EP-01 `work_items.project_id UUID NOT NULL REFERENCES projects(id)` but `projects` is defined in EP-10 (migration order position 10). EP-01 migration runs at position 2.

**Impact**: Migration failure. `ERROR: relation "projects" does not exist`.

**Fix**: Create `projects` in EP-00 or a dedicated pre-EP-01 migration with minimal columns (`id`, `workspace_id`, `name`, `status`, `created_at`). EP-10 extends via ALTER.

### SD-3. Two Audit Tables With Overlapping Purpose

EP-00 defines `audit_logs` (auth events). EP-10 defines `audit_events` (admin/domain actions). Nearly identical schemas, different names, no shared service.

**Fix**: Merge into `audit_events` with a `category` column (`auth | admin | domain`). Auth events carry IP/user_agent in the `context` JSONB. Single write path.

### SD-4. EP-06 ALTER TABLE Duplicates EP-01 Columns

EP-06 still carries `ALTER TABLE work_items ADD COLUMN has_override...` but EP-01's CREATE TABLE already defines these columns. Running EP-06 migration will fail with `column "has_override" of relation "work_items" already exists`.

**Fix**: Remove the ALTER block from EP-06.

### SD-5. `work_items.workspace_id` Missing

EP-01's `work_items` has no `workspace_id` column. Security review CRIT-2 requires workspace scoping on every query. Currently the only path to workspace is through `project_id -> projects.workspace_id`, forcing a JOIN on every access check.

**Impact**: Every single query that enforces workspace isolation requires a JOIN to `projects`. At 10K work items, that JOIN is on every request.

**Fix**: Add `workspace_id UUID NOT NULL REFERENCES workspaces(id)` directly on `work_items`. Denormalization is justified -- this column is in every WHERE clause.

### SD-6. `work_item_versions` Dual Ownership

EP-04 creates the base table. EP-07 ALTERs it with 6 new columns. EP-04's `SectionService.save()` writes version rows. EP-07's `VersioningService` also writes version rows. Two writers, different column awareness.

**Impact**: EP-04 inserts will have wrong defaults (`trigger = 'content_edit'`, `actor_type = 'human'` regardless of actual trigger).

**Fix**: Single `VersioningService` (EP-07) owns all writes. EP-04 calls it, never inserts directly.

### SD-7. `assistant_suggestions` vs `SuggestionSet + SuggestionItem`

EP-03 design defines a two-table pattern (`SuggestionSet` + `SuggestionItem`). `tech_info.md` documents a flat `assistant_suggestions` table. Two incompatible schemas for the same concept.

**Fix**: Adopt EP-03's two-table design. Update `tech_info.md`.

### SD-8. `sessions` vs `refresh_tokens` Naming Inconsistency

EP-00 calls it `sessions`. `tech_info.md` calls it `refresh_tokens`. Pick one.

### SD-9. Missing `workspace_id` on `comments`, `task_nodes`, `timeline_events`

These tables reference `work_items(id)` but don't carry `workspace_id` directly. Workspace-scoped queries require a JOIN through `work_items`. For hot-path queries (comment listing, timeline), this adds latency.

**Fix**: Add `workspace_id` as a denormalized column on `comments`, `timeline_events`, and `notifications`. Not on `task_nodes` (always accessed via work_item_id). Index it.

### SD-10. `validation_requirements` Uses `rule_id VARCHAR(100)` as PK

String PKs are slower for JOINs than UUIDs. More importantly, this is a seeded lookup table with human-readable IDs (`spec_review_complete`), which means renames require cascading FK updates.

**Impact**: Low at MVP scale, but a trap.

**Fix**: Acceptable for MVP since the table is tiny and seeded. Document that `rule_id` values are immutable identifiers, not display names.

---

## Missing Indexes (will cause slow queries)

### IDX-1. `work_items` Missing Composite for Workspace-Scoped Listing

Every list query filters by `workspace_id` (after SD-5 fix). No index covers `(workspace_id, state, updated_at)`.

```sql
CREATE INDEX idx_work_items_ws_state_updated
  ON work_items(workspace_id, state, updated_at DESC)
  WHERE deleted_at IS NULL;
```

### IDX-2. `review_requests` Inbox Query Uses `reviewer_id` + `status`, Not `assignee_user_id`

EP-08 inbox query references `assignee_user_id` -- phantom column. The actual column is `reviewer_id`. Current partial index `idx_review_requests_reviewer` on `reviewer_id WHERE reviewer_id IS NOT NULL` is correct but missing the `status` filter.

```sql
CREATE INDEX idx_review_requests_reviewer_pending
  ON review_requests(reviewer_id, status)
  WHERE reviewer_id IS NOT NULL AND status = 'pending';
```

### IDX-3. `notifications` Missing Index for Unread Count Badge

`GET /api/v1/notifications/unread-count` needs:
```sql
CREATE INDEX idx_notifications_unread_count
  ON notifications(recipient_id, workspace_id)
  WHERE state = 'unread';
```

The existing `idx_notifications_recipient_unread` lacks `workspace_id`.

### IDX-4. `work_item_versions` Missing Index for Version Listing

`GET /work-items/:id/versions` orders by `version_number DESC`. Current index `idx_wiv_work_item_created` is on `(work_item_id, created_at DESC)`. Add:

```sql
CREATE INDEX idx_wiv_work_item_version
  ON work_item_versions(work_item_id, version_number DESC)
  WHERE archived = false;
```

### IDX-5. `timeline_events` Missing Composite for Filtered Queries

Timeline endpoint accepts `event_types` and `actor_types` filters. The per-column indexes `idx_timeline_event_type` and `idx_timeline_actor_type` both include `work_item_id` as prefix -- good. But the main timeline cursor index should include `id` for stable cursor pagination:

```sql
CREATE INDEX idx_timeline_cursor
  ON timeline_events(work_item_id, occurred_at DESC, id DESC);
```

### IDX-6. `work_item_sections` Missing Composite for Completeness Query

`CompletenessService` fetches sections by `work_item_id` and checks `is_required` and `content`. The single-column index is fine, but adding `is_required` helps:

```sql
CREATE INDEX idx_wis_completeness
  ON work_item_sections(work_item_id, is_required, section_type);
```

### IDX-7. `validation_statuses` Missing Index for Ready Gate

`ReadyGateService.check()` queries `validation_statuses WHERE work_item_id = ? AND rule_id IN (...)`. Current index is on `(work_item_id)` only. Add:

```sql
CREATE INDEX idx_validation_statuses_gate
  ON validation_statuses(work_item_id, status)
  WHERE status NOT IN ('passed', 'obsolete');
```

### IDX-8. EP-09 Search `tsvector` Column Not Auto-Maintained

EP-09 adds `search_vector tsvector` on `work_items` with a GIN index but relies on application-layer maintenance (SQLAlchemy `after_flush` or PG trigger). No trigger is defined in the DDL.

**Fix**: Define the trigger in the migration:
```sql
CREATE FUNCTION work_items_search_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B');
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_work_items_search
  BEFORE INSERT OR UPDATE OF title, description ON work_items
  FOR EACH ROW EXECUTE FUNCTION work_items_search_update();
```

Async content (comments, tasks) updated via Celery is acceptable.

### IDX-9. EP-10 `validation_rules` Missing Partial UNIQUE for Workspace Scope

Two workspace-level rules for the same `(workspace_id, work_item_type, validation_type)` silently overwrite each other in the precedence engine.

```sql
CREATE UNIQUE INDEX uq_validation_rules_workspace
  ON validation_rules(workspace_id, work_item_type, validation_type)
  WHERE project_id IS NULL AND active = true;
```

### IDX-10. Over-Indexing on `users`

EP-00 creates `idx_users_google_sub` on `google_sub` AND a UNIQUE constraint on `google_sub`. The UNIQUE constraint already creates an implicit unique index. Same for `email`. Two of the three indexes are redundant.

**Fix**: Remove explicit `CREATE INDEX` for `google_sub` and `email`. UNIQUE constraints handle it.

Similarly, `workspaces` has both `UNIQUE(slug)` and `CREATE UNIQUE INDEX idx_workspaces_slug ON workspaces(slug)`. Remove the explicit index.

---

## Query Performance Risks (top 10 expensive queries)

### Q1. Inbox UNION Query (EP-08) -- BROKEN AND SLOW

The inbox query has 4 phantom references (see architect review C1). Even when fixed to 2 tiers, the UNION ALL across `review_requests + work_items + team_memberships` with subquery exclusion `NOT IN (SELECT review_request_id FROM review_responses)` is an anti-join that will degrade.

**Fix**: Replace `NOT IN` with `NOT EXISTS` (avoids NULL pitfalls, uses anti-join optimization). Add `LIMIT 50` per sub-query. At 10K items:
```sql
-- Tier 1 (team reviews): use NOT EXISTS instead of NOT IN
WHERE rr.status = 'pending'
  AND NOT EXISTS (
    SELECT 1 FROM review_responses resp
    WHERE resp.review_request_id = rr.id
  )
```

**Estimated cost at 10K items**: Without fix, ~50ms per tier (200ms total). With NOT EXISTS + partial indexes, ~15ms per tier.

### Q2. Dashboard Aggregation (EP-09/EP-10) -- COUNT(*) GROUP BY state

```sql
SELECT state, COUNT(*), AVG(...) FROM work_items WHERE workspace_id = ? GROUP BY state
```

Full table scan within workspace. At 10K items per workspace, this is ~20ms (acceptable). At 100K, ~200ms.

**Mitigation**: Redis cache (120s TTL) is already designed. Cold query needs the workspace-scoped index (IDX-1).

### Q3. Pipeline View (EP-09) -- ROW_NUMBER Window Function

The pipeline query uses `ROW_NUMBER() OVER (PARTITION BY state ORDER BY updated_at DESC)` with a filter `WHERE rn <= 20`. PostgreSQL must sort the entire result set before applying the row number.

**Estimated cost at 10K items**: ~80ms. Acceptable. At 100K: ~800ms (exceeds 300ms target).

**Fix for scale**: Use a lateral join pattern instead:
```sql
SELECT DISTINCT ON (state) state, ... FROM work_items
```
Or better: query each state separately with `LIMIT 20` -- 7 queries x ~5ms = 35ms total.

### Q4. Full-Text Search (EP-09) -- tsvector + GIN

Well-designed. GIN index will handle <100K documents under 300ms. The `ts_headline` calls add ~10ms per result. With `LIMIT 25`, this is fine.

**Risk**: `aggregated_comment_text` and `aggregated_task_text` are denormalized columns. If async update falls behind, search results are stale.

### Q5. Detail View Assembly (EP-09) -- 5 selectinload Queries

```python
selectinload(WorkItem.tasks),
selectinload(WorkItem.validation_requirements),
selectinload(WorkItem.review_requests).selectinload(ReviewRequest.responses),
selectinload(WorkItem.comments).selectinload(Comment.author),
```

5 SQL queries total. Each is indexed. At 100 comments per item, the comment query returns ~100 rows -- fine. At 1000 comments, the `selectinload(Comment.author)` fires a second query with 1000 author UUIDs (`WHERE id IN (...)`) -- this is still fast but watch the IN-list size.

**Risk**: No pagination on comments within the detail view. 1000+ comments loaded in one shot.

**Fix**: Cap comments at `LIMIT 100` in the detail view. Lazy-load the rest.

### Q6. Timeline Cursor Pagination (EP-07)

```sql
WHERE work_item_id = $1 AND occurred_at < $cursor ORDER BY occurred_at DESC LIMIT 50
```

With `idx_timeline_work_item` on `(work_item_id, occurred_at DESC)`, this is an index-only scan. Fast at any scale.

### Q7. Completeness Computation (EP-04) -- 3 Queries on Cache Miss

On cache miss: sections query + validators query + work_item query. All by `work_item_id` (indexed). Total: ~5ms. Redis absorbs repeated calls. No concern.

### Q8. Version Diff (EP-07) -- Two JSONB Reads

Reads two `work_item_versions.snapshot` JSONB blobs (~20KB each). TOAST decompression adds ~2ms per blob. Diff computation in Python is ~50ms for 100KB total. Well within 2s target.

### Q9. Audit Log Listing (EP-10)

```sql
WHERE workspace_id = ? AND created_at < ? ORDER BY created_at DESC LIMIT 50
```

Indexed. At 1M rows, the partial scan is fast. No concern until 10M+ rows (partition by month at that point).

### Q10. `total_count` on Every Paginated List (EP-09)

Every list endpoint runs `COUNT(*)` with the same WHERE clause. This is a full index scan. At 10K items: ~10ms. At 100K: ~100ms added to every list request.

**Fix**: Make `total_count` opt-in (`?include_count=true`). Default to omitting it. Frontend shows "Load more" instead of "Page X of Y".

---

## Data Integrity Gaps

### DI-1. No FK from `work_items.current_version_id` to `work_item_versions`

EP-01 comments out the FK with a note "added in EP-07 migration". If EP-07 migration fails or is skipped, `current_version_id` can reference non-existent version rows. Every diff and review-pinning query breaks silently.

**Fix**: The FK must be in the EP-07 migration as a hard requirement. Add a CHECK constraint or a migration test that verifies the FK exists.

### DI-2. `review_requests.version_id` References `work_item_versions` Before Table Exists

EP-06 creates `review_requests` with `version_id UUID NOT NULL REFERENCES work_item_versions(id)`. EP-04 creates `work_item_versions`. Migration order must have EP-04 before EP-06. Verify this is enforced.

### DI-3. `comments.no_deep_nesting` CHECK Constraint is a Subquery in CHECK

```sql
CONSTRAINT no_deep_nesting CHECK (
    parent_comment_id IS NULL
    OR (SELECT parent_comment_id FROM comments c2 WHERE c2.id = parent_comment_id) IS NULL
)
```

**PostgreSQL does not allow subqueries in CHECK constraints.** This will fail at table creation. `ERROR: cannot use subquery in check constraint`.

**Fix**: Enforce nesting depth in the application layer (service layer check before INSERT). Remove the CHECK constraint. Add a comment documenting the invariant.

### DI-4. `task_dependencies` Missing Cross-Work-Item Guard at DB Level

The UNIQUE constraint `(task_id, depends_on_id)` and the self-dependency CHECK exist, but there's no DB-level check that both tasks belong to the same `work_item_id`. Cross-work-item dependencies are explicitly out of scope for MVP.

**Fix**: Add a trigger or application-layer check. A trigger is simpler:
```sql
CREATE FUNCTION check_same_work_item() RETURNS trigger AS $$
BEGIN
  IF (SELECT work_item_id FROM task_nodes WHERE id = NEW.task_id) !=
     (SELECT work_item_id FROM task_nodes WHERE id = NEW.depends_on_id) THEN
    RAISE EXCEPTION 'Dependencies must be within the same work item';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_task_dep_same_wi
  BEFORE INSERT ON task_dependencies
  FOR EACH ROW EXECUTE FUNCTION check_same_work_item();
```

### DI-5. `integration_exports.version_id` Has No FK

EP-11 declares `version_id UUID NOT NULL` with a comment "version at time of export" but no `REFERENCES work_item_versions(id)`. Orphan risk if versions are ever hard-deleted.

**Fix**: Add the FK: `REFERENCES work_item_versions(id)`.

### DI-6. CASCADE Behavior Review

| FK | ON DELETE | Risk |
|----|-----------|------|
| `work_items -> projects` | None (default RESTRICT) | Correct. Cannot delete project with items. |
| `work_items -> users (owner_id)` | None (RESTRICT) | Correct. Cannot delete user who owns items. |
| `comments -> work_items` | CASCADE | Correct. Item deletion cleans comments. |
| `task_nodes -> work_items` | CASCADE | Correct. |
| `timeline_events -> work_items` | CASCADE | **Risky.** Timeline is audit-like. Deleting a work item destroys its history. |
| `review_requests -> work_items` | CASCADE | Correct for soft-delete items. |
| `team_memberships -> teams` | None specified | Should be CASCADE or RESTRICT. Missing. |

**Fix**: `timeline_events` should use `ON DELETE SET NULL` on `work_item_id` or better, `ON DELETE RESTRICT` (work items are soft-deleted, never hard-deleted). Add `ON DELETE CASCADE` to `team_memberships -> teams`.

### DI-7. No `ON DELETE` Specified for `notifications -> workspaces`

EP-08 `notifications.workspace_id` has no ON DELETE clause. If a workspace is ever deleted, orphan notifications remain.

**Fix**: `ON DELETE CASCADE` (workspace deletion cascades to notifications).

---

## Migration Safety Issues

### MS-1. EP-07 ALTER on `work_item_versions` Adds NOT NULL Columns Without Defaults

```sql
ALTER TABLE work_item_versions
    ADD COLUMN trigger TEXT NOT NULL DEFAULT 'content_edit',
```

This is safe because `DEFAULT` is specified. PostgreSQL 11+ rewrites the default lazily (no table rewrite). Verified safe.

### MS-2. EP-09 Adding `search_vector tsvector` Column to `work_items`

```sql
ALTER TABLE work_items ADD COLUMN search_vector tsvector;
```

Nullable, no default -- no table rewrite. Safe. But the GIN index creation:

```sql
CREATE INDEX idx_work_items_search ON work_items USING GIN (search_vector);
```

**This takes an ACCESS EXCLUSIVE lock on the table.** At 10K rows, ~5 seconds of downtime. At 100K rows, ~30 seconds.

**Fix**: Use `CREATE INDEX CONCURRENTLY`:
```sql
CREATE INDEX CONCURRENTLY idx_work_items_search ON work_items USING GIN (search_vector);
```

Note: `CONCURRENTLY` cannot run inside a transaction block. Alembic migrations run inside transactions by default. Use a separate migration step with `op.execute()` outside the transaction.

### MS-3. EP-10 Adding GIN Index on `capabilities` Array

Same issue as MS-2:
```sql
CREATE INDEX idx_workspace_memberships_capabilities ON workspace_memberships USING GIN (capabilities);
```

At MVP scale this is trivial, but use `CONCURRENTLY` as a habit.

### MS-4. EP-05 `gin_trgm_ops` Requires `pg_trgm` Extension

```sql
CREATE INDEX idx_task_nodes_mat_path ON task_nodes USING gin(materialized_path gin_trgm_ops);
```

Requires:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

If this is not in the migration, the index creation fails. Verify the extension is created in a pre-migration step.

### MS-5. Backfill `search_vector` After Column Addition

Adding the column is instant. But existing rows have `NULL` search vectors. A backfill UPDATE of 10K rows takes ~2 seconds. At 100K rows, ~20 seconds.

**Fix**: Run backfill in batches:
```sql
UPDATE work_items SET search_vector = ... WHERE id IN (SELECT id FROM work_items WHERE search_vector IS NULL LIMIT 1000);
```
Repeat in a loop. Or run as a Celery task post-migration.

---

## Growth & Partitioning Recommendations

### GP-1. `work_item_versions` -- The Storage Problem

**Math at MVP**: 20KB/snapshot x 100 versions x 10K items = 20GB. TOAST compresses ~60%, so ~8GB on disk. Manageable.

**Math at 10x (100K items)**: 200GB raw, ~80GB compressed. VACUUM on this table becomes painful (autovacuum takes minutes). Index maintenance on 10M rows adds write overhead.

**Recommendation**:
1. Implement the `archived` column (already designed in EP-07). Background job archives versions older than 90 days keeping latest 10.
2. At 10x: Partition by `work_item_id` range or by `created_at` month. Monthly partitions enable cheap `DROP PARTITION` for old data.

### GP-2. `timeline_events` -- Append-Only Growth

**Math**: 100 events/item x 10K items = 1M rows (MVP). At 10x: 10M rows. Each row is ~500 bytes = 5GB.

**Recommendation**: Partition by `created_at` month when row count exceeds 5M. The cursor pagination query already filters on `occurred_at`, so partition pruning works naturally.

### GP-3. `audit_events` -- Same Pattern

**Math**: Similar to timeline but across all entities, not just work items. 10M+ rows within first year at scale.

**Recommendation**: Partition by `created_at` month. The immutability rules (no UPDATE, no DELETE) make this table a perfect partitioning candidate since old partitions are read-only.

### GP-4. `notifications` -- Read-Heavy, Write-Heavy

**Math**: 5 notifications/event x 100 events/item x 10K items = 5M notifications (MVP). Most are `read` state.

**Recommendation**: Add a retention job that hard-deletes notifications older than 90 days with state `read` or `actioned`. Keep `unread` indefinitely.

### GP-5. `snapshot_data` JSONB in `integration_exports`

Each snapshot is ~20KB. At 10K exports: 200MB. Not a concern. But the `no_update_integration_exports_snapshot` RULE means old snapshots stay forever.

**Recommendation**: Add a `snapshot_archived_at` column. After 90 days, replace `snapshot_data` with `NULL` and store a reference to cold storage (S3). Or accept the storage cost at MVP.

---

## Connection Pool Sizing

### CP-1. Pool Configuration Not Specified in Schema Designs

EP-09 mentions "PostgreSQL connection pool: min 5, max 20. Redis connection pool: min 2, max 10." This is the only mention.

**Sizing analysis for async SQLAlchemy**:
- FastAPI with uvicorn (4 workers): each worker needs its own pool
- 4 workers x max 20 connections = 80 max connections
- PostgreSQL default `max_connections = 100`
- Add Celery workers (5 queues, ~11 workers total): each worker needs ~2 connections = 22 connections
- Total: 80 + 22 = 102 connections > 100 default

**Fix**: Either:
- **Option A**: Use PgBouncer in transaction mode. Set PG `max_connections = 200`, PgBouncer pool = 50. All application connections go through PgBouncer.
- **Option B** (simpler for MVP): Set PG `max_connections = 200`. Reduce per-worker pool to `max = 10` (4 workers x 10 = 40). Celery workers use `pool_size = 2`. Total: 40 + 22 = 62. Headroom for admin connections.

**Recommendation**: Option B for MVP. Add PgBouncer when connection count exceeds 100 concurrent.

---

## JSONB Usage Audit

| Table | Column | Queried? | Index Needed? | Should Be Columns? |
|-------|--------|----------|---------------|---------------------|
| `work_item_versions.snapshot` | No (read by PK) | No | No -- it's a blob |
| `timeline_events.payload` | No (returned as-is) | No | Correct as JSONB |
| `notifications.quick_action` | Read at action time | No | See security HIGH-6 -- should be an enum, not arbitrary JSONB |
| `notifications.extra` | No (returned as-is) | No | Acceptable |
| `audit_events.before_value` / `after_value` | No (audit read) | No | Correct |
| `audit_events.context` | No | No | Correct |
| `integration_exports.snapshot_data` | No (immutable blob) | No | Correct |
| `jira_project_mappings.work_item_type_mappings` | Read at export time | No | Acceptable for small config |
| `comments.anchor_*` | Queried by section_id | Already indexed via `anchor_section_id` | Correct |
| `work_items.draft_data` | Listed in tech_info.md, not in EP-01 DDL | N/A | **Missing from DDL** |

**Finding**: No JSONB column needs a GIN index. All JSONB is used as opaque blobs or small config read by PK. Correct usage.

**Missing**: `work_items.draft_data` is in `tech_info.md` schema but not in EP-01's CREATE TABLE. If auto-save draft stores partial form state in JSONB, define it.

---

## Strengths (good design choices)

1. **Cursor pagination everywhere** (EP-09). Correct. `(sort_value, id)` tiebreaker handles timestamp ties. No offset pagination anywhere.

2. **Full snapshot versioning** (EP-04/EP-07). O(1) read, O(1) diff. TOAST compression handles the bulk. The `archived` flag for lifecycle management is forward-thinking.

3. **Partial indexes on soft-delete** (EP-01). `WHERE deleted_at IS NULL` on most work_items indexes keeps the index small and relevant. Well done.

4. **Immutability enforcement on audit tables** (EP-10). PostgreSQL RULEs preventing UPDATE/DELETE on `audit_events` and `integration_exports.snapshot_data`. Simple, effective, DB-level guarantee.

5. **Capability array over RBAC tables** (EP-10). GIN index on `text[]` is the right call for 10 static capabilities. Avoids the role-permission join table complexity that plagues every RBAC implementation.

6. **Adjacency list + materialized path** (EP-05). Correct tree strategy for concurrent edits. Nested sets would be a disaster here.

7. **Separate `timeline_events` table** (EP-07). Fan-in on write beats UNION ALL on read. Append-only, indexed, trivial pagination.

8. **Idempotency keys on notifications** (EP-08). `SHA256(recipient_id + domain_event_id)` UNIQUE constraint prevents duplicate notifications on Celery retry. Correct pattern.

9. **Version-pinned reviews** (EP-06). `review_requests.version_id` is a snapshot FK, never mutated. Clean temporal reference.

10. **CHECK constraints on domain values** (EP-01, EP-06). `work_items_state_valid`, `work_items_type_valid`, `chk_reviewer_target` -- domain invariants enforced at DB level as a backstop to application-layer validation.

---

## Summary

| Category | Count | Severity |
|----------|-------|----------|
| Schema Design Issues | 10 | 3 critical (SD-1, SD-2, SD-5), 7 should-fix |
| Missing Indexes | 10 | 2 will cause slow queries (IDX-1, IDX-2), 8 preventive |
| Query Performance Risks | 10 | 2 broken (Q1 inbox), 1 will degrade at 10x (Q3 pipeline) |
| Data Integrity Gaps | 7 | 1 will crash (DI-3 subquery CHECK), 6 should-fix |
| Migration Safety | 5 | 1 will lock (MS-2), 1 will fail (MS-4) |
| Growth/Partitioning | 5 | Address before 10x scale |
| Connection Pool | 1 | Will exceed PG default at 4+ workers |
| JSONB Audit | Clean | No issues |
| Strengths | 10 | Preserve |

**Priority order for fixes**:
1. DI-3 -- subquery in CHECK constraint will crash table creation
2. SD-1 -- missing `state` column blocks all middleware
3. SD-2 -- missing `projects` table blocks EP-01 migration
4. SD-4 -- duplicate ALTER will fail EP-06 migration
5. MS-4 -- missing `pg_trgm` extension will fail EP-05 index
6. SD-5 -- add `workspace_id` to `work_items` for workspace scoping
7. MS-2 -- use CONCURRENTLY for GIN index creation
8. IDX-1, IDX-2 -- critical query performance
9. Everything else in order
