# Redis + Celery Removal Plan

**Date:** 2025-04-18
**Constraint:** No pg-jobs table. BackgroundTasks for async. Loss-on-restart accepted.
**Scale:** <100 users, <50 workspaces, VPN-only, single Uvicorn worker.

---

## PR 1: Delete CacheService + RedisCacheAdapter (dead code prune) — PR1: shipped — 3 files deleted

No behavior change. All services already accept `ICache` via DI; `InMemoryCacheAdapter` stays as the only implementation. `get_cache_adapter` dependency always returns `InMemoryCacheAdapter`.

### Files to DELETE

| File | Notes |
|------|-------|
| `backend/app/infrastructure/cache/redis_cache.py` | `CacheService` class — unused standalone |
| `backend/app/infrastructure/adapters/redis_cache_adapter.py` | `RedisCacheAdapter` — replaced by `InMemoryCacheAdapter` |
| `backend/tests/unit/infrastructure/cache/test_redis_cache.py` | Tests for deleted class |

### Files to MODIFY

| File | Change |
|------|--------|
| `backend/app/presentation/dependencies.py` | Remove `RedisCacheAdapter` import + branch. `get_cache_adapter` always returns `InMemoryCacheAdapter`. Remove `settings.redis.use_fake` check. |
| `backend/app/presentation/controllers/dundun_callback_controller.py` | Remove `RedisCacheAdapter` import + `settings.redis.use_fake` branch (~L441-447). Always use `InMemoryCacheAdapter`. |
| `backend/app/domain/ports/cache.py` | Update docstring: remove "Redis adapter implements this" reference. |

### Verification
- `grep -r "RedisCacheAdapter\|redis_cache" backend/app/` returns zero hits.
- All existing tests pass (services use `ICache` via DI, tests inject fakes).

---

## PR 2: PgRateLimiter replaces RedisRateLimiter + migration

> **PR2a shipped** — PgRateLimiter + migration + tests; wiring deferred to PR2b when main.py is free.
> **PR2b shipped** — wiring switched, RedisRateLimiter deleted.

### New file: `backend/app/infrastructure/rate_limiting/pg_rate_limiter.py`

**Responsibility:** Sliding-window rate limiter backed by Postgres. Same `RateLimitResult` dataclass, same `check(identifier, limit)` signature as `RedisRateLimiter`.

**Strategy:** Single `INSERT ... ON CONFLICT DO UPDATE SET count = count + 1` per check. Window = 1-minute bucket. Fail-open on DB error (same as current Redis fail-open).

**Constructor:** Takes `AsyncSession` (or raw asyncpg connection from the pool).

### Migration: `backend/migrations/versions/XXXX_rate_limit_buckets.py`

```sql
CREATE TABLE rate_limit_buckets (
    identifier      VARCHAR(255)  NOT NULL,
    window_minute   BIGINT        NOT NULL,
    count           INTEGER       NOT NULL DEFAULT 1,
    PRIMARY KEY (identifier, window_minute)
);

CREATE INDEX ix_rate_limit_buckets_window ON rate_limit_buckets (window_minute);
-- TODO(pg-jobs): add periodic cleanup job to DELETE WHERE window_minute < extract(epoch from now())::bigint / 60 - 10
```

### Files to DELETE

| File | Notes |
|------|-------|
| `backend/app/infrastructure/rate_limiting/redis_rate_limiter.py` | Entire module |
| `backend/tests/unit/presentation/middleware/test_rate_limit.py` | Rewrite for PG-based |
| `backend/tests/integration/test_rate_limiting.py` | Rewrite for PG-based |

### Files to MODIFY

| File | Change |
|------|--------|
| `backend/app/main.py` | Remove `import redis.asyncio`, remove `_redis_client` creation (L150-152). `RateLimitMiddleware` constructor takes DB session factory instead of Redis client. |
| `backend/app/infrastructure/rate_limiting/__init__.py` | Export `PgRateLimiter`, `RateLimitMiddleware` |

### New tests
- Unit: `test_pg_rate_limiter.py` — test `check()` with fake async session.
- Integration: rewrite `test_rate_limiting.py` — hit middleware with real Postgres.

