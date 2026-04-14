# Technical Design: EP-13 — Semantic Search + Puppet Integration

**Epic**: EP-13
**Stack**: Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL 16 / Celery + Redis / Next.js 14
**Date**: 2026-04-13
**Status**: Proposed

---

## 1. Architecture Overview

EP-13 extends EP-09 search without replacing it. PG FTS remains the keyword engine; Puppet is additive. EP-10 integration pattern (Fernet credentials, `integration_configs`, capability guards) is reused directly.

```
Browser
  └── POST /api/v1/search
        └── SearchController
              └── HybridSearchService
                    ├── KeywordSearchService (EP-09 PG FTS)          [parallel]
                    └── PuppetSearchAdapter → Puppet API             [parallel]
                          └── RRFRanker.fuse(keyword_results, semantic_results)
                                └── SearchResponse with provenance labels

Work item mutation
  └── WorkItemService
        └── IndexingEventPublisher.enqueue(work_item_id, event)
              └── Celery integrations queue
                    └── puppet.index_work_item task
                          └── PuppetIndexAdapter → Puppet API

Celery beat
  └── puppet.reconcile (daily 02:00 UTC)
  └── puppet.health_check (per integration_config, every 10min)
```

---

## 2. Puppet Adapter — Domain Port + Infrastructure Implementation

### Domain port (interface)

```python
# domain/ports/puppet_client.py
from typing import Protocol
from uuid import UUID
from dataclasses import dataclass

@dataclass
class PuppetSearchResult:
    id: str
    title: str
    snippet: str
    score: float
    result_type: str  # 'work_item' | 'doc'
    workspace_id: UUID | None
    url: str | None

@dataclass
class PuppetIndexPayload:
    id: UUID
    workspace_id: UUID
    title: str
    description: str
    spec_content: str | None
    aggregated_sections: str | None
    tags: list[str]
    owner_id: UUID | None
    state: str
    type: str
    updated_at: str  # ISO8601

class IPuppetClient(Protocol):
    async def search(
        self,
        q: str,
        workspace_ids: list[UUID],
        collection: str,  # 'work_items' | 'docs'
        limit: int,
    ) -> list[PuppetSearchResult]: ...

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

## 3. Hybrid Search Service — RRF Fusion

### Algorithm

Reciprocal Rank Fusion (Cormack et al., 2009):

```
score_rrf(item) = sum over engines e of: w_e / (k + rank_e(item))
```

Where:
- `k = 60` (smoothing constant — configurable via `RRF_K` env var)
- `w_keyword = 0.40` (configurable via `RRF_WEIGHT_KEYWORD`)
- `w_semantic = 0.60` (configurable via `RRF_WEIGHT_SEMANTIC`)
- `rank_e(item)` = 1-based rank in engine `e`'s result list (items not present get `rank = len(results) + 1`)

```python
# application/services/hybrid_search_service.py
import asyncio
from dataclasses import dataclass

@dataclass
class SearchResult:
    id: str
    result_type: str
    title: str
    score: float
    provenance: str   # 'keyword' | 'semantic' | 'both'
    matched_by: list[str]
    snippet: str
    workspace_id: str

class HybridSearchService:
    def __init__(
        self,
        keyword_service: KeywordSearchService,
        puppet_client: IPuppetClient,
        rrf_k: int = 60,
        w_keyword: float = 0.40,
        w_semantic: float = 0.60,
    ): ...

    async def search(self, q: str, mode: str, scope: str, workspace_ids: list[UUID], limit: int) -> SearchResponse:
        fallback_reason = None

        if mode == "keyword":
            kw_results = await self._keyword_service.search(q, workspace_ids, limit)
            return self._build_response(kw_results, [], mode_used="keyword")

        if mode == "semantic":
            sem_results = await self._semantic_only(q, workspace_ids, scope, limit)
            return self._build_response([], sem_results, mode_used="semantic")

        # hybrid: parallel execution
        kw_task = asyncio.create_task(self._keyword_service.search(q, workspace_ids, limit * 2))
        sem_task = asyncio.create_task(self._semantic_safe(q, workspace_ids, scope, limit * 2))

        kw_results, (sem_results, fallback_reason) = await asyncio.gather(kw_task, sem_task)

        fused = self._rrf_fuse(kw_results, sem_results)[:limit]
        return self._build_response(fused, mode_used="hybrid" if not fallback_reason else "keyword",
                                    fallback_reason=fallback_reason)

    async def _semantic_safe(self, q, workspace_ids, scope, limit):
        try:
            results = await asyncio.wait_for(
                self._puppet.search(q, workspace_ids, self._scope_to_collection(scope), limit),
                timeout=self._timeout_s,
            )
            return results, None
        except Exception as e:
            logger.warning("puppet_unavailable", error=str(e), integration="puppet")
            return [], "puppet_unavailable"

    def _rrf_fuse(self, kw: list, sem: list) -> list[SearchResult]:
        scores: dict[str, float] = {}
        provenance: dict[str, set] = {}
        items: dict[str, SearchResult] = {}

        for rank, r in enumerate(kw, start=1):
            scores[r.id] = scores.get(r.id, 0) + self._w_kw / (self._k + rank)
            provenance.setdefault(r.id, set()).add("keyword")
            items[r.id] = r

        for rank, r in enumerate(sem, start=1):
            scores[r.id] = scores.get(r.id, 0) + self._w_sem / (self._k + rank)
            provenance.setdefault(r.id, set()).add("semantic")
            if r.id not in items:
                items[r.id] = r

        result = []
        for item_id, score in sorted(scores.items(), key=lambda x: -x[1]):
            item = items[item_id]
            p = provenance[item_id]
            prov_str = "both" if len(p) == 2 else next(iter(p))
            result.append(SearchResult(
                id=item_id, result_type=item.result_type, title=item.title,
                score=score, provenance=prov_str, matched_by=list(p),
                snippet=item.snippet, workspace_id=str(item.workspace_id)
            ))
        return result
```

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
| RRF vs learned fusion | RRF (static weights) | ML re-ranker | No training data at MVP; RRF is proven, parameter-free, easily tuneable |
| Puppet timeout | 2000ms hard timeout | No timeout | Unbounded Puppet calls would blow search P95 |
| Doc content serving | Internal proxy + Redis cache | Direct Puppet URL from browser | Enforces access control; avoids CORS; enables caching |
| Index payload | Snapshot on task execution | Event-carried state | Avoids stale payloads from delayed Celery execution; always indexes current state |
| Separate collection for docs vs work items | Separate Puppet collections | Single collection with type filter | Cleaner indexing pipelines; Puppet can use different embedding models per collection |

---

## 14. Out of Scope for MVP

- Real-time index updates via WebSocket (indexing is eventually consistent — async Celery)
- User-level search history or saved searches
- Custom embedding model configuration per workspace
- Faceted search filters on semantic results
- Puppet index export / import
- Multi-language search (EN only for MVP)
