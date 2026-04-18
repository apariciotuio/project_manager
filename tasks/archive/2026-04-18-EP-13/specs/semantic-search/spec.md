# Spec: Semantic Search + Hybrid Search
## US-130 (Semantic Search over Work Items) + US-133 (Unified Hybrid Search Results)

**Epic**: EP-13
**Date**: 2026-04-13
**Status**: Draft

---

## Scope

Extends EP-09 search infrastructure. PG FTS remains the keyword engine. Puppet provides semantic similarity scores. Results are fused via Reciprocal Rank Fusion (RRF) and returned from a single POST /api/v1/search endpoint. Workspace isolation enforced server-side — Puppet queries are always filtered by `workspace_id`.

---

## US-130: Semantic Search over Work Items

### AC-130-1: Basic semantic query returns ranked results

WHEN a user sends `POST /api/v1/search` with `{ "q": "how we handle claim disputes", "mode": "semantic", "scope": "items" }`
THEN the response contains a list of work items ranked by Puppet similarity score
AND each result includes `{ "id", "title", "type", "state", "score", "provenance": "semantic", "snippet" }`
AND results are scoped to workspaces the user is a member of
AND archived items are excluded unless `include_archived: true` is explicitly set

### AC-130-2: Workspace isolation is enforced

WHEN a user sends a semantic search query
THEN the Puppet adapter adds `workspace_ids: [<user_accessible_workspace_ids>]` to every Puppet request
AND results from workspaces the user cannot access are never returned
AND if the user has no workspace memberships, the response is `{ "data": [], "meta": { "total": 0 } }`

### AC-130-3: Puppet unavailable — graceful degradation

WHEN Puppet API is unreachable (timeout > 2000ms or HTTP 5xx)
THEN the endpoint falls back to PG FTS keyword-only results
AND the response includes `"meta": { "search_mode_used": "keyword", "fallback_reason": "puppet_unavailable" }`
AND the HTTP status is still 200 (Puppet is additive, not required)
AND the fallback is logged at WARN level with `integration=puppet` and the error reason

### AC-130-4: Puppet timeout is enforced

WHEN a Puppet API call exceeds 2000ms
THEN the call is cancelled
AND the service falls back to keyword-only (same as AC-130-3)
AND the timeout duration is configurable via `PUPPET_TIMEOUT_MS` env var (default 2000)

### AC-130-5: Empty query is rejected

WHEN a user sends a search request with `q` as empty string or whitespace-only
THEN the response is `400 Bad Request`
AND the error body contains `{ "error": { "code": "INVALID_QUERY", "message": "Query must not be empty" } }`

---

## US-133: Unified Hybrid Search Results

### AC-133-1: Hybrid mode fuses keyword and semantic results

WHEN a user sends `POST /api/v1/search` with `{ "q": "...", "mode": "hybrid", "scope": "items" }`
THEN the service runs PG FTS and Puppet searches in parallel
AND results are merged using RRF: `score_rrf = 1/(k + rank_keyword) * w_keyword + 1/(k + rank_semantic) * w_semantic`
  where `k=60`, `w_keyword=0.40`, `w_semantic=0.60` (configurable via env vars `RRF_K`, `RRF_WEIGHT_KEYWORD`, `RRF_WEIGHT_SEMANTIC`)
AND the final list is sorted by descending RRF score
AND each result includes `"provenance"` showing which engines matched: `"keyword"`, `"semantic"`, or `"both"`

### AC-133-2: Items matched by both engines surface first

WHEN a work item scores in both PG FTS and Puppet results
THEN its RRF score reflects contributions from both engines
AND items matched by only one engine appear below items matched by both (given equal query relevance)

### AC-133-3: Provenance labels are present on every result

WHEN search results are returned in any mode
THEN each result item includes `"provenance": "keyword" | "semantic" | "both"`
AND results also include `"matched_by"` array listing `"keyword"` and/or `"semantic"` for UI badge rendering

### AC-133-4: Mode=keyword returns PG FTS only, no Puppet call

WHEN a user sends `POST /api/v1/search` with `"mode": "keyword"`
THEN no Puppet API call is made
AND results come from PG FTS only
AND `"meta": { "search_mode_used": "keyword" }` is included

### AC-133-5: Pagination is cursor-based and consistent across modes

WHEN a search result set exceeds `limit` (default 20, max 50)
THEN the response includes `"pagination": { "cursor": "<opaque>", "has_next": true }`
AND the cursor encodes `(rrf_score, id)` for hybrid mode, `(rank, id)` for keyword, `(similarity, id)` for semantic
AND subsequent requests with `cursor` return the next page without duplicates

### AC-133-6: Scope=all returns both work items and docs in a unified list

WHEN a user sends `POST /api/v1/search` with `"scope": "all"`
THEN work items and documentation results are returned in the same list
AND each result includes `"result_type": "work_item" | "doc"`
AND provenance labels apply to both types

### AC-133-7: Search request is validated

WHEN `mode` is not one of `hybrid | keyword | semantic`
THEN the response is `400 Bad Request` with `"code": "INVALID_MODE"`
WHEN `scope` is not one of `items | docs | all`
THEN the response is `400 Bad Request` with `"code": "INVALID_SCOPE"`

---

## API Contract

```
POST /api/v1/search
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "q": string,                          // required, min 1 char
  "mode": "hybrid" | "keyword" | "semantic",  // default: "hybrid"
  "scope": "items" | "docs" | "all",    // default: "items"
  "limit": integer,                     // default: 20, max: 50
  "cursor": string | null,
  "include_archived": boolean           // default: false
}

Response 200:
{
  "data": [
    {
      "id": "uuid",
      "result_type": "work_item" | "doc",
      "title": "string",
      "type": "story" | "epic" | ...,    // work_item only
      "state": "draft" | ...,            // work_item only
      "score": float,
      "provenance": "keyword" | "semantic" | "both",
      "matched_by": ["keyword", "semantic"],
      "snippet": "string",
      "workspace_id": "uuid"
    }
  ],
  "pagination": {
    "cursor": "base64...",
    "has_next": boolean
  },
  "meta": {
    "total_count": integer,
    "search_mode_used": "hybrid" | "keyword" | "semantic",
    "fallback_reason": "puppet_unavailable" | null
  }
}

Response 400: { "error": { "code": "INVALID_QUERY|INVALID_MODE|INVALID_SCOPE", "message": "..." } }
Response 401: missing/invalid token
Response 403: no workspace access
```

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Puppet returns 0 results, PG FTS returns N | Return PG FTS results, provenance=keyword, mode_used=keyword (partial fallback) |
| PG FTS returns 0 results, Puppet returns N | Return Puppet results, provenance=semantic |
| Both return 0 | Empty data array, total_count=0, 200 |
| Query has special characters | Sanitize before passing to PG `plainto_tsquery`; pass raw to Puppet (it handles its own escaping) |
| User is member of 10 workspaces | Puppet filter contains all 10 workspace_ids; PG WHERE uses `workspace_id = ANY(:ids)` |
| `limit` > 50 | Clamp to 50, include `"meta": { "limit_clamped": true }` |

---

## Non-Functional Requirements

- Hybrid search P95 latency: < 800ms (Puppet + PG run in parallel; dominated by Puppet RTT)
- Keyword-only P95: < 400ms (EP-09 budget)
- Puppet calls use a connection pool (min 2, max 10); no per-request new connections
- RRF weights and `k` configurable via env vars without code change
