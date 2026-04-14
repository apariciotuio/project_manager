# EP-17 Technical Design — Edit Locking + Collaboration Control

## 1. Architecture Overview

Edit locking is a distributed coordination problem. The design uses Redis as the authoritative lock store (TTL-backed, fast, atomic) and PostgreSQL exclusively for immutable audit history. The two stores serve different purposes and must never be confused.

```
Client (edit mode)
  ├── POST /lock           → LockService.acquire()     → Redis SET NX + TTL
  ├── POST /lock/heartbeat → LockService.heartbeat()   → Redis EXPIRE
  ├── DELETE /lock         → LockService.release()     → Redis DEL + PG audit
  └── SSE sse:work_item:id ← RedisPubSub.publish()    ← lock state changes

Write endpoints
  └── require_lock_holder dep → Redis GET → compare holder_id vs current_user
        ├── match   → pass, write proceeds
        ├── mismatch → 423 Locked
        └── Redis down → 503 (fail-closed default)
```

---

## 2. Lock Storage

### Redis (source of truth for active locks)

Key pattern: `lock:work_item:{work_item_id}`

Value (JSON string):
```json
{
  "holder_id": "<uuid>",
  "holder_display_name": "<string>",
  "acquired_at": "<iso-8601>",
  "expires_at": "<iso-8601>",
  "last_heartbeat_at": "<iso-8601>"
}
```

TTL: Set to `LOCK_TTL_SECONDS` (default 300) on acquire. Reset to `LOCK_TTL_SECONDS` on each heartbeat. Redis native TTL manages expiry — no cron required for expiry itself.

Clock authority: All timestamps use Redis `TIME` command (returns server-side Unix time). Client-side `datetime.utcnow()` is never used for lock timestamps.

```python
# Pattern for getting Redis server time
redis_time = await redis.time()  # returns (seconds, microseconds)
now = datetime.utcfromtimestamp(redis_time[0])
```

### Unlock request store (ephemeral, Redis)

Key pattern: `lock_request:work_item:{work_item_id}`

Value (JSON string):
```json
{
  "requester_id": "<uuid>",
  "requester_display_name": "<string>",
  "reason": "<text>",
  "requested_at": "<iso-8601>",
  "expires_at": "<iso-8601>"
}
```

TTL: `UNLOCK_REQUEST_TTL_SECONDS` (default 120). Expiry triggers Celery auto-release task.

### PostgreSQL (audit only — not source of truth)

```sql
CREATE TYPE lock_event_type AS ENUM (
    'acquired',
    'released',
    'auto_expired',
    'force_released',
    'unlock_requested'
);

CREATE TABLE work_item_lock_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id    UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    event_type      lock_event_type NOT NULL,
    actor_id        UUID REFERENCES users(id) ON DELETE SET NULL,  -- NULL for system-triggered (auto_expired)
    reason          TEXT,           -- populated for force_released, unlock_requested
    metadata        JSONB,          -- former holder info, lock timestamps, trigger context
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_lock_events_work_item_id ON work_item_lock_events (work_item_id, created_at DESC);
CREATE INDEX idx_lock_events_actor_id     ON work_item_lock_events (actor_id, created_at DESC);
```

This table is append-only. No UPDATE, no DELETE paths exposed via any API.

Note: The proposal mentioned a `work_item_locks` table with a current lock row. That design is rejected — it creates two sources of truth (Redis + PG for the same lock state) which diverge under failure. PG is audit only.

---

## 3. LockService

Location: `app/application/services/lock_service.py`

```python
class LockService:
    def __init__(
        self,
        redis: Redis,
        lock_event_repo: LockEventRepository,
        notification_service: NotificationService,
        sse_publisher: RedisPubSub,
        settings: LockSettings,
    ): ...
```

### Methods

#### `acquire(work_item_id: UUID, workspace_id: UUID, user_id: UUID, user_display_name: str) -> LockDTO`

1. Verify work_item belongs to workspace (workspace-scoped repo, raises 404 on mismatch).
2. Get Redis server time.
3. Compute `expires_at = now + TTL_SECONDS`.
4. Build lock JSON value.
5. `SET NX EX` on `lock:work_item:{id}`. If returns nil → GET current lock → raise `AlreadyLockedError(current_lock: LockDTO)`.
6. Write `acquired` event to PG (fire-and-forget; do not block response on PG write — use Celery if needed).
7. Publish `lock_acquired` SSE event.
8. Return `LockDTO`.

