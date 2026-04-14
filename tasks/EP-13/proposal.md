# EP-13 — Semantic Search + Puppet Integration

## Business Need

Users need to find work items and documentation by meaning, not just keywords. Current search (EP-09) uses PostgreSQL full-text search (tsvector/GIN). This works for exact terms and stems but fails for conceptual queries like "how we handle claim disputes" when the actual document says "resolución de reclamaciones".

Additionally, users need to search across **external documentation** — READMEs, Tuio project docs, architectural documents — to understand domain context while defining new work. Today this context lives outside the system, fragmenting knowledge.

Integrate with **Puppet** (Tuio's internal semantic search / documentation indexing platform) to provide:
- Semantic search over work items inside the workspace
- Search over external Tuio documentation (READMEs, project docs, ADRs)
- Unified "search everything" experience while working on an item

## Objectives

- Integrate with Puppet API for semantic search
- Index all work items, specifications, and comments in Puppet (push model)
- Query Puppet from the frontend search UI — returns ranked results by semantic similarity
- Index external documentation sources (configured per project in EP-10) into Puppet
- Hybrid search results: combine keyword (PG FTS) + semantic (Puppet) with clear provenance
- Documentation browser: read external docs without leaving the app
- Respect workspace isolation — Puppet queries scoped to accessible workspaces + public Tuio docs

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-130 | Semantic search over work items | Must |
| US-131 | Search Tuio documentation from within the app | Must |
| US-132 | Push work item changes to Puppet index | Must |
| US-133 | View unified search results (keyword + semantic) | Must |
| US-134 | Browse external documentation while editing an item | Should |
| US-135 | Admin: configure Puppet integration and documentation sources | Must |

## Acceptance Criteria

- WHEN a user searches with a conceptual query THEN Puppet returns semantically similar items AND PG FTS returns exact matches, merged and ranked
- WHEN a work item is created/updated THEN it is pushed to Puppet index asynchronously via Celery
- WHEN Puppet is unreachable THEN keyword search still works (Puppet is additive, not required)
- WHEN a user searches THEN results include both work items (internal) and docs (external) clearly distinguished
- WHEN viewing a work item THEN a side panel can show related Puppet documentation
- WHEN a user views search results THEN each result shows provenance: "matched by: semantic" vs "matched by: keyword"
- AND admin can configure Puppet API endpoint, credentials, and which documentation sources to sync
- AND workspace isolation is enforced — Puppet queries filter by accessible workspace_ids

## Technical Notes

- Puppet integration as wrapped adapter (never direct SDK calls from domain)
- Async indexing via Celery (`integrations` queue) on every work item create/update/delete
- Reindex task: daily Celery beat job to reconcile drift
- Search endpoint: `GET /api/v1/search?q=<text>&mode=hybrid|keyword|semantic&scope=items|docs|all`
- Hybrid ranking: reciprocal rank fusion (RRF) merging PG FTS scores + Puppet similarity scores
- Documentation browser: cached documents served via internal API, not direct to Puppet from browser
- Credentials: encrypted Fernet (same pattern as Jira in EP-10)

## Dependencies

- EP-09 (existing search infrastructure — extend, don't replace)
- EP-10 (integration configuration pattern)
- EP-12 (LLM adapter pattern for wrapped Puppet client)

## Complexity Assessment

**High** — External API integration, index maintenance, hybrid ranking, permission scoping at Puppet layer, documentation browser UI.

## Risks

- Puppet index drift if sync fails silently (need monitoring + daily reconcile)
- Search latency if Puppet is slow (need timeout with fallback to keyword-only)
- Permission leaks if Puppet doesn't filter by workspace (must enforce server-side)
- Cost: semantic search API calls, indexing overhead
