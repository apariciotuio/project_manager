# Spec: Admin Force Unlock (US-174)

## Scope

Hard unlock by a user with `force_unlock` capability. Irreversible. Requires explicit reason. Full audit trail. Former holder is notified.

---

## US-174 — Admin Force Unlock with Audit Trail

### Scenario 1: Admin successfully force-unlocks a locked item

WHEN a user with the `force_unlock` capability navigates to a locked work item (detail page or admin support tools from EP-10)  
THEN the "Force unlock" action is visible and enabled (hidden from users without `force_unlock` capability)  
AND the user clicks "Force unlock"  
THEN the `ForceReleaseDialog` opens with:
  - A read-only summary of the current lock: holder name, acquired time, elapsed duration
  - A required "Reason" textarea (min 10 chars, max 1000 chars)
  - A confirmation checkbox: "I understand this will immediately end [Holder]'s edit session"
  - "Force unlock" button (disabled until reason and checkbox are filled)  
AND the user fills the reason and checks the confirmation  
THEN the client issues `POST /api/v1/work-items/:id/lock/force-release` with body `{ "reason": "<text>" }`  
AND the server validates the caller has `force_unlock` capability via `require_capabilities(["force_unlock"])`  
AND the server DELetes the Redis key `lock:work_item:{id}`  
AND the server also DELetes any pending unlock request `lock_request:work_item:{id}` if present  
AND the server writes a `force_released` event to `work_item_lock_events` with `actor_id = admin_user_id`, `reason = <text>`, `metadata: { former_holder_id, former_holder_display_name, lock_acquired_at, lock_expires_at }`  
AND the server publishes `lock_force_released` SSE event on `sse:work_item:{id}` with payload `{ forced_by_id, forced_by_display_name, reason, former_holder_id }`  
AND the server sends a notification to the former holder via EP-08 with type `LOCK_FORCE_RELEASED`, including admin's name and reason  
AND the server responds `200 OK` with `{ "event_id": "<uuid>", "released_at": "<iso>" }`  
AND the client closes the dialog and shows a success toast: "Lock released successfully."

### Scenario 2: Admin attempts force unlock without `force_unlock` capability

WHEN a user without the `force_unlock` capability calls `POST /api/v1/work-items/:id/lock/force-release`  
THEN the server responds `403 Forbidden` with `{ "error": { "code": "FORBIDDEN", "missing": ["force_unlock"] } }`  
AND no Redis key is modified  
AND no audit event is written  
AND the "Force unlock" button is not rendered in the UI for this user

### Scenario 3: Force unlock on an item with no active lock

WHEN an admin calls force-release on a work item that has no active lock  
THEN the server responds `404 Not Found` with `{ "error": { "code": "LOCK_NOT_FOUND" } }`  
AND no audit event is written

### Scenario 4: Former holder is in edit mode when force-released

WHEN a force release occurs  
AND the former holder has an active edit session (connected to SSE)  
THEN the former holder's client receives the `lock_force_released` SSE event  
AND the client immediately transitions to view mode  
AND the lock-loss recovery banner is shown: "An admin has released your edit lock. Reason: [reason]. Your unsaved changes are preserved below — copy them before refreshing."  
AND the client does NOT auto-discard unsaved changes  
AND the heartbeat interval is stopped immediately

### Scenario 5: Force unlock audit event is complete and immutable

WHEN a `force_released` event is written to `work_item_lock_events`  
THEN it contains: `id`, `work_item_id`, `event_type = force_released`, `actor_id` (admin), `reason` (verbatim), `metadata` (former holder info, lock timestamps), `created_at` (using DB server time, not client time)  
AND the event is never updated or deleted (append-only audit table)  
AND the event is queryable via admin support tools (EP-10) filtered by `work_item_id` or `actor_id`

### Scenario 6: Force unlock action is not accessible via the "Request unlock" flow

WHEN a user with `force_unlock` capability uses the soft unlock request flow  
THEN the force unlock action remains a separate, distinct UI element  
AND calling the force-release endpoint does not require a prior unlock request  
AND the soft request and force unlock are independent pathways with independent audit trails

### Scenario 7: Former holder is notified even if offline

WHEN the former holder is not connected at the time of force release  
THEN the EP-08 notification is persisted in the notifications table  
AND the notification is delivered when the holder next connects  
AND the notification includes: admin display name, reason, work item title, timestamp

### Scenario 8: Redis unavailable during force unlock

WHEN Redis is unreachable at the time of a force-unlock request  
THEN the server responds `503 Service Unavailable` with `{ "error": { "code": "LOCK_STORE_UNAVAILABLE" } }`  
AND no audit event is written (to ensure audit and Redis state remain consistent)  
AND no notification is sent (idempotency: the lock was not confirmed released)

---

## Non-functional Requirements

- `force_unlock` capability is defined in EP-10 capability registry. It is assignable to workspace admin and superadmin roles.
- Reason field: required, min 10 characters, max 1000 characters. Stripped of leading/trailing whitespace before storage.
- Force release audit events must NOT be deletable via any API endpoint — the table has no DELETE path.
- The `ForceReleaseDialog` must include a confirmation checkbox to prevent accidental clicks. The "Force unlock" button is disabled until both reason (valid) and checkbox are checked.
- Rate limit: no specific rate limit beyond the standard 300 req/min per user. Force unlock is an admin action with inherent friction.
- Observability: emit a structured log at `WARNING` level on every force release: `lock_force_released work_item_id={} by admin_id={} former_holder_id={}`.