#### `release(work_item_id: UUID, workspace_id: UUID, user_id: UUID) -> None`

1. GET `lock:work_item:{id}`. If None → raise `LockNotFoundError`.
2. Compare `holder_id` vs `user_id`. If mismatch → raise `NotLockHolderError`.
3. DEL `lock:work_item:{id}`.
4. DEL `lock_request:work_item:{id}` (clean up any pending request).
5. Write `released` event to PG.
6. Publish `lock_released` SSE event with `{ expired: false }`.

#### `heartbeat(work_item_id: UUID, workspace_id: UUID, user_id: UUID) -> LockDTO`

1. GET `lock:work_item:{id}`. If None → raise `LockNotFoundError`.
2. Compare `holder_id` vs `user_id`. If mismatch → raise `NotLockHolderError`.
3. Get Redis server time.
4. Update `last_heartbeat_at` and `expires_at` in value.
5. SET the key with updated value and reset EX to TTL_SECONDS.
6. Return updated `LockDTO`. (No PG write, no SSE — high-frequency operation.)

#### `force_release(work_item_id: UUID, workspace_id: UUID, admin_id: UUID, reason: str) -> LockDTO`

1. GET `lock:work_item:{id}`. If None → raise `LockNotFoundError`.
2. Capture former lock state.
3. DEL `lock:work_item:{id}`.
4. DEL `lock_request:work_item:{id}` if present.
5. Write `force_released` event to PG with full metadata.
6. Publish `lock_force_released` SSE event.
7. Enqueue Celery task `notify_force_unlock` to send EP-08 notification to former holder.
8. Return `LockDTO` of the released lock (before-state).

#### `request_unlock(work_item_id: UUID, workspace_id: UUID, requester_id: UUID, requester_display_name: str, reason: str) -> UnlockRequestDTO`

1. GET `lock:work_item:{id}`. If None → raise `LockNotFoundError`.
2. If `holder_id == requester_id` → raise `CannotRequestOwnLockError`.
3. Check `lock_request:work_item:{id}` — if exists → raise `UnlockRequestPendingError(existing_request)`.
4. Get Redis server time.
5. SET `lock_request:work_item:{id}` with TTL `UNLOCK_REQUEST_TTL_SECONDS`.
6. Write `unlock_requested` event to PG.
7. Publish `unlock_requested` SSE event to `sse:work_item:{id}`.
8. Enqueue Celery task `notify_unlock_request` (sends EP-08 notification to holder).
9. Return `UnlockRequestDTO`.

#### `respond_to_request(work_item_id: UUID, workspace_id: UUID, user_id: UUID, decision: Literal["release", "ignore"]) -> None`

1. GET `lock:work_item:{id}`. If None → raise `LockNotFoundError`.
2. Compare `holder_id` vs `user_id`. If mismatch → raise `NotLockHolderError`.
3. GET `lock_request:work_item:{id}`. If None → raise `NoRequestPendingError`.
4. If `decision == "release"` → call `self.release(...)`.
5. If `decision == "ignore"` → DEL `lock_request:work_item:{id}` + enqueue `notify_unlock_denied` task.

#### `get_status(work_item_id: UUID, workspace_id: UUID) -> LockDTO | None`

1. Verify workspace scoping (404 on mismatch).
2. GET `lock:work_item:{id}`. If None → return None.
3. Return `LockDTO`.

---

## 4. Middleware: `require_lock_holder`

Location: `app/presentation/dependencies/lock.py`

FastAPI dependency injected on all mutable work item endpoints.

```python
async def require_lock_holder(
    work_item_id: UUID,
    workspace_id: UUID = Depends(get_current_workspace_id),
    current_user: AuthenticatedUser = Depends(get_current_user),
    lock_service: LockService = Depends(get_lock_service),
    settings: LockSettings = Depends(get_lock_settings),
) -> None:
    try:
        lock = await lock_service.get_status(work_item_id, workspace_id)
    except RedisUnavailableError:
        if settings.fail_open:
            logger.warning("lock_fail_open_active", work_item_id=str(work_item_id))
            return
        raise HTTPException(status_code=503, detail={"error": {"code": "LOCK_STORE_UNAVAILABLE"}})

    if lock is None:
        raise HTTPException(status_code=423, detail={"error": {"code": "NOT_IN_EDIT_MODE", "lock": None}})

    if lock.holder_id != current_user.id:
        raise HTTPException(status_code=423, detail={
            "error": {
                "code": "LOCKED",
                "lock": lock.to_response_dict(),
            }
        })
```

