# Backend Tasks: EP-13 — Puppet Integration (Search + Sync Pipeline)

**Epic**: EP-13
**Date**: 2026-04-13 (rewritten 2026-04-14 per decisions #4/#9/#24/#28)
**Status**: Draft

> **Scope (2026-04-14)**: Puppet is the sole search backend. No PG FTS, no hybrid RRF, no keyword+semantic fusion, no learned re-ranker, no per-workspace embeddings. Our BE calls Puppet directly with tag `wm_<workspace_id>`. Below: Hybrid/RRF groups are removed; doc-search collapses into the single search endpoint with Puppet tag scoping.

---

## API Contracts (Reference)

```
GET    /api/v1/search?q=...&cursor=&limit=&include_archived=&state=&type=&team_id=&owner_id=
         Response: { data: [SearchResult], pagination: {...}, meta: { puppet_latency_ms } }

GET    /api/v1/search/suggest?q=...
         Response: { data: [{ title, id, type }] }  -- prefix / type-ahead (decision #24)

GET/POST/PATCH/DELETE /api/v1/saved-searches   (decision #24)

POST   /api/v1/admin/integrations/puppet
PATCH  /api/v1/admin/integrations/puppet/{id}
GET    /api/v1/admin/integrations/puppet
POST   /api/v1/admin/puppet/{id}/health-check        → 202 Accepted
POST   /api/v1/admin/puppet/reindex                  → 202 Accepted
GET    /api/v1/admin/puppet/health                   → { lag_seconds, last_reconcile_at, failure_count_24h }
```

SearchResult shape (returned verbatim from Puppet, plus our wrapper metadata):
```json
{
  "id": "uuid",
  "entity_type": "work_item | section | comment | task | doc",
  "title": "string",
  "type": "string",
  "state": "string",
  "score": 1.23,
  "snippet": "string",
  "workspace_id": "uuid"
}
```

---

## Bounded Slice (2026-04-17) — puppet_ingest_requests pipeline

> Implemented per instructions: migration + domain + infra + service + REST + Celery task

- [x] Migration 0034: `puppet_ingest_requests` table — id, workspace_id, source_kind, work_item_id, payload, status, puppet_doc_id, attempts, last_error, created_at, updated_at, succeeded_at. Indexes: (workspace_id, status), (work_item_id), (created_at DESC). RLS policy workspace isolation. (2026-04-17)
- [x] `PuppetIngestRequestORM` added to orm.py (2026-04-17)
- [x] `PuppetIngestRequest` domain model: create(), mark_dispatched/succeeded/failed/skipped/reset_for_retry transitions. 11 unit tests. (2026-04-17)
- [x] `IPuppetIngestRequestRepository` interface in domain/repositories/ (2026-04-17)
- [x] `PuppetIngestRequestRepositoryImpl`: save, get, claim_queued_batch (FOR UPDATE SKIP LOCKED), has_succeeded_for_work_item, list_by_workspace (2026-04-17)
- [x] `PuppetHTTPClient`: index_document/delete_document/search/health with PuppetNotImplementedError + TODO for PENDING Puppet platform-ingestion endpoints (2026-04-17)
- [x] `verify_puppet_signature`: HMAC-SHA256 mirror of verify_dundun_signature (2026-04-17)
- [x] `PuppetSettings` extended: service_key + callback_secret (2026-04-17)
- [x] `FakePuppetClient` updated: idempotent delete, index_calls/delete_calls trackers (2026-04-17)
- [x] `PuppetIngestService`: enqueue() + dispatch_pending() with idempotency + retry logic. 8 unit tests. (2026-04-17)
- [x] `POST /api/v1/puppet/ingest-callback`: HMAC-only, idempotent by ingest_request_id (2026-04-17)
- [x] `POST /api/v1/puppet/search`: workspace-scoped proxy, category server-enforced (2026-04-17)
- [x] `GET /api/v1/puppet/ingest-requests`: paginated admin observability (2026-04-17)
- [x] `POST /api/v1/puppet/ingest-requests/{id}/retry`: manual retry for failed/skipped rows (2026-04-17)
- [x] 14 integration tests covering all 4 REST endpoints (2026-04-17)
- [x] `process_puppet_ingest` Celery task: outbox drain → ingest_request creation → dispatch_pending, acks_late=True, soft_time_limit=30, max_retries=3, exponential backoff. 5 unit tests. (2026-04-17)

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
- [x] **[GREEN]** Define `domain/ports/puppet_client.py`: `IPuppetClient` Protocol — already existed; FakePuppetClient updated with index_calls/delete_calls trackers and idempotent delete (2026-04-17)
- [ ] **[RED]** Write unit tests for `PuppetClient.search()`: correct payload shape, workspace_ids filter present
- [ ] **[RED]** Write unit tests for `PuppetClient.upsert()`: correct HTTP PUT, no PII fields (no email)
- [x] **[RED]** Write unit tests for `PuppetClient.delete()`: 404 is silently swallowed — FakePuppetClient delete is idempotent, test_fake_puppet_delete_missing_doc_is_noop passes (2026-04-17)
- [ ] **[RED]** Write unit tests for `PuppetClient.probe()`: returns True on 200, False on any exception
- [x] **[GREEN]** Implement `infrastructure/adapters/puppet_http_client.py`: PuppetHTTPClient with index_document/delete_document/search/health + PuppetNotImplementedError stub guard (2026-04-17)
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

## Group 4: SearchService (thin Puppet wrapper)

**Acceptance Criteria**
WHEN `SearchService.search(q, workspace_id, facets, cursor, limit)` is called THEN `PuppetClient.search` is called with `tag=wm_<workspace_id>` and facet tags
WHEN the query ends with `*` OR is short/prefix THEN `PuppetClient.prefix` is used (decision #24)
WHEN Puppet times out / returns 5xx THEN the wrapper raises `SearchUnavailableError` (controller maps to 503 `SEARCH_UNAVAILABLE` — no local fallback exists)
WHEN `workspace_id` is missing or not supplied by the session THEN the wrapper raises — `wm_<workspace_id>` is ALWAYS server-enforced, never client-supplied

- [ ] **[RED]** Write test: `search()` calls Puppet with correct `tag=wm_<workspace_id>`
- [ ] **[RED]** Write test: facet filters (state/type/team_id/owner_id/archived) forwarded as Puppet tags
- [ ] **[RED]** Write test: Puppet timeout → `SearchUnavailableError` (no partial result)
- [ ] **[RED]** Write test: prefix endpoint routes to `PuppetClient.prefix`
- [ ] **[RED]** Write test: workspace_id must come from session, never from request body/query
- [ ] **[GREEN]** Implement `application/services/search_service.py` as a thin wrapper over `PuppetClient`
- [ ] **[GREEN]** No `RRF_K` / `RRF_WEIGHT_*` env vars — no fusion. Remove any such references if they leaked into earlier drafts.

---

## Group 5: SavedSearchService (decision #24)

**Acceptance Criteria**
WHEN a user creates a saved search THEN `(workspace_id, user_id, name, query, filters)` is persisted
WHEN a user lists saved searches THEN only their own records are returned
WHEN a user runs a saved search THEN `SearchService.search()` is called with the stored `(query, filters)`

- [ ] **[RED]** Write test: CRUD on `saved_searches` scoped to the calling user
- [ ] **[RED]** Write test: cannot read/update/delete another user's saved search (404, not 403, to avoid leaking existence)
- [ ] **[GREEN]** Implement `SavedSearchService` + `saved_search_repo_impl.py`
- [ ] **[GREEN]** Wire CRUD controller at `/api/v1/saved-searches`

(DocSearch / DocContent — collapsed into the main search flow. Puppet indexes both internal and external documentation under their own tags; our wrapper passes the query untouched. No separate `DocContentService`, no `doc_content_cache.py` in our repo — doc rendering is Puppet's responsibility or a direct Puppet URL.)

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

- [x] **[RED]** Write test: `process_puppet_ingest` — Puppet upsert called with correct payload (test_index_row_creates_ingest_request_and_dispatches, 2026-04-17)
- [x] **[RED]** Write test: `process_puppet_ingest` — retries with exponential backoff on failure (test_puppet_failure_marks_ingest_request_failed, 2026-04-17)
- [ ] **[RED]** Write test: `index_work_item` — dead-letter after 3 failures, `puppet_index_failures` updated
- [x] **[RED]** Write test: empty outbox → no-op (test_empty_outbox_returns_zero, 2026-04-17)
- [x] **[RED]** Write test: `deindex_work_item` — puppet delete called; 404 does not raise (test_delete_idempotent_when_doc_not_found, 2026-04-17)
- [ ] **[RED]** Write test: `reconcile_workspace` — drifted items enqueue index tasks
- [ ] **[RED]** Write test: `reconcile_workspace` — items absent from DB enqueue deindex tasks
- [ ] **[RED]** Write test: `reconcile_workspace` — records `puppet_reconcile_runs` entry
- [ ] **[RED]** Write test: `health_check` — updates `integration_configs.state` and `last_health_check_status`
- [x] **[GREEN]** Implement `infrastructure/tasks/puppet_ingest_tasks.py`: process_puppet_ingest task with acks_late=True, soft_time_limit=30, max_retries=3, exponential backoff (2026-04-17)
- [ ] **[GREEN]** Register `puppet.reconcile` on Celery beat schedule (daily 02:00 UTC)
- [ ] **[GREEN]** Register `puppet.health_check` on Celery beat schedule (every 600s)
- [x] **[REFACTOR]** `acks_late=True` on all index/deindex tasks (safe re-execution if worker crashes) — done on process_puppet_ingest (2026-04-17)

---

## Group 9: Search Controllers

**Acceptance Criteria**
WHEN `GET /api/v1/search?q=...` is called THEN `SearchService.search()` is called with the session's `workspace_id` (never from the request)
WHEN `q` is empty / < 2 chars THEN 422 with `INVALID_QUERY`
WHEN unauthenticated THEN 401
WHEN Puppet is unavailable THEN 503 `SEARCH_UNAVAILABLE`

- [ ] **[RED]** Write integration test: GET search returns Puppet result list with snippets, wm tag injected server-side
- [ ] **[RED]** Write test: empty / short `q` → 422 INVALID_QUERY
- [ ] **[RED]** Write test: unauthenticated → 401
- [ ] **[RED]** Write test: Puppet 5xx → 503 SEARCH_UNAVAILABLE (no fallback)
- [ ] **[RED]** Write test: `GET /search/suggest` → returns prefix matches
- [ ] **[RED]** Write test: workspace isolation — user from workspace A cannot see results from workspace B even by manipulating query params
- [ ] **[GREEN]** Implement `presentation/controllers/search_controller.py`
- [ ] **[GREEN]** Implement `presentation/controllers/saved_search_controller.py`
- [ ] **[GREEN]** Implement `presentation/controllers/puppet_health_controller.py` (GET /admin/puppet/health)

---

## Group 10: Tests (Integration + E2E)

- [ ] **[RED]** Integration test: end-to-end search flow with `FakePuppetClient`
- [ ] **[RED]** Integration test: Puppet unavailable → 503 SEARCH_UNAVAILABLE
- [ ] **[RED]** Integration test: reconcile job detects drift and reindexes
- [ ] **[RED]** Integration test: admin creates puppet config → health check triggered
- [ ] **[RED]** Integration test: workspace isolation enforced (user A cannot see workspace B items)
- [ ] **[RED]** Integration test: push-on-write — creating/updating a work_item fires a Puppet index task within 3s of commit
- [ ] **[GREEN]** Implement all integration tests using fakes (no real Puppet API in test suite)
- [ ] **[REFACTOR]** Ensure no tests import `PuppetClient` directly — all use `FakePuppetClient` implementing `IPuppetClient`
