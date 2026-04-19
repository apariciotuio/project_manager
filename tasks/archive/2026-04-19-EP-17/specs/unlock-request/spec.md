# Spec: Soft Unlock Request (US-172)

## Scope

The soft unlock flow: a non-holder requests that the current lock holder releases the lock, with notification, holder response UI, auto-release on timeout, and requester notification of resolution.

---

## US-172 — Request Unlock (Notifies Current Editor)

### Scenario 1: Non-holder sends unlock request with reason

WHEN a user who does not hold the lock clicks "Request unlock" on the lock banner or badge  
THEN the client renders the `UnlockRequestDialog` with a required "reason" text field (min 1 char, max 500 chars)  
AND after the user enters a reason and confirms  
THEN the client issues `POST /api/v1/work-items/:id/lock/request-unlock` with body `{ "reason": "<text>" }`  
AND the server verifies the requester is NOT the lock holder (holders cannot request unlock of their own lock)  
AND the server stores the unlock request in Redis with key `lock_request:work_item:{id}` → `{ requester_id, requester_display_name, reason, requested_at, expires_at }` with TTL 120 seconds  
AND the server creates a notification for the lock holder via EP-08 notification service with type `UNLOCK_REQUESTED`  
AND the server publishes an `unlock_requested` SSE event on `sse:work_item:{id}` with payload `{ requester_id, requester_display_name, reason, expires_at }`  
AND the server responds `202 Accepted`  
AND the client closes the dialog and shows a toast: "Unlock request sent to Maria Garcia. You'll be notified when she responds."  
AND the "Request unlock" button is disabled until the request resolves

### Scenario 2: Duplicate unlock request while one is already pending

WHEN an unlock request is already pending for a work item  
AND another user (or the same user) attempts to send another request  
THEN the server responds `409 Conflict` with `{ "error": { "code": "UNLOCK_REQUEST_PENDING", "expires_at": "<iso>" } }`  
AND the client shows: "An unlock request is already pending from [Requester]. The lock will auto-release at [time] if not responded to."

### Scenario 3: Lock holder receives unlock request notification — in-app

WHEN the lock holder is on the detail page in edit mode  
AND an `unlock_requested` SSE event arrives on `sse:work_item:{id}`  
THEN the `HolderResponsePanel` is injected into the edit interface: "[Requester Avatar] Juan Lopez is asking to edit this item · Reason: [reason] · Auto-releases in 2:00"  
AND the panel has two primary actions: "Release lock" (primary, destructive) and "Ignore" (secondary)  
AND the countdown ticks down in real time  
AND the panel is not dismissible by clicking outside (requires explicit action)

### Scenario 4: Lock holder releases lock in response to request

WHEN the lock holder clicks "Release lock" in the `HolderResponsePanel`  
THEN the client issues `DELETE /api/v1/work-items/:id/lock`  
AND the server processes the voluntary release (see acquire-release spec Scenario 6)  
AND the server additionally resolves the pending request in Redis (DEL `lock_request:work_item:{id}`)  
AND the server sends a notification to the original requester with type `UNLOCK_GRANTED` via EP-08  
AND the requester receives an SSE event `lock_released` on `sse:work_item:{id}`  
AND if the requester is on the detail page, their lock banner disappears and the "Edit" button re-enables  
AND the requester receives a toast: "Maria Garcia has released the lock. You can now edit."

### Scenario 5: Lock holder ignores the unlock request

WHEN the lock holder clicks "Ignore" in the `HolderResponsePanel`  
THEN the client issues `POST /api/v1/work-items/:id/lock/respond-to-request` with body `{ "decision": "ignore" }`  
AND the server DELetes `lock_request:work_item:{id}` from Redis  
AND the server sends a notification to the requester with type `UNLOCK_DENIED` via EP-08  
AND the `HolderResponsePanel` dismisses  
AND the requester receives a toast: "Maria Garcia is continuing to edit. You can try again later or ask a workspace admin."

### Scenario 6: Auto-release when holder does not respond within 2 minutes

WHEN the unlock request Redis key `lock_request:work_item:{id}` expires (TTL reaches zero — 120 seconds)  
THEN the Celery task `auto_release_on_unlock_request_timeout` is triggered  
AND the task acquires a distributed lock to prevent race conditions with concurrent task executions  
AND the task calls `LockService.force_release` with `actor_id = SYSTEM`, `reason = "auto_release_on_request_timeout"`  
AND the task writes a `auto_expired` event to `work_item_lock_events` with `metadata: { trigger: "unlock_request_timeout", requester_id }`  
AND the task publishes `lock_released` SSE event with `{ expired: true, trigger: "unlock_request_timeout" }`  
AND the server sends a notification to the original requester with type `UNLOCK_AUTO_GRANTED` via EP-08  
AND the former holder's edit session receives the lock-loss recovery banner (see acquire-release spec Scenario 9)

### Scenario 7: Requester navigates away before request resolves

WHEN the requester who sent an unlock request navigates away from the work item detail page  
THEN the pending request remains active in Redis  
AND if the lock is subsequently released, the requester receives an EP-08 notification (persisted, not only SSE)  
AND the notification links directly to the work item  
AND the notification type is `UNLOCK_GRANTED` or `UNLOCK_DENIED` depending on resolution

### Scenario 8: Requester is the lock holder (self-request prevention)

WHEN the lock holder attempts to call `POST /api/v1/work-items/:id/lock/request-unlock`  
THEN the server responds `400 Bad Request` with `{ "error": { "code": "CANNOT_REQUEST_OWN_LOCK" } }`

### Scenario 9: Rate limiting on unlock requests

WHEN a user sends more than 5 unlock request attempts per hour per work item  
THEN the server responds `429 Too Many Requests` with `{ "error": { "code": "RATE_LIMIT_EXCEEDED" }, "Retry-After": <seconds> }`  
AND the "Request unlock" button is disabled client-side until `Retry-After` has elapsed

---

## Non-functional Requirements

- Unlock request TTL: 120 seconds (configurable via `UNLOCK_REQUEST_TTL_SECONDS`).
- Only one pending request per work item at a time (enforced by Redis key uniqueness).
- Rate limit: 5 unlock requests per user per work item per hour (key: `ratelimit:unlock_request:{user_id}:{work_item_id}`).
- Notifications created via EP-08 must be persisted (not SSE-only) so the requester sees them even if offline.
- The `reason` field is required and stored in Redis (not in the audit table — it is ephemeral, not an audit event). The reason IS included in the `work_item_lock_events.metadata` JSONB if auto-release occurs.
- Auto-release Celery task: `lock.tasks.auto_release_on_request_timeout`, scheduled as a periodic task checking every 30 seconds, or triggered by Redis keyspace notifications if configured (prefer keyspace notifications to avoid polling).
