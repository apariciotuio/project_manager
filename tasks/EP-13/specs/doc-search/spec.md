# Spec: Documentation Search + Browser
## US-131 (Search Tuio Documentation) + US-134 (Browse External Docs on Work Item)

**Epic**: EP-13
**Date**: 2026-04-13
**Status**: Draft

---

## Scope

External documentation (READMEs, ADRs, project docs) is indexed into Puppet per documentation source configured in admin (see admin-config spec). Doc search queries Puppet's doc collection, scoped to the workspace and public Tuio sources. The browser serves doc content via an internal API proxy — the browser never calls Puppet directly.

---

## US-131: Search Tuio Documentation from Within the App

### AC-131-1: Doc search returns results from Puppet doc collection

WHEN a user sends `POST /api/v1/search` with `{ "q": "...", "scope": "docs" }`
THEN the Puppet adapter queries the documentation collection
AND results include only docs from sources configured for the user's accessible workspaces OR flagged as public (`is_public=true`)
AND each result includes `{ "id", "result_type": "doc", "title", "source_name", "url", "snippet", "score", "provenance": "semantic" }`

### AC-131-2: Doc results respect workspace isolation

WHEN a user searches docs
THEN the Puppet adapter filters by `workspace_ids` the user can access PLUS docs from public sources
AND docs from a workspace the user is not a member of (non-public) are never returned

### AC-131-3: Doc search degrades gracefully if Puppet is unavailable

WHEN Puppet is unavailable during a doc search
THEN the response returns an empty result set with `"meta": { "fallback_reason": "puppet_unavailable" }`
AND HTTP status is 200 (no keyword fallback exists for docs — unlike work items)

### AC-131-4: Scope=all merges work items and doc results

WHEN `scope=all` is used
THEN work item results (keyword+semantic or hybrid) and doc results (semantic only) are interleaved
AND the merged list is sorted by a unified relevance score
AND each result includes `"result_type"` to allow frontend to render different card types

### AC-131-5: Doc results link to the original source

WHEN a doc result is returned
THEN the `url` field contains the original document URL (e.g. GitHub permalink, Confluence page URL)
AND a `doc_id` field references the internal `documentation_sources` record

---

## US-134: Browse External Documentation While Editing a Work Item

### AC-134-1: Related docs appear in work item detail side panel

WHEN a user opens a work item detail view
THEN the frontend fetches `GET /api/v1/work-items/{id}/related-docs`
AND the response includes up to 5 semantically related documentation items from Puppet
AND each entry includes `{ "doc_id", "title", "source_name", "snippet", "url", "score" }`

### AC-134-2: Related docs respect access control

WHEN the related-docs endpoint is called
THEN only docs from the work item's workspace (or public sources) are returned
AND the endpoint returns 200 with empty list if no related docs exist (not 404)

### AC-134-3: Doc preview panel shows document content inline

WHEN a user clicks a doc result or a related doc
THEN the frontend opens a side panel and fetches `GET /api/v1/docs/{doc_id}/content`
AND the response returns `{ "doc_id", "title", "content_html", "url", "source_name", "last_indexed_at" }`
AND `content_html` is the rendered Markdown/HTML of the document (sanitized server-side)
AND the panel renders the content with a link to open the full source in a new tab

### AC-134-4: Doc preview access is access-controlled

WHEN a user requests doc content
THEN the server checks that the doc's `workspace_id` matches a workspace the user is a member of, OR `is_public=true`
AND if access is denied, the response is `403 Forbidden` with `"code": "DOC_ACCESS_DENIED"`

### AC-134-5: Doc content is cached

WHEN doc content is fetched from Puppet
THEN the response is cached in Redis with key `doc_content:{doc_id}` and TTL 1 hour
AND subsequent requests for the same doc within the TTL are served from cache without calling Puppet
AND cache is invalidated when the doc is re-indexed

### AC-134-6: Related docs are lazy-loaded

WHEN the work item detail page loads
THEN related docs are NOT loaded as part of the main detail request
AND they are fetched via a separate client-side request after the main detail renders
AND if the related-docs call fails or Puppet is unavailable, the side panel shows "No related docs available" (no error state)

---

## API Contracts

```
GET /api/v1/work-items/{id}/related-docs
Authorization: Bearer <token>

Response 200:
{
  "data": [
    {
      "doc_id": "uuid",
      "title": "string",
      "source_name": "string",
      "snippet": "string",
      "url": "string",
      "score": float
    }
  ]
}
Response 401, 403, 404 (work item not found)

---

GET /api/v1/docs/{doc_id}/content
Authorization: Bearer <token>

Response 200:
{
  "doc_id": "uuid",
  "title": "string",
  "content_html": "string",   // sanitized HTML
  "url": "string",
  "source_name": "string",
  "last_indexed_at": "ISO8601"
}
Response 401
Response 403: { "error": { "code": "DOC_ACCESS_DENIED" } }
Response 404: { "error": { "code": "DOC_NOT_FOUND" } }
```

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Work item has no related docs in Puppet | Empty array, 200 |
| Doc source was deleted after indexing | Return doc result with `"source_deleted": true`; content endpoint returns 404 |
| Puppet returns a doc with malformed HTML | Server-side HTML sanitization strips unsafe tags before serving |
| Doc `content_html` exceeds 500KB | Truncate at 500KB and include `"content_truncated": true` in response |
| User accesses doc from a workspace they just left | 403 (membership re-checked on every request) |
| Multiple workspaces, public doc in one | Public doc returns for all authenticated users regardless of workspace |
