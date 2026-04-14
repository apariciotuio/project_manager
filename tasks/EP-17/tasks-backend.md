# EP-17 Backend Tasks

## Progress Tracking

Update checkboxes after each step. Format: `[x] Step — note (YYYY-MM-DD)`.

---

## Group 0: Setup & Configuration

- [ ] Add env vars to settings: `LOCK_TTL_SECONDS=300`, `LOCK_HEARTBEAT_INTERVAL_SECONDS=30`, `UNLOCK_REQUEST_TTL_SECONDS=120`, `LOCK_FAIL_OPEN=false`
- [ ] Add `LockSettings` dataclass in `app/infrastructure/config/lock_settings.py`
- [ ] Add `get_lock_settings` FastAPI dependency
- [ ] Extend `channel_registry.py` with `"work_item_lock": "sse:work_item:{work_item_id}"`

---

## Group 1: Database Migration (Audit Table)

- [ ] **RED** — Write migration test: verify `work_item_lock_events` table exists, enum values, indexes, FK cascade
- [ ] Create Alembic migration: `work_item_lock_events` table with `lock_event_type` ENUM
  - Columns: `id UUID PK`, `work_item_id UUID NOT NULL FK → work_items(id) CASCADE`, `event_type lock_event_type NOT NULL`, `actor_id UUID FK → users(id) SET NULL`, `reason TEXT`, `metadata JSONB`, `created_at TIMESTAMPTZ DEFAULT NOW()`
  - Indexes: `(work_item_id, created_at DESC)`, `(actor_id, created_at DESC)`
  - Include `EXPLAIN ANALYZE` comment for queries: by work_item_id, by actor_id, by event_type
- [ ] **GREEN** — Run migration, verify tests pass
- [ ] Verify: no UPDATE or DELETE statements are possible on this table via any service path

---

## Group 2: Domain Layer

- [ ] **RED** — Write unit tests for `LockDTO`, `UnlockRequestDTO`, domain error classes
- [ ] Create `app/domain/locks/models.py`: `LockDTO`, `UnlockRequestDTO` (pure dataclasses, no ORM)
- [ ] Create `app/domain/locks/errors.py`: `AlreadyLockedError`, `NotLockHolderError`, `LockNotFoundError`, `UnlockRequestPendingError`, `CannotRequestOwnLockError`, `NoRequestPendingError`, `RedisUnavailableError`
- [ ] Create `app/domain/locks/repositories.py`: `LockEventRepository` interface (abstract)
- [ ] **GREEN** — All domain tests pass

---

## Group 3: Infrastructure — Lock Event Repository

- [ ] **RED** — Write tests for `LockEventRepositoryImpl.write_event()`: verifies correct PG insert per event_type, verifies no update/delete methods exist
- [ ] Implement `app/infrastructure/persistence/lock_event_repository_impl.py`
  - `write_event(event_type, work_item_id, actor_id, reason, metadata)` — async SQLAlchemy insert
  - No read methods required (admin support tools in EP-10 reads directly) ⚠️ originally MVP-scoped — see decisions_pending.md
- [ ] **GREEN** — Repository tests pass (use real async test DB session, not mocks)

---

## Group 4: LockService

- [ ] **RED** — Write unit tests for all `LockService` methods using fake Redis (in-memory dict with TTL simulation) and fake notification/SSE:
  - `test_acquire_free_item_returns_lock_dto`
  - `test_acquire_locked_item_raises_already_locked_with_current_holder`
  - `test_acquire_same_user_raises_already_locked_by_self`
  - `test_acquire_cross_workspace_raises_404`
  - `test_release_by_holder_deletes_redis_key`
  - `test_release_by_non_holder_raises_not_holder`
  - `test_release_missing_lock_raises_not_found`
  - `test_heartbeat_extends_ttl_and_updates_timestamp`
  - `test_heartbeat_non_holder_raises`
  - `test_heartbeat_missing_lock_raises`
  - `test_force_release_writes_audit_event_with_metadata`
  - `test_force_release_notifies_former_holder`
  - `test_force_release_missing_lock_raises`
  - `test_request_unlock_non_holder_creates_request`
  - `test_request_unlock_self_raises_cannot_request_own`
  - `test_request_unlock_duplicate_raises_pending`
  - `test_respond_release_calls_release`
  - `test_respond_ignore_deletes_request_notifies_requester`
  - `test_get_status_returns_none_when_no_lock`
  - `test_redis_unavailable_raises_redis_unavailable_error`
  - Triangulate: empty UUIDs, boundary TTLs, concurrent acquire simulation