### Verification
- `grep -r "redis" backend/app/infrastructure/rate_limiting/` returns zero.
- Rate limit headers appear on responses.

---

## PR 3: PgNotificationBus replaces RedisPubSub, adapt SSE stack — PR3 shipped — PgNotificationBus + LISTEN/NOTIFY; RedisPubSub deleted, job_progress_controller adapted, JobProgressService rewritten as in-memory, progress_task.py _RedisPublishProto→_PublishProto; 1 publisher migrated (job_progress_controller)

### New file: `backend/app/infrastructure/sse/pg_notification_bus.py`

**Responsibility:** Pub/sub using Postgres `LISTEN/NOTIFY`. Same interface as `RedisPubSub`: `publish(channel, message)` and `subscribe(channel) -> AsyncIterator[dict]`.

**Design:**
- `publish()`: Executes `SELECT pg_notify($1, $2)` on any pooled connection.
- `subscribe()`: Acquires a **dedicated** raw `asyncpg` connection (not from SQLAlchemy pool), runs `LISTEN <channel>`, yields messages via `connection.add_listener()` / polling loop. Releases connection in `finally`.
- JSON payload in NOTIFY (8000 byte Postgres limit — fine for SSE frames).
- Constructor takes `asyncpg.Pool` (or connection DSN to create one).

### Files to DELETE

| File | Notes |
|------|-------|
| `backend/app/infrastructure/sse/redis_pubsub.py` | Replaced by `pg_notification_bus.py` |
| `backend/app/infrastructure/sse/job_progress_service.py` | Rewrite: back with PG table or in-memory dict (job state is ephemeral, <100 concurrent jobs). In-memory dict with TTL is simplest. |
| `backend/tests/unit/infrastructure/test_sse_infrastructure.py` | Rewrite for PG bus |
| `backend/tests/unit/infrastructure/test_sse_handler.py` | Adapt: SseHandler protocol stays same, just swap fake |
| `backend/tests/integration/test_sse_job_progress.py` | Rewrite: use real PG LISTEN/NOTIFY |

### Files to MODIFY

| File | Change |
|------|--------|
| `backend/app/infrastructure/sse/sse_handler.py` | Update docstring only. `_PubSubProto` is already generic enough — `PgNotificationBus` will satisfy it. |
| `backend/app/infrastructure/sse/channel_registry.py` | Update docstrings: s/Redis/Postgres NOTIFY/. No code changes. |
| `backend/app/infrastructure/sse/job_progress_service.py` | Rewrite: `InMemoryJobProgressService` with `dict[str, dict]` + TTL eviction. Same public API (`get_state`, `set_state`, `complete`, `fail`). |
| `backend/app/presentation/controllers/job_progress_controller.py` | Remove `import redis.asyncio`. `override_job_progress_service` returns `InMemoryJobProgressService`. `_stream_job_progress` uses `PgNotificationBus` instead of `RedisPubSub`. |
| `backend/app/infrastructure/tasks/progress_task.py` | `_RedisPublishProto` renamed to `_PublishProto`. Constructor takes `PgNotificationBus` (or any publish-compatible protocol). Update docstrings. |

### Testing
- Integration: real Postgres LISTEN/NOTIFY test — publish on one connection, subscribe on another, assert message arrives.
- Unit: SseHandler tests use a `FakePubSub` (already protocol-based, no change needed to test structure).

### Risks
- NOTIFY payload limit: 8000 bytes. SSE progress frames are ~200 bytes. Fine.
- Dedicated listener connection: must be a raw asyncpg connection, NOT from SQLAlchemy pool. Document this clearly.
- Single-worker only: LISTEN/NOTIFY works per-connection. Multi-worker needs shared connection or revert to external bus.

---

## PR 4: Replace Celery tasks with plain async + BackgroundTasks — PR4 shipped — Celery removed, BackgroundTasks + TODO(pg-jobs) planted at 4 sites (dundun_tasks ×3, puppet_sync_tasks, puppet_ingest_tasks)

This is the largest PR. All Celery task wrappers become plain `async def` functions.

### Files to DELETE