Applied via `Depends(require_lock_holder)` on each mutable endpoint. NOT applied to `GET`, `HEAD`, or lock management endpoints themselves.

---

## 5. API Endpoints

All endpoints are workspace-scoped. `workspace_id` is extracted from authenticated user's active membership — never from the request.

| Method | Path | Auth | Capability | Rate limit |
|--------|------|------|-----------|------------|
| POST | `/api/v1/work-items/:id/lock` | JWT | None (any member) | 20/min/user |
| DELETE | `/api/v1/work-items/:id/lock` | JWT | None (holder only) | Standard |
| POST | `/api/v1/work-items/:id/lock/heartbeat` | JWT | None (holder only) | Standard |
| POST | `/api/v1/work-items/:id/lock/request-unlock` | JWT | None | 5/hour/user/item |
| POST | `/api/v1/work-items/:id/lock/respond-to-request` | JWT | None (holder only) | Standard |
| POST | `/api/v1/work-items/:id/lock/force-release` | JWT | `force_unlock` | Standard |
| GET | `/api/v1/work-items/:id/lock` | JWT | None | Standard |

Response bodies follow the global API shape: `{ "data": {...}, "message": "..." }` for success, `{ "error": {...} }` for errors.

`respond-to-request` is a new endpoint not in the original proposal. It is required to distinguish holder-initiated release (in response to a request) from a voluntary release, so the notification path is correct.

---

## 6. SSE Events

Channel: `sse:work_item:{work_item_id}` (shared with other EP-12 events for this item)

All events follow the shared SSE frame format from EP-12.

| Event type | Published by | Payload |
|------------|-------------|---------|
| `lock_acquired` | `LockService.acquire` | `{ holder_id, holder_display_name, acquired_at, expires_at }` |
| `lock_released` | `LockService.release` | `{ released_by, released_at, expired: false }` |
| `lock_released` | Celery auto-expire task | `{ former_holder_id, released_at, expired: true, trigger }` |
| `lock_force_released` | `LockService.force_release` | `{ forced_by_id, forced_by_display_name, reason, former_holder_id }` |
| `unlock_requested` | `LockService.request_unlock` | `{ requester_id, requester_display_name, reason, expires_at }` |

SSE subscribers on `sse:work_item:{id}` include: detail page viewers, edit mode holder, list views (via workspace-level channel if implemented). The SSE infrastructure from EP-12 (`RedisPubSub`, `SseHandler`) is used without modification.

---

## 7. Celery Tasks

Location: `app/workers/tasks/lock_tasks.py`

### `notify_unlock_request`

Triggered by `LockService.request_unlock`. Sends EP-08 notification to the lock holder. Payload includes requester name, reason, work item title, direct link.

### `notify_force_unlock`

Triggered by `LockService.force_release`. Sends EP-08 notification to former holder. Payload includes admin name, reason, work item title.

### `auto_release_on_unlock_request_timeout`

Triggered by Redis keyspace notification on `lock_request:work_item:*` key expiry (preferred), or as a periodic Celery beat task running every 30 seconds (fallback if keyspace notifications are not enabled).

For keyspace notification approach:
- Subscribe to `__keyevent@0__:expired` (or the configured DB index)
- Filter for keys matching `lock_request:work_item:*`
- For each match, check if the corresponding `lock:work_item:*` key still exists
- If yes, call `LockService.force_release` with `actor_id=SYSTEM`
- Send `UNLOCK_AUTO_GRANTED` notification to the original requester

Race condition guard: use `SET NX` on a processing key `lock_expire_processing:{work_item_id}` with 30s TTL before processing, to prevent duplicate Celery workers from double-releasing.

### `notify_unlock_denied`

Triggered by `LockService.respond_to_request` when decision is `ignore`. Sends EP-08 notification to requester.

### `notify_unlock_granted`

Triggered by `LockService.respond_to_request` when decision is `release`. Sends EP-08 notification to requester.

---

## 8. Frontend Architecture

### `useWorkItemLock` hook

Location: `src/hooks/useWorkItemLock.ts`

Responsibilities:
- Acquire lock on mount when entering edit mode
- Start heartbeat interval (30s, `setInterval`)
- Clear interval and release lock on unmount (`useEffect` cleanup)
- Handle `403 NOT_LOCK_HOLDER` and `404 LOCK_NOT_FOUND` responses from heartbeat → trigger lock-loss state
- Expose: `{ lock, isHolder, lockLost, lockLostReason, acquireLock, releaseLock }`

