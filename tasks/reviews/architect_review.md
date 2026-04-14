# Architect Review

**Date**: 2026-04-13
**Scope**: 13 epics (EP-00 through EP-12), full architecture review
**Reviewer**: sw-architect agent

---

## Critical Findings (must address before implementation)

### C1. EP-08 Inbox Query References Non-Existent Tables, Columns, and States

**Files**: `tasks/EP-08/design.md`, lines 178-226

The inbox UNION query is broken in 4 out of 4 sub-queries:

| Sub-query | Problem |
|-----------|---------|
| Tier 1 (direct reviews) | Uses `rr.assignee_user_id` -- column does not exist on `review_requests` (EP-06 defines `reviewer_id`) |
| Tier 1 (direct reviews) | Uses `rr.state` -- column is named `status` in EP-06's schema |
| Tier 2 (returned items) | Filters `state = 'returned'` -- not a valid `WorkItemState` in EP-01. Closest is `changes_requested` |
| Tier 3 (blocking items) | References `blocks` table -- does not exist in any epic's schema |
| Tier 4 (decisions) | References `decision_owner_id` column and `awaiting_decision` state -- neither exists |
| Index list | References `assignee_user_id`, `decision_owner_id`, `caused_by_user_id` -- all phantom columns |

The consistency_review (issue #5) flagged this, but the inbox query in EP-08 design.md is unchanged. This will produce a 100% broken inbox feature.

**Fix**: Rewrite the inbox query against EP-06's actual `review_requests` schema. Map the tiers to real states:
- Tier 1: `review_requests WHERE reviewer_id = :user_id AND status = 'pending'` (direct) + team fan-out via `team_memberships`
- Tier 2: `work_items WHERE owner_id = :user_id AND state = 'changes_requested'`
- Tier 3: Remove entirely (no `blocks` table exists) or defer
- Tier 4: Remove entirely (no `decision_owner_id` concept exists) or model it explicitly

### C2. EP-06 Override Migration Conflicts with EP-01 Column Definitions

**Files**: `tasks/EP-06/design.md` lines 143-148, `tasks/EP-01/design.md` lines 168-206

EP-06 design still contains an `ALTER TABLE work_items` that adds `has_override`, `override_justification`, `override_by`, and `override_at`. But EP-01's CREATE TABLE already defines all four columns. Running EP-06's migration will fail with `column already exists`.

The consistency_review (issue #2) noted this, and EP-01 was updated, but EP-06's design.md still carries the duplicate ALTER. 

**Fix**: Remove the ALTER TABLE block from EP-06's design. Add a comment: "Override columns owned by EP-01. EP-06 reads and writes them via WorkItemService."

### C3. EP-04 work_item_versions Ownership vs EP-07 Additive Migration -- Ambiguous Table Lifecycle

**Files**: `tasks/EP-04/design.md` lines 41-52, `tasks/EP-07/design.md` lines 17-27

EP-04 creates `work_item_versions` (base table). EP-07 extends it with an ALTER adding 5 columns. But EP-04's `SectionService.save()` is documented as writing version rows. EP-07's versioning service also writes version rows. Two services writing to the same table with different column awareness:

- EP-04 writes `(id, work_item_id, version_number, snapshot, created_by, created_at)` -- the base columns
- EP-07's ALTER adds `trigger`, `actor_type`, `actor_id`, `commit_message`, `archived` with NOT NULL defaults

This means EP-04's inserts will work (defaults fill the EP-07 columns), but the data will be wrong -- every EP-04-initiated version will have `trigger = 'content_edit'` and `actor_type = 'human'` regardless of actual trigger.

**Fix**: Single versioning service. EP-04 should not write `work_item_versions` directly. Extract a `VersioningService` (EP-07 domain) that accepts a `VersionTrigger` enum and `actor_type`. EP-04's `SectionService.save()` calls `VersioningService.create_version(work_item_id, trigger=CONTENT_EDIT, actor=...)`. EP-01's `transition_state()` calls it with `trigger=STATE_TRANSITION`. This eliminates dual ownership.

### C4. EP-03 Suggestion Model Diverges from tech_info.md Schema

**Files**: `tasks/EP-03/design.md` lines 140-164, `tech_info.md` lines 83-84

EP-03 design defines `SuggestionSet` + `SuggestionItem` (two tables, set/item pattern). But `tech_info.md` line 84 documents a flat `assistant_suggestions` table with columns `(id, work_item_id, thread_id, section_id, proposed_content, status, version_number_target, created_by)`.

These are two incompatible designs for the same concept. EP-04 line 353 references "suggestions table" with a `section_id` FK. Which schema is canonical?

**Fix**: EP-03's `SuggestionSet + SuggestionItem` design is richer and supports partial application. Adopt it. Update `tech_info.md` to match. Remove `assistant_suggestions` reference. Update EP-04's integration section to reference `suggestion_items.section_id`.

### C5. EP-10 Introduces Duplicate Table Names for Jira Config

**Files**: `tasks/EP-10/design.md` lines 126-148, `tech_info.md` lines 104-105

EP-10 design uses `jira_configs` and `jira_project_mappings` and `jira_sync_logs`. But `tech_info.md` uses `integration_configs` and `integration_project_mappings`. EP-11 references `jira_configs` (matching EP-10). 

**Fix**: Pick one naming convention. Since EP-11 also uses `jira_configs`, standardize on EP-10's names (`jira_configs`, `jira_project_mappings`, `jira_sync_logs`). Update `tech_info.md`. The `integration_*` naming anticipates multi-provider, which is out of scope and violates YAGNI. ⚠️ originally MVP-scoped — see decisions_pending.md

### C6. workspace_memberships Missing State and Capabilities Columns in EP-00

**Files**: `tasks/EP-00/design.md` lines 104-121, `tasks/EP-10/design.md` line 21

EP-00's `workspace_memberships` CREATE TABLE has no `state` column and no `capabilities` column. EP-10 adds `capabilities` via ALTER. But every middleware from EP-10 and EP-12 checks `member.state == 'active'` -- there is no `state` column defined anywhere.

The `WorkspaceMemberMiddleware` (EP-10 line 47, EP-12 line 72) will fail because there is no `state` column on `workspace_memberships`.

**Fix**: Add to EP-00's CREATE TABLE:
```sql
state VARCHAR(50) NOT NULL DEFAULT 'active', -- active | suspended | deactivated
capabilities TEXT[] NOT NULL DEFAULT '{}'
```
Remove EP-10's ALTER. Bootstrap the first member with all capabilities in EP-00's workspace creation transaction.

---

## Structural Recommendations (should address)

### S1. Dual Completeness Score -- EP-01 Domain Method vs EP-04 Engine

EP-01's `WorkItem` entity has a `compute_completeness()` method (line 67) and a `completeness_score` column. EP-04 builds an entire `CompletenessService` with `DimensionChecker`, `ScoreCalculator`, weighted dimensions, and Redis caching.

These are two implementations of the same concept. EP-01's domain-level computation cannot access sections, validators, or task nodes -- it only has entity fields. EP-04's computation does the real work.

**Fix**: Remove `compute_completeness()` from EP-01's WorkItem entity. The `completeness_score` column on `work_items` should be treated as a denormalized cache updated by EP-04's `CompletenessService` after each recomputation. EP-01 only stores it; EP-04 owns the algorithm.

### S2. EP-08 Assignment Endpoints Use Wrong URL Prefix

**Files**: `tasks/EP-08/design.md` lines 275-279

Assignment endpoints use `/api/v1/items/{item_id}/...` instead of `/api/v1/work-items/{item_id}/...`. This breaks the URL convention established by EP-01 and used by every other epic.

**Fix**: Replace `/items/` with `/work-items/` in EP-08's assignment endpoints. Also, `POST /api/v1/items/{item_id}/reviews` collides with EP-06's `POST /api/v1/work-items/{id}/review-requests` -- same action, two endpoints. Remove EP-08's version; EP-06 owns review creation.

### S3. Two Audit Tables Without Clear Boundary

**Files**: `tasks/EP-00/design.md` lines 126-141 (`audit_logs`), `tasks/EP-10/design.md` lines 214-238 (`audit_events`)

EP-00 defines `audit_logs` for auth events. EP-10 defines `audit_events` for admin/domain actions. Two append-only audit tables with overlapping schema and no shared interface.

**Fix**: Merge into one `audit_events` table with a `category` column (`auth | admin | domain`). Single `AuditService` with one write path. Auth events include IP/user_agent in the `context` JSONB. This prevents "which audit table do I query?" confusion and simplifies compliance queries.

### S4. EP-03 Gap Detection vs EP-04 Gap Detection -- Boundary Unclear

EP-03 defines a `gap_detection/` domain module with rule-based + LLM-enhanced gap detection. EP-04 defines gap detection as "a filter over dimension results where `filled == False`". EP-03 line 254 clarifies ownership but the code structure is confusing.

Both epics have domain code for "what's missing in this work item." Two codepaths, two mental models.

**Fix**: EP-04 owns structural completeness gaps (missing sections, empty required fields). EP-03 owns content quality gaps (vague language, insufficient detail). Document this split in `tech_info.md`. EP-03's `gap_detector.py` module should be renamed to `content_quality_analyzer.py` to avoid name collision.

### S5. Event Bus Implementation Undefined

Every epic references "in-process event bus" for domain events. 17 event types are cataloged in `tech_info.md`. But no epic defines the event bus implementation.

**Fix**: EP-12 should own the event bus definition. A simple synchronous dispatcher (list of handler callables, keyed by event type) with a `publish(event)` method. Define in `infrastructure/events/event_bus.py`. Include in EP-12's design as a cross-cutting concern, same as middleware.

### S6. EP-08 WebSocket Endpoint Contradicts SSE Decision

**Files**: `tasks/EP-08/design.md` line 287

EP-08 lists both SSE and WebSocket endpoints for notifications:
```
GET  /api/v1/notifications/stream  # SSE
WS   /ws/notifications             # WebSocket alternative
```

The design explicitly chooses SSE over WebSocket (lines 292-298). The WebSocket endpoint should not exist -- it creates implementation ambiguity and doubles the real-time infrastructure.

**Fix**: Remove the WebSocket endpoint from EP-08's API table. SSE only, as decided.

### S7. EP-01 work_items References projects(id) but projects Table is Created in EP-10

**Files**: `tasks/EP-01/design.md` line 175, consistency_review migration order

EP-01's `work_items` has `project_id UUID NOT NULL REFERENCES projects(id)`. But the `projects` table is defined in EP-10 (line 98 of tech_info.md, EP-10 design section 2). The migration order puts EP-01 at position 2 and EP-10 at position 10.

This FK will fail at migration time. The consistency_review migration order does not address this.

**Fix**: Move the `projects` table creation to EP-01 (minimal: `id`, `workspace_id`, `name`, `status`, `created_at`). EP-10 adds columns via ALTER for its configuration features. Or, create `projects` in a shared EP-00.5 migration between EP-00 and EP-01.

### S8. EP-00 session table named `sessions` but tech_info.md says `refresh_tokens`

**Files**: `tasks/EP-00/design.md` line 69 (`sessions`), `tech_info.md` line 43 (`refresh_tokens`)

**Fix**: Standardize. EP-00's `sessions` is the source of truth (it stores more than just the token). Update `tech_info.md`.

---

## Scalability Concerns (address before 10x)

### SC1. Inbox UNION Query Will Degrade

The inbox (EP-08) runs 4+ sub-queries UNIONed with no result limit per tier. At 10x scale (10k work items, 5k reviews per workspace), this query will exceed the 300ms target.

**Mitigation**: Add `LIMIT 50` per sub-query in the UNION. Application layer already deduplicates. If p95 still exceeds target, materialize the inbox as an eventually-consistent table refreshed on domain events.

### SC2. Full-Snapshot Versioning Storage Growth

EP-07's math: 20KB/snapshot x 100 versions x 10k items = 20GB at current target scale. At 10x (100k items), it is 200GB of JSONB in one table. TOAST compresses, but vacuum and index maintenance become painful.

**Mitigation**: Implement the `archived` column from EP-07's design. Background job archives versions older than 90 days (keeping latest 10). Archived versions moved to a `work_item_versions_archive` table or partitioned by date.

### SC3. SSE Connection Count

Each authenticated user holds one SSE connection. At 1k concurrent users, that is 1k long-lived HTTP connections. FastAPI on uvicorn handles this, but:
- Each SSE handler subscribes to a Redis pub/sub channel
- Redis pub/sub does not scale horizontally natively (no consumer groups)

**Mitigation**: At 10x, switch from Redis pub/sub to Redis Streams with consumer groups, or introduce a dedicated message broker (NATS, RabbitMQ). At current target scale, Redis pub/sub is fine. ⚠️ originally MVP-scoped — see decisions_pending.md

### SC4. Dashboard Cache Invalidation Is Too Broad

`tech_info.md` and EP-09: "Any work_item state change" invalidates the global dashboard cache. At 10x traffic, a high mutation rate means the cache is constantly cold, defeating its purpose.

**Mitigation**: Invalidate per-scope only (team/person dashboards on relevant mutations). For the global dashboard, accept a stale window (TTL-only, no event-driven invalidation). 120s staleness is acceptable for aggregate metrics.

### SC5. total_count on Every List Request

EP-09 runs `COUNT(*)` with the same WHERE clause on every paginated list request. At 10x, this is an extra sequential scan per request.

**Mitigation**: Make `total_count` optional (`?include_count=true`). Default to omitting it. Frontend shows "Load more" instead of "Page X of Y". If needed, use `pg_stat_user_tables.n_live_tup` for an approximate count.

### SC6. Completeness Score Computed Synchronously on GET

EP-04 computes completeness on every `GET /completeness` request (cache miss = sync DB query + calculation). If cache TTL is 60s and the item is actively edited, every save invalidates the cache, and the next GET recomputes.

**Mitigation**: Compute asynchronously on write (Celery task on section save). Store result in `work_items.completeness_score`. GET reads the column directly -- no cache needed. Latency: near-zero for reads; writes accept eventual consistency (score updates within seconds).

---

## Architecture Strengths (validated decisions)

### V1. Custom FSM Over Library (EP-01)
14 edges in a frozenset. Zero dependencies. Trivially testable. Business rules stay in the service layer, not in framework callbacks. Correct decision.

### V2. Capability Array Over RBAC (EP-10)
With ~10 capabilities and no role inheritance, a `text[]` column is the right call. Avoids the role-permission join table circus. GIN index makes capability checks fast. Capability granting constraint ("can only grant what you hold") is elegant. ⚠️ originally MVP-scoped — see decisions_pending.md

### V3. Full Snapshot Versioning (EP-07)
O(1) read, O(1) diff. TOAST handles compression. The storage math works at current target scale. Delta encoding adds complexity for zero user-facing benefit. Good call. ⚠️ originally MVP-scoped — see decisions_pending.md

### V4. SSE Over WebSocket (EP-08, EP-12)
Unidirectional server push. No upgrade handshake. Auto-reconnect in browsers. Shared infrastructure across EP-03 and EP-08. The right primitive for the problem.

### V5. Adjacency List + Materialized Path (EP-05)
Nested sets would be a disaster for concurrent task editing. Adjacency list with materialized path gives O(1) breadcrumb lookups and clean recursive CTEs for tree reads. Depth cap of 10 levels is sensible.

### V6. Shared SSE Infrastructure (EP-12)
Extracting a common `infrastructure/sse/` module with Redis pub/sub, channel registry, and SSE handler prevents the duplicate infrastructure that EP-03 and EP-08 would otherwise build independently. Good cross-cutting ownership.

### V7. Deterministic Next-Step Recommender (EP-04)
Pure function, ordered rule list, first match wins. No LLM. Fast, cheap, testable, auditable. The LLM is reserved for content generation where non-determinism is acceptable. Clean separation.

### V8. DDD Layer Discipline
Across all 13 epics, the dependency direction is consistent: presentation -> application -> domain <- infrastructure. Domain models are pure dataclasses with no ORM decorators. Repository interfaces in domain, implementations in infrastructure. No epic violates this.

### V9. Cursor Pagination Everywhere (EP-09, EP-12)
Offset pagination degrades under concurrent writes. Cursor with `(sort_value, id)` tiebreaker is correct. Standardized response shape across all list endpoints.

### V10. Audit Immutability (EP-10)
PostgreSQL RULE to prevent UPDATE/DELETE on audit_events. Simple, effective. Combined with synchronous writes within the same transaction as the audited action, this guarantees consistency without eventual-consistency risks.

---

## Summary Table

| Category | Count | Severity |
|----------|-------|----------|
| Critical (blocks implementation) | 6 | Must fix |
| Structural (causes confusion/bugs) | 8 | Should fix |
| Scalability (breaks at 10x) | 6 | Pre-scale |
| Validated strengths | 10 | No action |

**Recommended implementation order for fixes**:
1. C6 (workspace_memberships state/capabilities) -- blocks all middleware
2. C7/S7 (projects table FK) -- blocks EP-01 migration
3. C1 (inbox query) -- blocks EP-08 inbox feature entirely
4. C3 (versioning service ownership) -- blocks EP-04 and EP-07 from parallel development
5. C2 (EP-06 duplicate ALTER) -- trivial, do immediately
6. C4 (suggestion schema) -- blocks EP-03/EP-04 integration
7. C5 (Jira table names) -- blocks EP-10/EP-11 integration
8. Everything else in priority order
