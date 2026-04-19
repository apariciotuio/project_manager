# Spec: Acquire, Release & Heartbeat (US-170, US-173, US-175)

## Scope

Covers the full lifecycle of an edit lock: acquisition when entering edit mode, TTL extension via heartbeat, voluntary release on exit, and automatic expiry on inactivity.

---

## US-170 — Acquire Edit Lock

### Scenario 1: Successful acquisition on a free item

WHEN an authenticated user clicks "Edit" on a work item that has no active lock  
THEN the system issues `POST /api/v1/work-items/:id/lock`  
AND the server executes SET NX on Redis key `lock:work_item:{id}` with TTL 300 seconds  
AND the Redis value stores `{ holder_id, acquired_at, expires_at, last_heartbeat_at }` using Redis server time (TIME command) — not client time  
AND the server writes a `acquired` event to `work_item_lock_events`  
AND the server publishes a `lock_acquired` event on SSE channel `sse:work_item:{id}` with payload `{ holder_id, holder_display_name, acquired_at, expires_at }`  
AND the server responds `201 Created` with the lock object  
AND the client enters edit mode and starts a heartbeat interval of 30 seconds

### Scenario 2: Acquisition fails — item already locked by another user

WHEN an authenticated user clicks "Edit" on a work item locked by another user  
THEN the system issues `POST /api/v1/work-items/:id/lock`  
AND the server's SET NX returns nil (key already exists)  
AND the server responds `409 Conflict` with body `{ "error": { "code": "LOCK_HELD", "holder": { "id", "display_name", "avatar_url" }, "acquired_at", "expires_at" } }`  
AND the client does NOT enter edit mode  
AND the client renders the lock indicator (see lock-display spec)  
AND the "Edit" button remains disabled for this user

### Scenario 3: Acquisition fails — item already locked by the same user (different session)

WHEN an authenticated user attempts to acquire a lock already held by their own user_id  
THEN the server responds `409 Conflict` with `{ "error": { "code": "LOCK_HELD_BY_SELF", ... } }`  
AND the client shows a prompt: "You are editing this item in another window. Continue here? (releases the other session)"  
AND if the user confirms, the client calls `DELETE /api/v1/work-items/:id/lock` to release then re-acquires  
AND if the user cancels, the client navigates to view mode

### Scenario 4: Acquisition attempted on non-existent or out-of-scope work item

WHEN a user attempts to acquire a lock on a work item that does not exist in their workspace  
THEN the server responds `404 Not Found`  
AND no Redis key is written  
AND no audit event is emitted

### Scenario 5: Lock acquisition rate limit exceeded

WHEN a user issues more than 20 lock acquisition requests per minute  
THEN the server responds `429 Too Many Requests` with `Retry-After` header  
AND no lock is created

---

## US-173 — Release Lock

### Scenario 6: Voluntary release by lock holder

WHEN the lock holder exits edit mode (navigates away, clicks Cancel, or closes the tab/window)  
THEN the client issues `DELETE /api/v1/work-items/:id/lock`  
AND the server verifies the requester is the current lock holder  
AND the server DELetes the Redis key  
AND the server writes a `released` event to `work_item_lock_events`  
AND the server publishes a `lock_released` event on SSE channel `sse:work_item:{id}` with payload `{ released_by, released_at }`  
AND the server responds `204 No Content`  
AND the client clears the heartbeat interval

### Scenario 7: Release attempt by non-holder

WHEN a user who does not hold the lock calls `DELETE /api/v1/work-items/:id/lock`  
THEN the server responds `403 Forbidden` with `{ "error": { "code": "NOT_LOCK_HOLDER" } }`  
AND the Redis key is not modified  
AND no audit event is emitted

### Scenario 8: Release on item with no active lock

WHEN a user calls `DELETE /api/v1/work-items/:id/lock` and no lock exists  
THEN the server responds `404 Not Found` with `{ "error": { "code": "LOCK_NOT_FOUND" } }`

### Scenario 9: Automatic release on TTL expiry (no heartbeat)

WHEN a lock's TTL in Redis reaches zero (no heartbeat received for 5 minutes)  
THEN Redis automatically deletes the key (native TTL expiry)  
AND a Celery task `expire_lock_events` polls for locks that disappeared from Redis but have no corresponding `released` or `auto_expired` event  
AND the Celery task writes an `auto_expired` event to `work_item_lock_events` with `actor_id = NULL`  
AND the Celery task publishes a `lock_released` event on SSE channel `sse:work_item:{id}` with payload `{ expired: true, former_holder_id }`  
AND the former holder's client — if still connected — receives the SSE event and shows: "Your editing session expired due to inactivity. Your unsaved changes are preserved below — copy them before refreshing."  
AND the client transitions to view mode  
AND the client does NOT auto-discard unsaved changes

---

## US-175 — Heartbeat

### Scenario 10: Successful heartbeat extends TTL

WHEN the lock holder's client sends `POST /api/v1/work-items/:id/lock/heartbeat` (every 30 seconds while edit mode is active)  
THEN the server verifies the requester is the current lock holder  
AND the server updates `last_heartbeat_at` in the Redis JSON value  
AND the server resets the Redis TTL to 300 seconds from now (using Redis server time)  
AND the server responds `200 OK` with updated `{ expires_at, last_heartbeat_at }`  
AND no audit event is written (heartbeats are high-frequency; audit is for state changes only)

### Scenario 11: Heartbeat by non-holder is rejected

WHEN a user who does not hold the lock sends a heartbeat request  
THEN the server responds `403 Forbidden` with `{ "error": { "code": "NOT_LOCK_HOLDER" } }`  
AND the Redis TTL is not modified

### Scenario 12: Heartbeat on expired or non-existent lock

WHEN a client sends a heartbeat and the Redis key no longer exists (expired between heartbeats)  
THEN the server responds `404 Not Found` with `{ "error": { "code": "LOCK_NOT_FOUND" } }`  
AND the client receives this response, stops the heartbeat interval  
AND the client shows the lock-loss recovery banner (see Scenario 9)

### Scenario 13: Heartbeat while Redis is unavailable

WHEN a heartbeat request arrives and Redis is unreachable  
THEN the server responds `503 Service Unavailable` with `{ "error": { "code": "LOCK_STORE_UNAVAILABLE" } }`  
AND the client shows: "Connection issue — your lock may expire soon. Save your work."  
AND the client continues attempting heartbeats on the 30-second interval

---

## Non-functional Requirements

- TTL: 300 seconds (5 minutes). Configurable via env var `LOCK_TTL_SECONDS`.
- Heartbeat interval: 30 seconds. Configurable via `LOCK_HEARTBEAT_INTERVAL_SECONDS`.
- Clock authority: Redis server TIME command. Client timestamps are never trusted.
- Redis unavailability: fail-closed by default. All write operations return 503. Admin can set `LOCK_FAIL_OPEN=true` env var for emergency override (logs a WARNING on every request while active).
- Lock acquisition rate limit: 20/minute per user (shared RateLimitMiddleware, key `ratelimit:lock_acquire:{user_id}`).
- All endpoints require JWT authentication and workspace scoping via `get_current_workspace_id` dependency.
- `work_item_id` must belong to the authenticated user's `active_workspace_id`; respond 404 otherwise (do not disclose cross-workspace existence).
