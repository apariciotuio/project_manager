# Spec: Search and Context Recovery (via Puppet)

**Story**: US-094 (Search and recover context)
**Epic**: EP-09
**Dependencies**: EP-01 (work_items), EP-07 (comments + timeline events), EP-13 (Puppet integration + push-on-write sync pipeline)

> **Resolved 2026-04-14 (decisions_pending.md #4, #9, #24, #28)**: Search is fully delegated to Puppet RAG. PostgreSQL FTS, `tsvector` columns, `aggregated_*_text` denormalized columns, GIN search indexes, `phraseto_tsquery`/`plainto_tsquery` query routing, and Elasticsearch hybrid fusion are all out of scope. The backend calls `PuppetClient` (EP-13) with workspace scoping on every query.

> **⚠️ SUPERSEDES (post-EP-18)**: workspace scoping uses **Puppet `category`** (`tuio-wmp:ws:<workspace_id>:workitem|section|comment`), not the `wm_<workspace_id>` tag pattern previously described. Facet filters (state, type, owner, team, archived, user tag slugs) remain on `tags`. Authoritative: `tasks/EP-18/specs/read-tools-assistant-search-extras/spec.md#semantic-search`.

---

## US-094 — Search via Puppet

### Core Search

WHEN a user submits a search query
THEN the backend calls `PuppetClient.search(query, tags=["wm_<workspace_id>", ...facet_tags], limit, cursor)`
AND Puppet returns ranked document IDs covering work items, comments, and timeline entries (all indexed via the EP-13 push pipeline).
AND the backend hydrates full rows by ID for rendering.
AND the response is returned in under 300 ms P95 (SLA targeted by Puppet at current scale).

WHEN the search query is empty or whitespace-only
THEN the API returns HTTP 422 with message "Query must not be empty".

WHEN the search query has fewer than 2 characters
THEN the API returns HTTP 422 with message "Query must be at least 2 characters".

### Search Scope

WHEN a search is performed
THEN results are scoped to the caller's active workspace via the mandatory `wm_<workspace_id>` tag filter.
AND soft-deleted items (`deleted_at IS NOT NULL`) are excluded by the indexer (they are removed from Puppet by the EP-13 delete handler).

### Result Structure

WHEN Puppet returns results
THEN each hit includes: `document_id`, `document_type` (`work_item`|`comment`|`timeline_event`), relevance score, and highlight snippet supplied by Puppet.
AND the backend attaches: work item title, type, state, owner display name, team name (looked up in Postgres).
AND highlight snippets preserve `<mark>` tags from Puppet.

### Facets / Filters

WHEN a user applies `state`, `type`, `team_id`, `owner_id`, `project_id`, or `tag_id` facets alongside a search query
THEN the backend translates each filter to a Puppet tag (`wm_state_<state>`, `wm_type_<type>`, `wm_team_<id>`, `wm_owner_<id>`, `wm_project_<id>`, `wm_tag_<slug>`) and passes them in the `tags` array.
AND Puppet applies the filter server-side; no local SQL filtering of search hits.

WHEN `owner_id=me`
THEN the backend resolves `me` to the authenticated user's ID before building the tag.

### Prefix / Type-ahead

WHEN a user types in the searchbar (per-keystroke, debounced 150 ms)
THEN the backend calls `PuppetClient.search_prefix(prefix, tags=[wm_<workspace_id>])`.
AND results (title-only matches, capped at 8) populate the autocomplete dropdown.

### Saved Searches

WHEN a user saves the current search parameters
THEN the backend inserts into `saved_searches(id, user_id, workspace_id, name, query_params JSONB, created_at)`.
AND `query_params` stores the raw query + facet IDs, not the translated Puppet tags.
AND replaying a saved search re-translates facets into tags at the time of execution (so that tag renames/moves reflect current state).

### Pagination

WHEN Puppet returns more results than the page size (default 20, max 50)
THEN Puppet returns a `cursor`; the backend forwards it in `{ data, cursor, has_next }`.
AND `has_next=true` iff Puppet indicates more results exist; no global `total_count` is computed (Puppet does not commit to one).

### Context Recovery

WHEN a user selects a result and later returns
THEN the original query + facets are preserved in the URL (`?q=...&facets=...`) for browser back navigation.

### Degraded Search

WHEN Puppet is unreachable (health check failing)
THEN the searchbar UI displays "search unavailable".
AND CRUD, filter-based listings, and dashboards continue to operate against PostgreSQL.
AND errors are logged with the correlation ID; no automatic fallback to SQL LIKE.

### Freshness

WHEN a work item, comment, or timeline entry is written
THEN the EP-13 push pipeline indexes (or deletes) it in Puppet within 3 s (eventual-consistency target).
AND a health probe monitors lag; breaching the target raises an alert visible to Workspace Admins.

### Search API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/search?q=&cursor=&limit=&<facet filters>` | Rate-limited to 30 requests/minute/user. |
| GET | `/api/v1/search/suggest?prefix=` | Type-ahead (Puppet prefix). |
| GET | `/api/v1/saved-searches` | List current user's saved searches. |
| POST | `/api/v1/saved-searches` | Save a search. |
| DELETE | `/api/v1/saved-searches/:id` | Remove a saved search. |