| File | Notes |
|------|-------|
| `backend/app/config/celery_app.py` | Celery app factory + beat schedule |
| `backend/app/worker.py` | Celery worker entrypoint |
| `backend/tests/unit/infrastructure/tasks/test_dundun_tasks.py` | Rewrite: no more `.delay()` |
| `backend/tests/unit/infrastructure/tasks/test_puppet_ingest_tasks.py` | Rewrite |
| `backend/tests/unit/infrastructure/tasks/test_progress_task.py` | Adapt (remove Redis ref) |
| `backend/tests/unit/presentation/controllers/test_job_progress_controller.py` | Adapt |

### Files to MODIFY (tasks become plain async)

Each task file loses its `@celery_app.task` decorator, `asyncio.run()` wrapper, `self.retry()` logic. The inner `_run_*` async functions become the public API.

| File | Before | After |
|------|--------|-------|
| `backend/app/infrastructure/tasks/dundun_tasks.py` | `@celery_app.task` + `asyncio.run(_run())` | `async def invoke_suggestion_agent(...)`, `async def invoke_gap_agent(...)`, `async def invoke_quick_action_agent(...)`. Called via `background_tasks.add_task()`. Add `# TODO(pg-jobs): crash mid-run = silent failure; move to pg jobs table if reliability needed` |
| `backend/app/infrastructure/tasks/notification_tasks.py` | `@celery_app.task` wrapping `_run_fan_out` | `async def fan_out_notification(...)` — called **inline** (not background) because fan-out is <100ms for <100 users. `sweep_expired_notifications` becomes plain async, triggered by cron endpoint. Add TODO. |
| `backend/app/infrastructure/tasks/puppet_sync_tasks.py` | `@celery_app.task` | `async def drain_puppet_outbox(...)`. Called via `background_tasks.add_task()`. Add TODO. |
| `backend/app/infrastructure/tasks/puppet_ingest_tasks.py` | `@celery_app.task` | `async def process_puppet_ingest(...)`. Called via `background_tasks.add_task()`. Add TODO. |
| `backend/app/infrastructure/tasks/progress_task.py` | References Redis | References `_PublishProto` (already done in PR 3). Remove Celery mentions from docstrings. |

### Periodic jobs (currently Celery Beat)

| File | Before | After |
|------|--------|-------|
| `backend/app/infrastructure/jobs/session_cleanup.py` | `@celery_app.task` | Plain `async def cleanup_expired_sessions()`. Expose via internal endpoint `POST /api/v1/internal/jobs/session-cleanup`. Trigger from host cron: `curl -s http://localhost:8000/api/v1/internal/jobs/session-cleanup` |
| `backend/app/infrastructure/jobs/oauth_state_cleanup.py` | `@celery_app.task` | Same pattern. `POST /api/v1/internal/jobs/oauth-state-cleanup`. Cron every 10m. |
| `backend/app/infrastructure/jobs/expire_drafts_task.py` | `@celery_app.task` | Same pattern. `POST /api/v1/internal/jobs/expire-drafts`. Cron daily 02:00 UTC. |

### New file: `backend/app/presentation/controllers/internal_jobs_controller.py`

**Responsibility:** Internal-only router (`/api/v1/internal/jobs/...`) for cron-triggered periodic jobs. No auth (VPN-only). Each endpoint calls the plain async function and returns `{"ok": true, "result": ...}`.

**Endpoints:**
- `POST /internal/jobs/session-cleanup`
- `POST /internal/jobs/oauth-state-cleanup`
- `POST /internal/jobs/expire-drafts`
- `POST /internal/jobs/notification-sweep`

Guard: Reject if `APP_ENV=production` and request not from localhost/VPN CIDR. Or simpler: require a shared secret header `X-Internal-Key`.

### Files to MODIFY (callers — wire BackgroundTasks)

Any controller or service that previously would have called `.delay()` needs to accept `BackgroundTasks` from FastAPI and call `background_tasks.add_task(the_async_fn, **kwargs)`.

Currently **no call sites exist in app code** (tasks are only dispatched via Celery beat or tests). This means:
- Periodic jobs: wired via internal endpoints + cron (above).
- Dundun/Puppet tasks: when a controller eventually needs to dispatch them, it will use `background_tasks.add_task()`. Leave TODO comments at each task function.