- [ ] Implement `app/application/services/lock_service.py`
  - Use Redis `TIME` for all timestamps (never `datetime.utcnow()`)
  - Use `SET NX EX` for atomic acquire
  - Fire-and-forget PG audit writes via `asyncio.create_task` (do not block on PG for acquire/release hot path)
  - Publish SSE events after Redis operation succeeds
- [ ] **GREEN** — All service tests pass
- [ ] **REFACTOR** — No `any` types, all methods fully typed, no logic in `__init__`

---

## Group 5: `require_lock_holder` Dependency

- [ ] **RED** — Write unit tests:
  - `test_passes_when_caller_is_holder`
  - `test_raises_423_when_caller_is_not_holder`
  - `test_raises_423_with_lock_info_in_body`
  - `test_raises_423_not_in_edit_mode_when_no_lock`
  - `test_raises_503_when_redis_unavailable_fail_closed`
  - `test_passes_when_redis_unavailable_fail_open`
  - `test_raises_404_when_work_item_not_in_workspace`
- [ ] Implement `app/presentation/dependencies/lock.py`
- [ ] **GREEN** — Dependency tests pass
- [ ] Verify safe methods (`GET`, `HEAD`) are never wrapped with this dependency

---

## Group 6: API Endpoints

All endpoints use `get_current_workspace_id`, full Pydantic request/response schemas, workspace-scoped work item validation.

- [ ] **RED** — Write integration tests for each endpoint (HTTP layer, fake Redis, real async test DB):

  **POST /api/v1/work-items/:id/lock**
  - `test_acquire_201_when_free`
  - `test_acquire_409_when_locked_by_other`
  - `test_acquire_409_when_locked_by_self`
  - `test_acquire_404_when_item_not_in_workspace`
  - `test_acquire_429_when_rate_limited`
  - `test_acquire_401_when_unauthenticated`

  **DELETE /api/v1/work-items/:id/lock**
  - `test_release_204_by_holder`
  - `test_release_403_by_non_holder`
  - `test_release_404_when_no_lock`

  **POST /api/v1/work-items/:id/lock/heartbeat**
  - `test_heartbeat_200_by_holder`
  - `test_heartbeat_403_by_non_holder`
  - `test_heartbeat_404_when_no_lock`

  **POST /api/v1/work-items/:id/lock/request-unlock**
  - `test_request_unlock_202_by_non_holder`
  - `test_request_unlock_400_by_holder_self`
  - `test_request_unlock_409_when_request_pending`
  - `test_request_unlock_429_when_rate_limited`

  **POST /api/v1/work-items/:id/lock/respond-to-request**
  - `test_respond_release_204`
  - `test_respond_ignore_204`
  - `test_respond_403_by_non_holder`

  **POST /api/v1/work-items/:id/lock/force-release**
  - `test_force_release_200_with_capability`
  - `test_force_release_403_without_capability`
  - `test_force_release_404_when_no_lock`
  - `test_force_release_400_when_reason_too_short`

  **GET /api/v1/work-items/:id/lock**
  - `test_get_status_200_with_active_lock`
  - `test_get_status_200_null_when_no_lock`

- [ ] Create `app/presentation/routers/lock_router.py` with all 7 endpoints
- [ ] Create Pydantic schemas in `app/presentation/schemas/lock_schemas.py`: `AcquireLockResponse`, `LockStatusResponse`, `UnlockRequestBody`, `ForceReleaseBody`, `RespondToRequestBody`
- [ ] Wire `lock_router` into `app/main.py`
- [ ] Apply `require_lock_holder` to all mutable work item endpoints in `work_item_router.py`, `section_router.py`, `task_node_router.py`
- [ ] **GREEN** — All integration tests pass
- [ ] **REFACTOR** — Verify no business logic in controllers, all validation in Pydantic schemas

---

## Group 7: SSE Event Emissions

- [ ] **RED** — Write tests verifying SSE publish is called with correct channel and payload for each event type: `lock_acquired`, `lock_released`, `lock_force_released`, `unlock_requested`
- [ ] Verify all SSE publishes use `sse:work_item:{work_item_id}` channel
- [ ] Verify SSE frame format matches EP-12 shared format: `{ "type": "<event>", "payload": {...}, "channel": "<channel>" }`
- [ ] **GREEN** — SSE emission tests pass