### `LockBanner` component

Location: `src/components/locks/LockBanner.tsx`

Rendered on detail page. Subscribes to SSE events for the item. Shows holder info, elapsed time, "Request unlock" button (hidden when `isHolder`). Amber background. Not dismissible.

### `LockBadge` component

Location: `src/components/locks/LockBadge.tsx`

Rendered in list row. Small lock icon + initials (desktop), icon only (mobile). Tooltip with holder name and elapsed time. Tap → `UnlockRequestDialog` on mobile.

### `UnlockRequestDialog` component

Location: `src/components/locks/UnlockRequestDialog.tsx`

Modal. Required reason field (Zod validation: min 1, max 500). Submits `request_unlock`. Closes on success, shows toast.

### `HolderResponsePanel` component

Location: `src/components/locks/HolderResponsePanel.tsx`

Injected into edit mode when `unlock_requested` SSE event received. Shows requester info, reason, countdown. "Release lock" and "Ignore" buttons. Not dismissible by click-outside.

### `ForceReleaseDialog` component (admin)

Location: `src/components/locks/ForceReleaseDialog.tsx`

Modal. Visible only to users with `force_unlock` capability (check via user capabilities in auth context). Required reason (min 10, max 1000). Confirmation checkbox. Calls force-release endpoint.

### Lock-loss recovery UX

When `lockLost === true` in `useWorkItemLock`:
- Transition to view mode
- Show a persistent (non-auto-dismiss) banner: "Your editing session ended. [reason]. Your unsaved changes are below — copy them before refreshing."
- Render a read-only `<textarea>` below the banner containing the serialized unsaved draft (JSON or plain text)
- "Copy to clipboard" button
- Do NOT auto-save, auto-submit, or discard the draft

---

## 9. Redis Availability Policy

| Mode | Behavior | Config |
|------|----------|--------|
| Fail-closed (default) | All writes → 503 if Redis unreachable | `LOCK_FAIL_OPEN=false` |
| Fail-open (emergency) | Writes proceed without lock enforcement | `LOCK_FAIL_OPEN=true` |

Fail-open must be treated as a break-glass procedure. It should be enabled only with explicit admin awareness and logged prominently at startup.

---

## 10. Dependency Graph

```
EP-17 depends on:
  EP-01 — work_items table, workspace_id scoping, FSM TransitionService
  EP-08 — NotificationService, EP-08 notification types
  EP-10 — force_unlock capability, require_capabilities decorator, admin support tools UI
  EP-12 — RedisPubSub, SseHandler, rate limiting middleware, workspace scoping pattern,
           structured logging, correlation ID, security middleware stack
```

EP-17 extends the SSE channel registry in EP-12 with a new channel type:

```python
# infrastructure/sse/channel_registry.py — add:
"work_item_lock": "sse:work_item:{work_item_id}"
```

---

## 11. Key Design Decisions

| Decision | Choice | Rejected alternative | Reason |
|----------|--------|---------------------|--------|
| Lock store | Redis primary, PG audit-only | PG as lock store | Redis TTL is the lock mechanism — PG has no native TTL, requires cron or advisory locks, adds write amplification on every heartbeat |
| Clock authority | Redis TIME command | Application server time | Eliminates clock drift between application servers in multi-node deployment |
| Fail mode | Fail-closed (503) | Fail-open | Last-write-wins data loss is worse than temporary unavailability. Break-glass env var for emergencies. |
| Heartbeat interval | 30s, TTL 5min | Shorter interval | 30s is 1/10 of TTL — 10 missed heartbeats before expiry. Robust to transient network hiccups. |
| Unlock request storage | Redis with TTL | PostgreSQL row | The request is ephemeral. Its TTL IS the auto-release timer. Using PG would require a separate cron to check expiry. |
| SSE channel reuse | Shared `sse:work_item:{id}` | Dedicated lock channel | The detail page already subscribes to this channel. No new subscription needed. |
| Section-level locking | Deferred (not in MVP) | Per-section locks | Adds complexity without proportional value at MVP scale. Work-item-level is sufficient. |
| Lock state in list API | Embedded in list response | Separate lock endpoint per item | N+1 on locks per list row is unacceptable. Embed in the list query with a LEFT JOIN on active locks (via a Redis-backed cache or a PG view of recent acquired events without corresponding released events). |
