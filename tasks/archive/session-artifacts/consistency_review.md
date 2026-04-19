# Cross-Epic Consistency Review

## MUST FIX (7 issues — migration failures or runtime errors)

| # | Epics | Issue | Resolution |
|---|-------|-------|------------|
| 1 | EP-01, EP-09 | `state_entered_at` column missing from `work_items` | Add to EP-01's schema. Update on every state transition in FSM service |
| 2 | EP-01, EP-06 | `has_override` defined twice, incompatibly. EP-06 adds columns EP-01 already has | EP-01 owns `has_override` + `override_justification`. EP-06 adds only `override_by` + `override_at` |
| 3 | EP-03, EP-07 | `version_number` + `current_version_id` missing from `work_items` but referenced by EP-03, EP-06, EP-11 | Add both to EP-01's `work_items` schema |
| 4 | EP-06, EP-07 | `work_item_versions` table referenced by EP-06 FK before EP-07 creates it | Move `work_item_versions` to EP-04 (it creates sections, needs versioning). Or enforce migration order: EP-07 before EP-06 |
| 5 | EP-08, EP-09 | Phantom tables in inbox query: `reviews` (should be `review_requests`), `review_resolutions`, `blocks`. States `returned`/`awaiting_decision` don't exist | Rewrite inbox queries using actual tables. Map to existing states |
| 6 | EP-00, EP-10 | Table name: `workspace_memberships` (EP-00) vs `workspace_members` (EP-10) | Standardize on `workspace_memberships`. Update EP-10 |
| 7 | EP-09 | `team_id` on `work_items` assumed but never defined | Add `team_id UUID REFERENCES teams(id)` to `work_items` or use join through assignments |

## SHOULD FIX (10 issues — inconsistencies that cause confusion)

| # | Epics | Issue | Resolution |
|---|-------|-------|------------|
| 8 | EP-01, EP-09 | State enum naming: snake_case vs UPPER_CASE. `ENRICHMENT`/`ARCHIVED` don't exist in EP-01 | Standardize on EP-01's lowercase. Remove phantom states |
| 9 | EP-01, EP-03, EP-10, EP-12 | "work_item" vs "element" vs "item" naming | Standardize on `work_item` everywhere |
| 10 | EP-04, EP-07 | Two versioning systems: section-level (EP-04) and full-snapshot (EP-07) | Document: section versions = internal audit. work_item_versions = canonical snapshots. Section save triggers both |
| 11 | EP-08, EP-06 | Inbox query uses wrong review table names | EP-08 must use EP-06's `review_requests` + `review_responses` |
| 12 | EP-09, EP-12 | Dashboard cache TTL mismatch (60s vs 120s) | EP-12 owns caching policy. EP-09 defers |
| 13 | EP-09, EP-12 | Pagination response shape divergence (`next_cursor` vs `cursor`) | Standardize on EP-12's shape: `cursor` + `has_next` |
| 14 | EP-00, EP-10 | `role` column vs `capabilities` array — relationship undefined | EP-10's capabilities supersede EP-00's role. Role becomes display label only |
| 15 | EP-03, EP-08 | Duplicate SSE infrastructure | Extract shared SSE layer (Redis pub/sub + handler) |
| 16 | EP-06, EP-01 | Ready transition endpoint duplication | EP-01's generic transition delegates to EP-06's ready gate when target=ready |
| 17 | EP-11, EP-00 | `exported_by` FK references `workspace_members(id)` instead of `users(id)` | Change to `users(id)` for consistency |

## NITPICK (3 issues)

| # | Epics | Issue | Resolution |
|---|-------|-------|------------|
| 18 | EP-03, EP-04 | Gap detection defined in both epics differently | EP-04's `/gaps` = completeness gaps. EP-03's = content quality gaps. Document distinction or merge |
| 19 | EP-00, EP-10 | `audit_logs` (EP-00) vs `audit_events` (EP-10) — two audit tables | `audit_logs` = auth events. `audit_events` = admin/domain actions. Explicit naming |
| 20 | EP-04, EP-03 | `/gaps` endpoint path collision | One epic owns. Other merges or uses different path |

## Consolidated Schema Fixes for EP-01

These columns must be added to EP-01's `work_items` CREATE TABLE:

```sql
-- Missing from initial schema, required by downstream epics
state_entered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- EP-09 dashboards
version_number      INTEGER NOT NULL DEFAULT 0,          -- EP-03 optimistic lock
current_version_id  UUID,                                -- EP-06 review pinning, EP-11 divergence
override_by         UUID REFERENCES users(id),           -- EP-06 override audit
override_at         TIMESTAMPTZ,                         -- EP-06 override audit
team_id             UUID REFERENCES teams(id),           -- EP-09 team filtering
```

## Table Name Standardization

| Canonical Name | Used In | Incorrect References |
|---------------|---------|---------------------|
| `workspace_memberships` | EP-00 | EP-10 uses `workspace_members` |
| `review_requests` | EP-06 | EP-08 uses `reviews` |
| `review_responses` | EP-06 | EP-08 uses `review_resolutions` |
| `work_items` | EP-01 | EP-10/EP-12 use `elements`, EP-08 uses `items` |

## Migration Order (Revised)

```
1. EP-00: users, refresh_tokens, workspaces, workspace_memberships
2. EP-01: work_items (with ALL columns including state_entered_at, version_number, current_version_id, team_id, override_by, override_at)
3. EP-08: teams, team_members, notifications
4. EP-02: work_item_drafts, templates (+ draft_data on work_items)
5. EP-04: work_item_sections, work_item_versions (moved from EP-07)
6. EP-03: conversation_threads, conversation_messages, assistant_suggestions
7. EP-05: task_nodes, task_node_section_links, task_dependencies
8. EP-06: review_requests, review_responses, validation_requirements (FK to work_item_versions now exists)
9. EP-07: comments, timeline_events (work_item_versions already created by EP-04)
10. EP-10: projects, validation_rules, routing_rules, context_sources, context_presets, integration_configs, audit_events
11. EP-11: integration_exports, sync_logs
12. EP-09: search indexes, denormalized columns
13. EP-12: no new tables (middleware + observability)
```
