# Technical Design: EP-13 — Puppet Integration (Search)

**Epic**: EP-13
**Stack**: Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL 16 / Celery + Redis / Next.js 14

> **Resolved 2026-04-14 (decisions_pending.md #4, #9, #24, #28)**: Puppet is the sole search backend for the product. No PG FTS, no Elasticsearch, no RRF hybrid fusion, no learned re-ranker, no per-workspace embeddings, no multi-language pipelines. Our backend calls Puppet directly; Dundun is **not** in the search path (Dundun uses Puppet for its own RAG via its own tool, not through us).

> **⚠️ SUPERSEDES (post-EP-18)**: real Puppet OpenAPI v0.1.1 — `POST /api/v1/retrieval/semantic/` with `QueryRequest { query, categories?, tags?, top_k? }` → `QueryResponse { sources: Source[] }`, where `Source = { page_id?, title?, content, category?, tags?, score? }` (raw text, no HTML). Workspace isolation uses **Puppet `category`** (convention `tuio-wmp:ws:<workspace_id>:workitem|section|comment`). Entity-type facets use **tags** (`state:<x>`, `type:<y>`, `owner:<uuid>`, `team:<uuid>`, `archived:<bool>`, `tag:<slug>` for user tags from EP-15). `page_id` convention at ingestion: `"<entity_kind>:<uuid>"`. Snippet highlighting is generated server-side by our backend. **Puppet platform-ingestion endpoints are not yet implemented upstream** — until they ship, workspace-content searches return empty; Tuio external docs (category `tuio-docs:*`, Puppet's existing Notion ingestion) already work. The authoritative contract is in `tasks/EP-18/specs/read-tools-assistant-search-extras/spec.md#semantic-search` and `tasks/EP-18/plan-backend.md#4.2`. Any `wm_<workspace_id>` references below are legacy prose; implementation follows the category/tag split above.

---

## 1. Architecture Overview

```
Browser
  └── GET /api/v1/search
        └── SearchController
              └── SearchService
                    └── PuppetClient.search(q, tags=[wm_<workspace_id>, ...], limit, cursor)
                          ← returns ranked document IDs + snippets
                    └── Hydrate rows from Postgres by ID → SearchResponse

Domain write (work_item / comment / timeline_event / tag change)
  └── Service publishes a domain event → outbox → Celery task on queue `puppet_sync`
        └── PuppetClient.index_document({id, type, workspace_id, tags, fields})
              OR PuppetClient.delete_document(id)
```

- **Search path**: our BE → Puppet HTTP. No fan-out, no fusion.
- **Indexing path**: domain event → Celery `puppet_sync` queue → Puppet upsert/delete. Target eventual consistency <3 s.
- **Facet filters** are represented as Puppet tags: `wm_<workspace_id>`, `wm_type_<type>`, `wm_state_<state>`, `wm_project_<id>`, `wm_owner_<id>`, `wm_team_<id>`, `wm_tag_<slug>`.
- **If Puppet is down**: the searchbar UI shows "unavailable"; CRUD and non-search listings continue via Postgres unaffected. The health check (below) emits a warning.

---

## 2. PuppetClient — Domain Port + Infrastructure Implementation

### Domain port (interface)

```python
# domain/ports/puppet_client.py
from typing import Protocol
from uuid import UUID
from dataclasses import dataclass

@dataclass
class PuppetSearchResult:
    id: str
    document_type: str           # 'work_item' | 'comment' | 'timeline_event'
    title: str
    snippet: str
    score: float
    workspace_id: UUID | None
    url: str | None

@dataclass
class PuppetDocument:
    id: str                      # e.g. "work_item:<uuid>", "comment:<uuid>", "timeline_event:<uuid>"
    document_type: str
    workspace_id: UUID
    title: str
    body: str                    # concatenated searchable text
    tags: list[str]              # wm_<workspace_id>, wm_type_<type>, etc.
    metadata: dict

class IPuppetClient(Protocol):
    async def search(
        self,
        query: str,
        tags: list[str],
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[PuppetSearchResult], str | None]: ...

    async def search_prefix(
        self, prefix: str, tags: list[str], limit: int = 8
    ) -> list[PuppetSearchResult]: ...

    async def index_document(self, doc: PuppetDocument) -> None: ...

    async def delete_document(self, id: str) -> None: ...

    async def health(self) -> bool: ...

    async def upsert(self, payload: PuppetIndexPayload) -> None: ...

    async def delete(self, item_id: UUID, collection: str) -> None: ...

    async def get_doc_content(self, doc_id: str) -> str: ...  # returns HTML

    async def probe(self) -> bool: ...
```

The domain never imports the concrete implementation. All callers receive `IPuppetClient` via constructor injection.

### Infrastructure implementation

```python
# infrastructure/adapters/puppet/puppet_client.py
import httpx
from uuid import UUID

class PuppetClient:
    def __init__(self, base_url: str, api_key: str, timeout_ms: int = 2000):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_ms / 1000,
        )

    async def search(self, q: str, workspace_ids: list[UUID], collection: str, limit: int):
        response = await self._client.post("/search", json={
            "q": q,
            "filter": {"workspace_ids": [str(wid) for wid in workspace_ids]},
            "collection": collection,
            "limit": limit,
        })
        response.raise_for_status()
        return [PuppetSearchResult(**r) for r in response.json()["results"]]

    async def upsert(self, payload: PuppetIndexPayload) -> None:
        data = {
            "id": str(payload.id),
            "workspace_id": str(payload.workspace_id),
            "title": payload.title,
            "description": payload.description,
            "spec_content": payload.spec_content or "",
            "aggregated_sections": payload.aggregated_sections or "",
            "tags": payload.tags,
            "owner_id": str(payload.owner_id) if payload.owner_id else None,
            "state": payload.state,
            "type": payload.type,
            "updated_at": payload.updated_at,
        }
        response = await self._client.put(f"/items/{payload.id}", json=data)
        response.raise_for_status()

    async def delete(self, item_id: UUID, collection: str) -> None:
        response = await self._client.delete(f"/{collection}/{item_id}")
        if response.status_code == 404:
            return  # idempotent
        response.raise_for_status()

    async def probe(self) -> bool:
        try:
            r = await self._client.get("/health")
            return r.status_code == 200
        except Exception:
            return False
```

`PuppetClient` is NOT imported anywhere in `domain/` or `application/`. Only `infrastructure/` and DI wiring.

---

## 3. SearchService — direct Puppet call

No fusion, no hybrid, no RRF. The service is a thin wrapper that builds the tag array from the caller's facets and calls Puppet.

```python
# application/services/search_service.py

class SearchService:
    def __init__(self, puppet_client: IPuppetClient, work_item_repo: IWorkItemRepository): ...

    async def search(self, query: str, workspace_id: UUID, facets: SearchFacets, limit: int, cursor: str | None):
        tags = [f"wm_{workspace_id}"]
        tags.extend(self._facets_to_tags(facets))
        hits, next_cursor = await self._puppet.search(query, tags, limit, cursor)
        rows = await self._work_item_repo.list_by_ids([h.id for h in hits if h.document_type == "work_item"])
        return self._merge(hits, rows, next_cursor)

    async def suggest(self, prefix: str, workspace_id: UUID, limit: int = 8):
        tags = [f"wm_{workspace_id}"]
        return await self._puppet.search_prefix(prefix, tags, limit)
```

Saved searches (table owned in EP-09) store raw query + facet params and replay them through this service.

---

## 4. Index Payload Schema

Fields sent to Puppet per work item:

| Field | Source | Notes |
|-------|--------|-------|
| `id` | `work_items.id` | UUID string |
| `workspace_id` | `work_items.workspace_id` | For Puppet filtering |
| `title` | `work_items.title` | Highest-weight field |
| `description` | `work_items.description` | |
| `spec_content` | `work_items.spec_content` | Raw spec markdown |
| `aggregated_sections` | Concatenated spec sections text | From spec_sections table if present |
| `tags` | `work_items.tags` | Array of strings |
| `owner_id` | `work_items.owner_id` | UUID only, no PII |
| `state` | `work_items.state` | For potential state-based boosting |
| `type` | `work_items.type` | story, epic, task, etc. |
| `updated_at` | `work_items.updated_at` | Used for drift detection in reconcile |

No: email addresses, user names, workspace secrets, comments text (too volatile, too much noise).

---

## 5. Async Indexing via Celery

Queue: `integrations` (already defined for EP-10 Jira tasks)

```python
# infrastructure/tasks/puppet_tasks.py

@celery_app.task(
    bind=True,
    queue="integrations",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def index_work_item(self, work_item_id: str, event: str, workspace_id: str):
    """Upsert a work item to Puppet. event: created|updated|reconcile"""
    config = get_puppet_config(workspace_id)
    if not config:
        return  # no-op — Puppet not configured
    client = build_puppet_client(config)
    item = fetch_work_item(work_item_id)
    if not item:
        return  # deleted before task ran — no-op
    payload = build_payload(item)
    try:
        asyncio.run(client.upsert(payload))
        resolve_failure_record(work_item_id)
    except Exception as exc:
        try:
            self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            record_dead_letter(work_item_id, workspace_id, str(exc), self.request.retries + 1)
            raise


@celery_app.task(
    bind=True,
    queue="integrations",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def deindex_work_item(self, work_item_id: str, workspace_id: str):
    config = get_puppet_config(workspace_id)
    if not config:
        return
    client = build_puppet_client(config)
    asyncio.run(client.delete(UUID(work_item_id), collection="work_items"))


@celery_app.task(queue="integrations")
def reconcile_workspace(workspace_id: str):
    """Daily drift reconcile for one workspace."""
    ...


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Daily at 02:00 UTC
    sender.add_periodic_task(
        crontab(hour=2, minute=0),
        reconcile_all_workspaces.s(),
    )
    # Health checks every 10 minutes
    sender.add_periodic_task(600.0, check_puppet_health.s())
```

---

## 6. Reconcile Job

```python
@celery_app.task(queue="integrations")
def reconcile_all_workspaces():
    configs = fetch_all_active_puppet_configs()
    for config in configs:
        reconcile_workspace.delay(str(config.workspace_id))


@celery_app.task(queue="integrations")
def reconcile_workspace(workspace_id: str):
    run = start_reconcile_run(workspace_id)
    client = build_puppet_client_for_workspace(workspace_id)

    # 1. Find items that may have drifted
    items = fetch_work_items_updated_since(workspace_id, run.last_run_at)

    # 2. Batch Puppet existence checks (100 at a time)
    for batch in chunks(items, 100):
        for item in batch:
            puppet_meta = asyncio.run(client.get_item_meta(str(item.id)))
            if not puppet_meta or puppet_meta["updated_at"] < item.updated_at.isoformat():
                index_work_item.delay(str(item.id), "reconcile", workspace_id)
                run.items_reindexed += 1
            run.items_checked += 1

    finish_reconcile_run(run)
```

Drift window: max 24 hours (one reconcile cycle). Acceptable for semantic search — keyword search (PG FTS) is always current.

---

## 7. Documentation Search

Puppet uses a separate collection (`docs`) per workspace. Public Tuio docs are indexed into a `public` collection shared across workspaces.

Filter logic:
```python
# For doc search
workspace_ids_for_docs = user_workspace_ids  # user's accessible workspaces
# Puppet also searches the 'public' collection automatically (Puppet-side config)
```

Doc content is served via internal proxy (`GET /api/v1/docs/{doc_id}/content`), cached in Redis:

```python
# Key: doc_content:{doc_id}   TTL: 3600s
async def get_doc_content(doc_id: str, user: User) -> DocContent:
    cache_key = f"doc_content:{doc_id}"
    cached = await redis.get(cache_key)
    if cached:
        return DocContent.parse_raw(cached)

    source = await doc_source_repo.get_by_doc_id(doc_id)
    if not source:
        raise DocNotFoundError()
    if not source.is_public and source.workspace_id not in user.workspace_ids:
        raise DocAccessDeniedError()

    raw_html = await puppet_client.get_doc_content(doc_id)
    sanitized = bleach.clean(raw_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)
    content = DocContent(doc_id=doc_id, content_html=sanitized, ...)
    await redis.set(cache_key, content.json(), ex=3600)
    return content
```

---

## 8. New Database Tables

### documentation_sources

```sql
CREATE TABLE documentation_sources (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    name            varchar(255) NOT NULL,
    source_type     varchar(50) NOT NULL CHECK (source_type IN ('github_repo', 'url', 'path')),
    url             text NOT NULL,
    is_public       boolean NOT NULL DEFAULT false,
    status          varchar(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'indexing', 'indexed', 'error')),
    last_indexed_at timestamptz,
    item_count      integer,
    error_message   text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz,
    UNIQUE (workspace_id, url)  -- prevent duplicate source registrations
);
CREATE INDEX idx_doc_sources_workspace ON documentation_sources(workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_doc_sources_public ON documentation_sources(is_public) WHERE deleted_at IS NULL AND is_public = true;
```

### puppet_index_failures

```sql
CREATE TABLE puppet_index_failures (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    work_item_id    uuid NOT NULL,
    last_error      text NOT NULL,
    attempt_count   integer NOT NULL DEFAULT 1,
    failed_at       timestamptz NOT NULL DEFAULT now(),
    resolved_at     timestamptz,
    UNIQUE (work_item_id)
);
CREATE INDEX idx_puppet_failures_workspace ON puppet_index_failures(workspace_id) WHERE resolved_at IS NULL;
```

### puppet_reconcile_runs

```sql
CREATE TABLE puppet_reconcile_runs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    started_at      timestamptz NOT NULL,
    completed_at    timestamptz,
    items_checked   integer NOT NULL DEFAULT 0,
    items_reindexed integer NOT NULL DEFAULT 0,
    items_deindexed integer NOT NULL DEFAULT 0,
    errors          integer NOT NULL DEFAULT 0,
    error_details   jsonb
);
```

`integration_configs` is reused from EP-10 with `provider='puppet'`. Unique constraint: `(workspace_id, provider)`.

---

## 9. API Endpoints

```
POST   /api/v1/search                               → HybridSearchController
GET    /api/v1/work-items/{id}/related-docs          → RelatedDocsController
GET    /api/v1/docs/{doc_id}/content                 → DocContentController

POST   /api/v1/admin/integrations/puppet             → PuppetConfigController (CONFIGURE_INTEGRATION)
GET    /api/v1/admin/integrations/puppet             → PuppetConfigController
PATCH  /api/v1/admin/integrations/puppet/{id}        → PuppetConfigController
POST   /api/v1/admin/puppet/{id}/health-check        → PuppetAdminController (202)
POST   /api/v1/admin/puppet/reindex                  → PuppetAdminController (202)
POST   /api/v1/admin/documentation-sources           → DocSourceController
GET    /api/v1/admin/documentation-sources           → DocSourceController
DELETE /api/v1/admin/documentation-sources/{id}      → DocSourceController
```

Note: `POST /api/v1/search` replaces `GET /api/v1/search` from EP-09. The GET endpoint is kept for backward compatibility (mode=keyword only) but is deprecated.

---

## 10. Frontend Architecture

```
app/
  search/
    page.tsx                    -- unified search page (server component)

components/
  search/
    SearchBar.tsx               -- existing (EP-09), add mode toggle
    ModeToggle.tsx              -- new: hybrid|keyword|semantic tabs
    SearchResults.tsx           -- existing, extend for doc result type
    SearchResultCard.tsx        -- extend: provenance badge
    DocResultCard.tsx           -- new: doc-specific result card
  docs/
    DocPreviewPanel.tsx         -- new: side panel, slide-over
    RelatedDocsWidget.tsx       -- new: widget for work item detail
  admin/
    PuppetConfigForm.tsx        -- new: credentials setup
    DocSourcesTable.tsx         -- new: CRUD list + add form
```

State management: URL params remain source of truth for `q`, `mode`, `scope`. React Query for data fetching. `DocPreviewPanel` uses local component state for open/close.

---

## 11. Performance Budget

| Endpoint | P50 | P95 | Notes |
|----------|-----|-----|-------|
| `POST /api/v1/search` (hybrid) | < 400ms | < 800ms | Puppet + PG in parallel; dominated by Puppet RTT |
| `POST /api/v1/search` (keyword) | < 200ms | < 400ms | PG FTS only, EP-09 budget |
| `GET /api/v1/work-items/{id}/related-docs` | < 300ms | < 600ms | Puppet call, cached after first fetch |
| `GET /api/v1/docs/{doc_id}/content` | < 50ms | < 150ms | Redis cache hit; cold < 500ms |

---

## 12. DDD Layer Breakdown

```
domain/
  ports/
    puppet_client.py            (IPuppetClient Protocol)
  models/
    documentation_source.py     (DocumentationSource entity)
    puppet_index_failure.py     (PuppetIndexFailure value object)
  repositories/
    doc_source_repo.py          (IDocSourceRepository)
    puppet_failure_repo.py      (IPuppetFailureRepository)

application/
  services/
    hybrid_search_service.py    (HybridSearchService — RRF fusion)
    doc_search_service.py       (DocSearchService — Puppet doc collection)
    indexing_service.py         (IndexingService — enqueues Celery tasks)
    doc_source_service.py       (admin CRUD for documentation sources)
    puppet_config_service.py    (admin CRUD for Puppet integration config)

presentation/
  controllers/
    search_controller.py        (POST /api/v1/search)
    doc_controller.py           (GET /api/v1/docs/{id}/content)
    related_docs_controller.py  (GET /api/v1/work-items/{id}/related-docs)
    puppet_config_controller.py (admin config endpoints)
    doc_source_controller.py    (admin doc source endpoints)

infrastructure/
  adapters/
    puppet/
      puppet_client.py          (PuppetClient — concrete impl of IPuppetClient)
      puppet_payload_builder.py (builds PuppetIndexPayload from WorkItem)
  persistence/
    sqlalchemy/
      doc_source_repo_impl.py
      puppet_failure_repo_impl.py
  tasks/
    puppet_tasks.py             (index_work_item, deindex_work_item, reconcile, health_check)
  cache/
    doc_content_cache.py        (Redis cache for doc content)
```

---

## 13. Decisions and Rejected Alternatives

| Decision | Chosen | Rejected | Reason |
|----------|--------|----------|--------|
| Search endpoint method | POST | GET (EP-09 pattern) | Request body for complex filter objects; GET with large query strings is brittle |
| RRF vs learned fusion | RRF (static weights) | ML re-ranker | No training data available; RRF is proven, parameter-free, easily tuneable ⚠️ originally MVP-scoped — see decisions_pending.md |
| Puppet timeout | 2000ms hard timeout | No timeout | Unbounded Puppet calls would blow search P95 |
| Doc content serving | Internal proxy + Redis cache | Direct Puppet URL from browser | Enforces access control; avoids CORS; enables caching |
| Index payload | Snapshot on task execution | Event-carried state | Avoids stale payloads from delayed Celery execution; always indexes current state |
| Separate collection for docs vs work items | Separate Puppet collections | Single collection with type filter | Cleaner indexing pipelines; Puppet can use different embedding models per collection |

---

## 14. Out of Scope

> ⚠️ Items below were originally MVP-scoped deferrals. Review each against full-product scope; log outcomes in decisions_pending.md.

- Real-time index updates via WebSocket (indexing is eventually consistent — async Celery)
- User-level search history or saved searches
- Custom embedding model configuration per workspace
- Faceted search filters on semantic results
- Puppet index export / import
- Multi-language search (EN only)