### Config cleanup

| File | Change |
|------|--------|
| `backend/app/config/settings.py` | Delete `CelerySettings` class. Delete `self.celery = CelerySettings()`. Delete `RedisSettings` class. Delete `self.redis = RedisSettings()`. |
| `backend/tests/conftest.py` | Remove `test_settings.celery = ...` and `test_settings.redis = ...` lines. |

### TODO comments to plant

Every `background_tasks.add_task()` call site and every task function that accepts loss-on-restart:
```python
# TODO(pg-jobs): crash mid-run = silent failure; move to pg jobs table if reliability needed
```

---

## PR 5: Remove deps from pyproject.toml, final cleanup — **PR5: shipped 2026-04-18** — Redis + Celery fully removed from stack

### Files to MODIFY

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Remove: `celery[sqlalchemy]>=5.3`, `redis[asyncio]>=5.0`. Remove `kombu` if present. Remove `flower` if present. |
| `docker-compose.dev.yml` | Remove `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` env vars. Remove any `redis` or `celery-worker` or `flower` service definitions if present. |
| Any `.env.example` or `.env.template` | Remove `CELERY_*` and `REDIS_*` env vars. |

### Verification
- `grep -rn "redis\|celery\|kombu\|flower" backend/app/ backend/tests/` returns zero (excluding comments/TODOs about migration history).
- `uv pip install` / `pip install -e .` succeeds without redis/celery.
- All tests pass.
- App starts with single `uvicorn` command, no worker process needed.

---

## Summary counts

| Metric | Count |
|--------|-------|
| Migrations | 1 (`rate_limit_buckets`) |
| Files to delete | 14 |
| Files to modify | ~22 |
| Files to add | 3 (`pg_rate_limiter.py`, `pg_notification_bus.py`, `internal_jobs_controller.py`) |
| Dependencies removed | 2 (`celery[sqlalchemy]`, `redis[asyncio]`) |
| PRs | 5 |
| Estimated wall-clock | ~2 days |

---

## Risks

| Risk | Mitigation |
|------|------------|
| LISTEN/NOTIFY 8KB payload limit | SSE frames are ~200B. If exceeded, publish a reference ID and fetch from DB. |
| Dedicated listener connection leak | `finally` block releases. Integration test verifies. |
| Single-worker restriction (BackgroundTasks) | Documented constraint. TODO(pg-jobs) at every call site. |
| Crash = silent failure for background tasks | Accepted for MVP. TODO(pg-jobs) planted. |
| Rate limit bucket table bloat | TODO: periodic cleanup via cron endpoint (same pattern as session cleanup). |
| Celery beat removal = no scheduler | Replaced by host cron + internal endpoints. Simpler, zero dependencies. |

---

## Post-review fixes (code review 2026-04-18)

- MF-1 (channel name SQL injection): `_CHANNEL_PATTERN = re.compile(r"^[A-Za-z0-9_:.\-]{1,63}$")` added to `pg_notification_bus.py`; `_validate_channel()` called in `publish()` and `subscribe()` before any SQL. 11 new tests covering injection, spaces, empty, >63 chars, and valid formats.
- SF-2 (dead keepalive check): removed duplicate post-event block in `SseHandler._generate()` that compared `now - last_event_at` immediately after `last_event_at = loop.time()` (always False). Pre-event check retained. Added keepalive test with mocked loop clock.
- SF-3 (stale Redis/Celery docstrings): `channel_registry.py` module + method docstrings updated — "Redis pub/sub key strings" → "Postgres NOTIFY channel strings", "Redis channel for a Celery job" → "Postgres NOTIFY channel for an async job".
- SF-4 (rename `_redis` attribute): already fixed in PR3 — `progress_task.py` uses `_PublishProto` and `self._publisher`. No action needed.
- SF-6 (internal jobs rate limit): `@auth_limiter.limit("5/minute")` added to `POST /api/v1/internal/jobs/{name}/run`.

## Out of scope

- pg-jobs table
- APScheduler or any in-process scheduler
- Multi-worker support
- Flower replacement / task monitoring UI
- Retry policies for BackgroundTasks
- Rate limit bucket cleanup job (planted as TODO)
