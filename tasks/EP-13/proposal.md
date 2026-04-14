# EP-13 — Puppet Integration (Search + Sync Pipeline)

> **Resolved 2026-04-14 (decisions_pending.md #4, #9, #24, #28)**: EP-13 reshaped. **Puppet is the sole search backend** — no PG FTS, no `tsvector`, no hybrid RRF, no keyword+semantic fusion, no learned re-ranker, no per-workspace embedding config, no multi-language pipeline. Our backend calls Puppet directly; Dundun is **not** in the search path.

## Business Need

Users need to find work items and related content by meaning, not just keyword, across their workspace and across external Tuio documentation (READMEs, project docs, ADRs). Today that context is fragmented.

The platform delegates the entire search responsibility to **Puppet** (Tuio's internal RAG/search platform), which is already the source of truth for Tuio documentation and already does the embedding/re-ranking/indexing work. Our job is (a) ship every writable domain entity into Puppet as it changes, and (b) expose a thin search API to the frontend that calls Puppet with the correct workspace tag.

## Objectives

- **PuppetClient** (HTTP wrapper) used by every BE call path to Puppet — no direct SDK in domain or presentation layers
- **Push pipeline**: on every create/update/delete of `work_items`, `sections`, `tasks`, `comments`, enqueue a Celery job that POSTs to Puppet with tag `wm_<workspace_id>`
- **Search API**: thin SearchService that calls `PuppetClient.search(...)` with the caller's `workspace_id` as the mandatory tag filter
- **Prefix / type-ahead**: dedicated `PuppetClient.prefix(...)` endpoint for the search bar
- **Saved searches**: local CRUD table (`saved_searches`) storing `(query, filters)` tuples per user
- **Faceted filters**: state/type/team/owner/archived filters forwarded as Puppet tags
- **External docs**: a user searching from inside the app can discover external Tuio docs (Puppet already indexes them under their own tags); our API forwards the query untouched and trusts Puppet's tag-based scoping
- **Admin**: Puppet API endpoint + credentials managed through the EP-10 admin UI

Not goals (decision #28):
- Hybrid RRF fusion with a local FTS engine — there is no local FTS
- Per-workspace embedding model configuration — Puppet decides
- Learned re-ranker with training loop
- Real-time multi-language pipelines

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-130 | Search over work items and comments via Puppet | Must |
| US-131 | Search Tuio external documentation from within the app | Must |
| US-132 | Push work item / section / comment / task changes to Puppet asynchronously | Must |
| US-133 | Prefix / type-ahead in the search bar | Must |
| US-134 | Saved searches per user | Must |
| US-135 | Admin: configure Puppet endpoint, credentials, health check | Must |
| US-136 | Admin: view Puppet indexing health / lag | Should |

## Acceptance Criteria

- WHEN a user searches THEN `SearchService` calls `PuppetClient.search(q, tag=wm_<workspace_id>, facets, cursor, limit)` and returns Puppet's ranked results verbatim, including snippets
- WHEN a user types ≥2 chars THEN `PuppetClient.prefix(q, tag=wm_<workspace_id>)` is used for type-ahead
- WHEN a work item is created/updated/deleted THEN a Celery job enqueues `PuppetClient.index(...)` / `.delete(...)` after commit; indexed within 3s (eventual consistency accepted per decision #4)
- WHEN Puppet is unreachable THEN the search API returns HTTP 503 `SEARCH_UNAVAILABLE`; there is no local-FTS fallback (none exists)
- WHEN a saved search is used THEN its `(query, filters)` is replayed as a single Puppet call
- WHEN filters (state/type/team/owner/archived) are applied THEN they are forwarded as Puppet tag filters server-side
- AND workspace isolation is enforced — `wm_<workspace_id>` tag is **always** injected server-side (never client-supplied)
- AND admin can configure Puppet endpoint, credentials, and view indexing health

## Technical Notes

- `PuppetClient` is an HTTP wrapper (httpx async); methods: `search`, `prefix`, `index`, `delete`, `health`
- Credentials stored Fernet-encrypted (same pattern as Jira in EP-10)
- Push-on-write uses the SQLAlchemy `after_commit` hook (owned by EP-09) that enqueues a Celery task on queue `puppet`
- Reconcile/backfill task: a daily Celery Beat job compares `work_items.updated_at` vs a `puppet_index_state` watermark and replays missing pushes
- Tag convention: `wm_<workspace_id>`, plus `type:<work_item_type>`, `state:<state>`, `archived:<bool>` — all injected server-side
- No hybrid ranking logic in our code — Puppet ranks, we return

## Dependencies

- EP-09 (listings/search FE surface; push hook lives in EP-09)
- EP-10 (integration configuration pattern, Fernet credentials store)

## Complexity Assessment

**Medium** — No ranking algorithm in-house. Complexity is in the sync pipeline (after-commit hook, idempotent tasks, reconcile job) and the permission-scoping invariant (wm tag always server-enforced).

## Risks

- Puppet index drift if sync fails silently (mitigated by reconcile job + health endpoint)
- Puppet outage → search unusable (503 response; deliberate — no local fallback by decision #4)
- Permission leaks if `wm_<workspace_id>` is ever client-supplied (must enforce server-side only)
- Puppet latency spikes → search P95 budget owned by Puppet; our wrapper must add <50ms overhead