---

## Group 8: Celery Tasks

- [ ] **RED** — Write tests for Celery tasks using fake Redis and fake notification service:
  - `test_notify_unlock_request_sends_notification_to_holder`
  - `test_notify_force_unlock_sends_notification_to_former_holder`
  - `test_notify_unlock_denied_sends_notification_to_requester`
  - `test_notify_unlock_granted_sends_notification_to_requester`
  - `test_auto_release_on_timeout_releases_lock_and_notifies`
  - `test_auto_release_on_timeout_skips_when_lock_already_gone`
  - `test_auto_release_race_guard_prevents_double_release` (SET NX on processing key)

- [ ] Implement `app/workers/tasks/lock_tasks.py`:
  - `notify_unlock_request`
  - `notify_force_unlock`
  - `notify_unlock_denied`
  - `notify_unlock_granted`
  - `auto_release_on_unlock_request_timeout` (with race guard via `SET NX`)

- [ ] Configure Redis keyspace notifications for `lock_request:work_item:*` expiry, OR add Celery beat schedule as fallback (30s interval)
- [ ] **GREEN** — All task tests pass

---

## Group 9: Rate Limiting

- [ ] Add rate limit rules to `RateLimitMiddleware` config:
  - `lock_acquire`: 20/min per user_id — key `ratelimit:lock_acquire:{user_id}`
  - `unlock_request`: 5/hour per user_id per work_item_id — key `ratelimit:unlock_request:{user_id}:{work_item_id}`
- [ ] **RED** — Write tests: `test_acquire_rate_limited_after_20_requests`, `test_unlock_request_rate_limited_after_5_per_hour`
- [ ] **GREEN** — Rate limit tests pass

---

## Group 10: Capability Check for Force Release

- [ ] Verify `force_unlock` capability is registered in EP-10 capability registry
- [ ] Apply `require_capabilities(["force_unlock"])` to the force-release endpoint
- [ ] **RED** — Tests: `test_force_release_403_without_force_unlock_capability`, `test_force_release_200_with_force_unlock_capability`
- [ ] **GREEN** — Capability tests pass

---

## Group 11: Observability & Audit

- [ ] Verify all LockService methods emit structured log lines with `work_item_id`, `actor_id`, `event_type` in context
- [ ] Add `WARNING` log on every force release: `lock_force_released work_item_id={} by admin_id={} former_holder_id={}`
- [ ] Add `WARNING` log on every request processed in fail-open mode
- [ ] Add `WARNING` log at startup if `LOCK_FAIL_OPEN=true`
- [ ] Verify `correlation_id` is present in all lock-related log lines (injected by EP-12 middleware)
- [ ] Verify Sentry captures exceptions from `LockService` (unhandled errors auto-captured via FastAPI integration)

---

## Group 12: List View — Lock State Embedding

- [ ] **RED** — Write test: list work items response includes `lock: { holder_id, holder_display_name, acquired_at } | null` per item
- [ ] Extend `WorkItemListDTO` to include optional `lock: LockSummaryDTO | None`
- [ ] Extend list repository query to LEFT JOIN on lock data — options:
  - **Preferred**: Redis multi-GET for active locks per item (single Redis pipeline call for all IDs in page)
  - **Fallback**: PostgreSQL: derive from `work_item_lock_events` (last `acquired` without a subsequent `released`/`force_released`/`auto_expired`) — acceptable only if Redis is unavailable
- [ ] **GREEN** — List tests pass

---

## Acceptance Criteria Checklist

- [ ] All write endpoints return `423 Locked` (not 422, not 403) when non-holder attempts write
- [ ] `423` response body includes holder info and `expires_at`
- [ ] `GET` and `HEAD` endpoints never trigger lock check
- [ ] Lock acquisition is atomic (SET NX — no race condition)
- [ ] TTL extended by exactly `LOCK_TTL_SECONDS` on each heartbeat
- [ ] All timestamps use Redis server time
- [ ] Force release requires `force_unlock` capability
- [ ] Force release audit event persists with full before-state metadata
- [ ] Former holder notified via EP-08 on force release
- [ ] Auto-release fires within 30 seconds of unlock request timeout
- [ ] Redis unavailability → 503 (fail-closed) by default
- [ ] All endpoints return 404 (not 423 or 403) for cross-workspace work item IDs
- [ ] No `any` types anywhere in lock-related code
- [ ] RED phase committed before each implementation step
