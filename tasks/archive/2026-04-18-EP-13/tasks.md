# EP-13 — Semantic Search + Puppet Integration

**Status (archived 2026-04-18 as v1)**: ✅ SHIPPED — Search via Puppet (thin wrapper) + outbox ingest pipeline + Celery `process_puppet_ingest` task + HMAC callback + admin observability endpoints. Frontend 59/61 items (SearchBar debounced type-ahead, SearchResultCard, DocResultCard, DocPreviewPanel, RelatedDocsWidget, SavedSearchesPanel, PuppetConfigForm, DocSourcesTable, i18n) — only deferrals are `useSearchParams` URL state wiring + React Query adoption (both polish, not feature-blocking).

> **Prior header said "backend IN FLIGHT; frontend NOT STARTED" — that's stale.** Ship-ready reality as of 2026-04-18: outbox + Celery + FE 59/61 + SearchService + PuppetHTTPClient stub (search/health real; index/delete wait on Puppet platform endpoints upstream).

### v1 scope shipped
- Migration 0034 + `PuppetIngestRequest` domain + repo + `PuppetIngestService`.
- Celery task `process_puppet_ingest` with acks_late, retry, exponential backoff.
- HMAC callback `POST /puppet/ingest-callback` (idempotent).
- Admin observability: `GET /puppet/ingest-requests` + `POST .../retry`.
- `PuppetHTTPClient` stub (search/health real; index/delete TODO pending upstream Puppet endpoints).
- `FakePuppetClient` for tests.
- Frontend 59/61: search UX + saved searches + Puppet admin config + doc sources table + i18n.

### v2 scope (new follow-up epic — NOT EP-13 v1)
- **Doc-sources full ingestion** (Group 7, PoC-grade in v1): GitHub, URL, path source scanners; currently BE stubs only.
- **Reconciliation job** (Group 8): `reconcile_workspace` drift detector + Celery beat schedule — observability-only, not core search path.
- **`IndexingService` hook layer** (Group 3): push-on-write from `WorkItemService.create/update/delete` → outbox. Current flow relies on manual/admin-triggered ingestion.
- **Integration test suite** (Groups 4, 9, 10, ~24 items): full end-to-end coverage with `FakePuppetClient`; unit coverage exists, integration-level tests deferred.
- **Upstream blocker**: Puppet platform-ingestion endpoints (`PUT /documents/{id}`, `DELETE`) still pending from Puppet team. Index/delete call paths are wired through the outbox but return 404 against current Puppet stub.
- **Puppet config encryption + health check task** (Group 6): credentials stored; Fernet encryption + periodic health beat deferred (FE form already wired).

Decisions relevant to this scope cut:
- **#4** (proposal): Puppet is sole search backend — no hybrid RRF, no local FTS fallback. v1 honors this.
- **#28** (proposal): No learned re-ranker, no per-workspace embeddings.
- **Upstream PENDING**: Puppet platform-ingestion endpoints — cross-team dependency.

Sub-trackers (authoritative, historical):
- Backend: `tasks-backend.md`
- Frontend: `tasks-frontend.md`

## Phase summary

| Phase | Artifact | Status |
|-------|----------|--------|
| Proposal / Specs / Design | `proposal.md`, `specs/`, `design.md` | **COMPLETED** |
| Backend (outbox, Celery sync task to Puppet, ingest endpoints) | `tasks-backend.md` | **IN FLIGHT** — outbox + Celery task shipped; Puppet platform-ingestion endpoints pending |
| Frontend (search bar wiring, results page, result-to-detail link) | `tasks-frontend.md` | **NOT STARTED** |
| Code review + review-before-push | — | Pending |

## Dependencies

Depends on EP-09 (listings/dashboards scaffolding), EP-10 (admin/integration config), EP-12 (security/rate limits on external calls). See `tasks/tasks.md` dependency table.
