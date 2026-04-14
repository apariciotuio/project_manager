# Backend Tasks: EP-13 — Semantic Search + Puppet Integration

**Epic**: EP-13
**Date**: 2026-04-13
**Status**: Draft

---

## API Contracts (Reference)

```
POST   /api/v1/search
         Body: { q, mode: hybrid|keyword|semantic, scope: items|docs|all, limit, cursor, include_archived }
         Response: { data: [SearchResult], pagination: {...}, meta: { search_mode_used, fallback_reason } }

GET    /api/v1/work-items/{id}/related-docs
         Response: { data: [RelatedDoc] }

GET    /api/v1/docs/{doc_id}/content
         Response: { doc_id, title, content_html, url, source_name, last_indexed_at }

POST   /api/v1/admin/integrations/puppet
PATCH  /api/v1/admin/integrations/puppet/{id}
GET    /api/v1/admin/integrations/puppet
POST   /api/v1/admin/puppet/{id}/health-check        → 202 Accepted
POST   /api/v1/admin/puppet/reindex                  → 202 Accepted

POST   /api/v1/admin/documentation-sources
GET    /api/v1/admin/documentation-sources
DELETE /api/v1/admin/documentation-sources/{id}
```

SearchResult shape:
```json
{
  "id": "uuid",
  "result_type": "work_item | doc",
  "title": "string",
  "type": "string",
  "state": "string",
  "score": 1.23,
  "provenance": "keyword | semantic | both",
  "matched_by": ["keyword"],
  "snippet": "string",
  "workspace_id": "uuid"
}
```

---

## Group 1: Migrations

**Acceptance Criteria**
WHEN migrations run THEN `documentation_sources`, `puppet_index_failures`, `puppet_reconcile_runs` tables exist
AND `integration_configs` has a unique partial index on `(workspace_id, provider)` where `provider='puppet'`
AND all new tables have appropriate indexes per design.md

- [ ] **[RED]** Write migration test asserting all three new tables exist after applying migrations
- [ ] **[GREEN]** Create Alembic migration: `documentation_sources` table + indexes
- [ ] **[GREEN]** Create Alembic migration: `puppet_index_failures` table
- [ ] **[GREEN]** Create Alembic migration: `puppet_reconcile_runs` table
- [ ] **[GREEN]** Add unique partial index on `integration_configs(workspace_id, provider)` for `provider='puppet'`
- [ ] **[REFACTOR]** Verify all CONCURRENTLY indexes use `transactional_ddl=False` pattern (EP-10 precedent)

---

## Group 2: Puppet Adapter (Domain Port + Infrastructure)

**Acceptance Criteria**
WHEN `IPuppetClient.search()` is called with workspace_ids THEN the HTTP request includes `filter.workspace_ids`
WHEN Puppet returns 404 on `delete()` THEN no exception is raised (idempotent)
WHEN Puppet API times out THEN `asyncio.TimeoutError` propagates to the caller

- [ ] **[RED]** Write tests for `IPuppetClient` interface contract via a fake implementation
- [ ] **[GREEN]** Define `domain/ports/puppet_client.py`: `IPuppetClient` Protocol, `PuppetSearchResult`, `PuppetIndexPayload` dataclasses
- [ ] **[RED]** Write unit tests for `PuppetClient.search()`: correct payload shape, workspace_ids filter present
- [ ] **[RED]** Write unit tests for `PuppetClient.upsert()`: correct HTTP PUT, no PII fields (no email)
- [ ] **[RED]** Write unit tests for `PuppetClient.delete()`: 404 is silently swallowed
- [ ] **[RED]** Write unit tests for `PuppetClient.probe()`: returns True on 200, False on any exception
- [ ] **[GREEN]** Implement `infrastructure/adapters/puppet/puppet_client.py`: full `PuppetClient`
- [ ] **[GREEN]** Implement `infrastructure/adapters/puppet/puppet_payload_builder.py`: `build_payload(work_item) -> PuppetIndexPayload`
- [ ] **[RED]** Write test: payload builder excludes email, includes all required fields, `aggregated_sections` is concatenated text
- [ ] **[GREEN]** Wire `PuppetClient` into DI container; inject via `IPuppetClient` everywhere
- [ ] **[REFACTOR]** Extract HTTP error handling into a shared decorator/context manager (`raise_for_status` + structured logging)

---

## Group 3: IndexingService

**Acceptance Criteria**
WHEN `IndexingService.on_work_item_created()` is called THEN a `puppet.index_work_item` Celery task is enqueued asynchronously
WHEN Puppet is not configured for the workspace THEN no task is enqueued
WHEN `on_work_item_deleted()` is called THEN `puppet.deindex_work_item` is enqueued

- [ ] **[RED]** Write tests for `IndexingService.on_work_item_created()`: task enqueued, correct payload
- [ ] **[RED]** Write test: no task enqueued when no `integration_configs` for workspace
- [ ] **[RED]** Write tests for `on_work_item_updated()`: task enqueued only for relevant field changes
- [ ] **[RED]** Write test for `on_work_item_deleted()`: deindex task enqueued
- [ ] **[GREEN]** Implement `application/services/indexing_service.py`
- [ ] **[GREEN]** Hook `IndexingService` into `WorkItemService.create/update/delete` (EP-09 service layer)
- [ ] **[REFACTOR]** Verify hook does not block the main transaction (task enqueued after flush, not before commit)

