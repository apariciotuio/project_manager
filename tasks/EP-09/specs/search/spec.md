# Spec: Search and Context Recovery

**Story**: US-094 (Search and recover context)
**Epic**: EP-09
**Dependencies**: EP-01 (work_items, history), EP-02 (captures/drafts with free text), EP-06 (review_responses with text content)

---

## US-094 — Search and Context Recovery

### Core Full-Text Search

WHEN a user submits a search query
THEN the system searches across: item titles, item descriptions, spec content, task descriptions, comment bodies, and review response text
AND the search uses PostgreSQL `tsvector`/`tsquery` with `english` text search configuration
AND results are ranked by `ts_rank_cd` (cover density) descending
AND the response is returned in under 300ms for datasets up to 50k indexed documents

WHEN the search query is empty or whitespace-only
THEN the API returns HTTP 422 with message "Query must not be empty"
AND no results are returned

WHEN the search query has fewer than 2 characters
THEN the API returns HTTP 422 with message "Query must be at least 2 characters"

### Search Scope

WHEN a search is performed
THEN results are scoped to items the authenticated user has read access to
AND items in `ARCHIVED` state are excluded from search results by default
AND a `include_archived=true` parameter re-includes archived items in results

WHEN a search indexes a work item
THEN the `tsvector` document weights are: title (weight A), description + spec (weight B), task descriptions (weight C), comments + review responses (weight D)
AND weight A results surface above weight B/C/D results in ranking

### Search Result Structure

WHEN search returns results
THEN each result includes: item id, title, type, state, owner display name, team name, relevance score, and a highlight snippet
AND the highlight snippet shows the matched text fragment with match terms wrapped in `<mark>` tags
AND the snippet is maximum 200 characters per matched field
AND if multiple fields match, snippets from the highest-weight field are shown first

WHEN a search term matches inside a comment or review response
THEN the snippet shows the comment/review text fragment
AND the result is attributed to the parent work item (not the comment itself)

### Filters Within Search

WHEN a user applies a `state` filter alongside a search query
THEN results are restricted to items in the specified state(s)
AND state filter uses the same multi-value OR logic as the list view

WHEN a user applies a `type` filter alongside a search query
THEN results are restricted to items of the specified type(s)

WHEN a user applies a `team_id` filter alongside a search query
THEN results are restricted to items assigned to the specified team

WHEN a user applies a `owner_id` filter alongside a search query
THEN results are restricted to items owned by the specified user
AND `owner_id=me` resolves to the authenticated user

WHEN multiple filters are applied alongside a search query
THEN all filters are AND-combined with the full-text match condition

### Pagination of Search Results

WHEN search returns more results than the page size (default 20, max 50)
THEN a `next_cursor` is returned for fetching the next page
AND `total_count` reflects the total number of matching results
AND cursor-based pagination is used (consistent with list view)

### Result Ranking

WHEN ranking search results
THEN the primary sort is `ts_rank_cd` descending (relevance)
AND the secondary sort is `updated_at` descending (recency as tiebreaker)
AND items in `READY` state receive no ranking boost (relevance is content-based only)

WHEN a phrase query is submitted (terms in double quotes, e.g., `"payment flow"`)
THEN the system performs phrase matching using `phraseto_tsquery`
AND only items containing the exact phrase are returned

WHEN a query contains multiple space-separated terms without quotes
THEN the system uses `plainto_tsquery` (AND logic — all terms must appear)
AND partial word matches are not supported (no prefix matching in MVP)

### tsvector Maintenance

WHEN a work item is created or updated (title, description, spec)
THEN the `search_vector` tsvector column on `work_items` is updated synchronously (via PostgreSQL trigger or SQLAlchemy event)
AND the update completes within the same transaction as the item change

WHEN a comment or review response is created
THEN the parent item's `search_vector` is updated asynchronously via a Celery task
AND the Celery task enqueues within 1 second of the comment/review event
AND the delay between comment creation and search indexing is acceptable for MVP (eventual consistency, not real-time)

WHEN a comment or review response is deleted
THEN the parent item's `search_vector` is re-computed from remaining content
AND the re-computation is handled by the same async Celery task

### Context Recovery

WHEN a user searches and selects a result
THEN navigating to the item opens the unified detail view (US-095)
AND the original search query is preserved in the URL (`?q=...`) for browser back navigation
AND the search results page is restored on back navigation (no re-fetch required — use browser history state)

WHEN a user returns to the search page after viewing a result
THEN the search query is still populated in the search input
AND the results list is at the same scroll position

### Search API

WHEN the search endpoint is called
THEN it is `GET /api/v1/search?q={query}&state=...&type=...&team_id=...&owner_id=...&cursor=...&limit=...`
AND the endpoint is read-only (HTTP GET, no side effects)
AND the endpoint is rate-limited to 30 requests per minute per authenticated user

### No Jira Dependency

WHEN the system has no Jira configured
THEN search functions identically
AND Jira issue keys found in item descriptions are searchable as plain text
AND no Jira-specific fields are required for indexing