---

## Group 4: HybridSearchService

**Acceptance Criteria**
WHEN `mode=hybrid` THEN PG FTS and Puppet run in parallel via `asyncio.gather`
WHEN Puppet times out THEN results come from PG FTS only and `fallback_reason='puppet_unavailable'` is set
WHEN RRF fusion runs THEN items in both result sets get higher scores than items in one set only
WHEN `mode=keyword` THEN no Puppet call is made

- [ ] **[RED]** Write test: `mode=hybrid` calls both keyword and Puppet services
- [ ] **[RED]** Write test: Puppet timeout → fallback to keyword-only, `fallback_reason` set
- [ ] **[RED]** Write test: RRF fusion scoring — item in both lists scores higher than item in one list
- [ ] **[RED]** Write test: provenance='both' when item appears in both result sets
- [ ] **[RED]** Write test: provenance='keyword' when item appears in keyword only
- [ ] **[RED]** Write test: `mode=keyword` → no Puppet call made (assert fake not called)
- [ ] **[RED]** Write test: `mode=semantic` → no PG FTS call made
- [ ] **[RED]** Write test: RRF weights and k configurable via constructor injection
- [ ] **[RED]** Write test: workspace_ids passed to both engines
- [ ] **[GREEN]** Implement `application/services/hybrid_search_service.py` with `_rrf_fuse`
- [ ] **[GREEN]** Read `RRF_K`, `RRF_WEIGHT_KEYWORD`, `RRF_WEIGHT_SEMANTIC` from env vars with defaults (60, 0.40, 0.60)
- [ ] **[REFACTOR]** Ensure `_semantic_safe` logs at WARN with `integration=puppet` structured field

---

## Group 5: DocSearchService

**Acceptance Criteria**
WHEN `DocSearchService.search()` is called THEN Puppet queries the `docs` collection
WHEN Puppet is unavailable THEN empty result with `fallback_reason` is returned (no keyword fallback for docs)
WHEN `DocContentService.get_content()` is called THEN content is fetched from Puppet and cached in Redis

- [ ] **[RED]** Write test: `DocSearchService.search()` passes `collection='docs'` to Puppet
- [ ] **[RED]** Write test: doc search filters by user's workspace_ids plus public sources
- [ ] **[RED]** Write test: Puppet unavailable → empty list returned with fallback_reason
- [ ] **[RED]** Write test: `DocContentService.get_content()` — cache hit returns without Puppet call
- [ ] **[RED]** Write test: access denied when doc workspace not in user's workspace_ids and not public
- [ ] **[RED]** Write test: content_html is sanitized (bleach) before returning
- [ ] **[GREEN]** Implement `application/services/doc_search_service.py`
- [ ] **[GREEN]** Implement `application/services/doc_content_service.py`
- [ ] **[GREEN]** Implement `infrastructure/cache/doc_content_cache.py` (Redis, TTL 3600s)
- [ ] **[REFACTOR]** Content truncation at 500KB with `content_truncated: true` flag

---

## Group 6: Admin Config Endpoints (Puppet Integration)

**Acceptance Criteria**
WHEN `POST /api/v1/admin/integrations/puppet` is called THEN credentials are Fernet-encrypted (never plaintext)
WHEN `GET /api/v1/admin/integrations/puppet` is called THEN no `api_key` in response
WHEN user lacks `CONFIGURE_INTEGRATION` capability THEN 403
WHEN duplicate config exists for workspace THEN 409

- [ ] **[RED]** Write test: POST creates `integration_configs` with `provider='puppet'`, state='active'
- [ ] **[RED]** Write test: credentials are encrypted (assert `api_key` not in DB column)
- [ ] **[RED]** Write test: GET response does not contain `api_key`
- [ ] **[RED]** Write test: PATCH rotates credentials (old ref deleted, new ref stored)
- [ ] **[RED]** Write test: 403 when user lacks `CONFIGURE_INTEGRATION`
- [ ] **[RED]** Write test: 409 when puppet config already exists for workspace
- [ ] **[RED]** Write test: audit_events records `puppet_config_created` / `puppet_config_updated`
- [ ] **[GREEN]** Implement `presentation/controllers/puppet_config_controller.py`
- [ ] **[GREEN]** Implement `application/services/puppet_config_service.py` (reuses EP-10 `CredentialsStore`)
- [ ] **[REFACTOR]** Health check auto-triggered after config creation (enqueue `puppet.health_check` task)

---

## Group 7: Admin Config Endpoints (Documentation Sources)

**Acceptance Criteria**
WHEN a doc source is created THEN `puppet.index_doc_source` task is enqueued
WHEN a doc source is deleted THEN soft-delete and `puppet.deindex_doc_source` enqueued
WHEN `source_type=github_repo` THEN URL must match GitHub pattern

- [ ] **[RED]** Write test: POST creates `documentation_sources` record with `status='pending'`
- [ ] **[RED]** Write test: index_doc_source task enqueued on create
- [ ] **[RED]** Write test: invalid source_type → 400
- [ ] **[RED]** Write test: github_repo URL validation
- [ ] **[RED]** Write test: DELETE soft-deletes and enqueues deindex task
- [ ] **[RED]** Write test: GET lists only non-deleted sources for workspace
- [ ] **[RED]** Write test: audit event recorded on create and delete
- [ ] **[GREEN]** Implement `presentation/controllers/doc_source_controller.py`
- [ ] **[GREEN]** Implement `application/services/doc_source_service.py`
- [ ] **[GREEN]** Implement `infrastructure/persistence/sqlalchemy/doc_source_repo_impl.py`

---

## Group 8: Celery Tasks

**Acceptance Criteria**
WHEN `puppet.index_work_item` runs THEN Puppet `upsert()` is called with correct payload
WHEN Puppet fails 3 times THEN task moves to dead-letter and `puppet_index_failures` is updated
WHEN `puppet.reconcile_workspace` runs THEN drift is detected and reindex tasks enqueued for drifted items
WHEN `puppet.health_check` completes THEN `integration_configs.last_health_check_status` is updated

- [ ] **[RED]** Write test: `index_work_item` — Puppet upsert called with correct payload
- [ ] **[RED]** Write test: `index_work_item` — retries with exponential backoff on failure
- [ ] **[RED]** Write test: `index_work_item` — dead-letter after 3 failures, `puppet_index_failures` updated
- [ ] **[RED]** Write test: `index_work_item` — no-op when no puppet config
- [ ] **[RED]** Write test: `deindex_work_item` — puppet delete called; 404 does not raise
- [ ] **[RED]** Write test: `reconcile_workspace` — drifted items enqueue index tasks
- [ ] **[RED]** Write test: `reconcile_workspace` — items absent from DB enqueue deindex tasks
- [ ] **[RED]** Write test: `reconcile_workspace` — records `puppet_reconcile_runs` entry
- [ ] **[RED]** Write test: `health_check` — updates `integration_configs.state` and `last_health_check_status`
- [ ] **[GREEN]** Implement `infrastructure/tasks/puppet_tasks.py`: all tasks
- [ ] **[GREEN]** Register `puppet.reconcile` on Celery beat schedule (daily 02:00 UTC)
- [ ] **[GREEN]** Register `puppet.health_check` on Celery beat schedule (every 600s)
- [ ] **[REFACTOR]** `acks_late=True` on all index/deindex tasks (safe re-execution if worker crashes)

---

## Group 9: Search + Doc Controllers

**Acceptance Criteria**
WHEN `POST /api/v1/search` is called with `mode=hybrid` THEN `HybridSearchService.search()` is called
WHEN `q` is empty THEN 400 with `INVALID_QUERY`
WHEN `mode` is invalid THEN 400 with `INVALID_MODE`
WHEN unauthenticated THEN 401
WHEN `GET /api/v1/docs/{id}/content` is called for inaccessible doc THEN 403

- [ ] **[RED]** Write integration test: POST search, mode=hybrid, returns SearchResult list with provenance
- [ ] **[RED]** Write test: empty `q` → 400 INVALID_QUERY
- [ ] **[RED]** Write test: invalid mode → 400 INVALID_MODE
- [ ] **[RED]** Write test: invalid scope → 400 INVALID_SCOPE
- [ ] **[RED]** Write test: unauthenticated → 401
- [ ] **[RED]** Write test: `scope=all` returns both work items and docs
- [ ] **[RED]** Write test: related-docs returns up to 5 docs for work item
- [ ] **[RED]** Write test: doc content — 403 for inaccessible doc
- [ ] **[RED]** Write test: doc content — 404 for unknown doc_id
- [ ] **[GREEN]** Implement `presentation/controllers/search_controller.py`
- [ ] **[GREEN]** Implement `presentation/controllers/doc_controller.py`
- [ ] **[GREEN]** Implement `presentation/controllers/related_docs_controller.py`
- [ ] **[REFACTOR]** `POST /api/v1/search` → `GET /api/v1/search` kept as deprecated alias (keyword-only, 200 + deprecation header)

---

## Group 10: Tests (Integration + E2E)

- [ ] **[RED]** Integration test: full hybrid search flow with fake PuppetClient and real PG FTS
- [ ] **[RED]** Integration test: Puppet unavailable → keyword-only fallback, correct meta
- [ ] **[RED]** Integration test: reconcile job detects drift and reindexes
- [ ] **[RED]** Integration test: admin creates puppet config → health check triggered
- [ ] **[RED]** Integration test: workspace isolation enforced (user A cannot see workspace B items)
- [ ] **[GREEN]** Implement all integration tests using fakes (no real Puppet API in test suite)
- [ ] **[REFACTOR]** Ensure no tests import `PuppetClient` directly — all use `FakePuppetClient` implementing `IPuppetClient`
