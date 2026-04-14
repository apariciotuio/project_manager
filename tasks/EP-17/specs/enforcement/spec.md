# Spec: Write Protection Enforcement

## Scope

Server-side enforcement that rejects write API calls with `423 Locked` when the caller is not the current lock holder. Applies to all mutable endpoints on work items, sections, and task nodes.

---

## Enforcement Scenarios

### Scenario 1: Non-holder attempts a write on a locked item

WHEN a user who does not hold the lock calls any write endpoint for a locked work item  
AND the endpoint is one of: `PUT`, `PATCH`, `POST`, or `DELETE` on `/api/v1/work-items/:id`, `/api/v1/work-items/:id/sections/*`, `/api/v1/work-items/:id/task-nodes/*`  
THEN the `require_lock_holder` FastAPI dependency checks Redis key `lock:work_item:{id}`  
AND the current lock holder's `holder_id` does not match the authenticated user's `user_id`  
THEN the dependency raises `HTTPException(status_code=423)` with body:

```json
{
  "error": {
    "code": "LOCKED",
    "message": "This item is currently being edited by another user.",
    "lock": {
      "holder_id": "<uuid>",
      "holder_display_name": "<string>",
      "acquired_at": "<iso>",
      "expires_at": "<iso>"
    }
  }
}
```

AND no write to PostgreSQL occurs  
AND no Celery task is enqueued for this request  
AND no SSE event is published

### Scenario 2: Non-holder attempts a state transition (FSM) on a locked item

WHEN a user who does not hold the lock calls the state transition endpoint (POST `/api/v1/work-items/:id/transitions`)  
THEN `require_lock_holder` is applied before `TransitionService.transition()`  
AND the server responds `423 Locked` (same body as Scenario 1)  
AND the state machine does not advance

### Scenario 3: Lock holder performs a write — allowed

WHEN the authenticated user holds the lock (their `user_id` matches `holder_id` in Redis)  
THEN the `require_lock_holder` dependency passes without raising  
AND the write proceeds normally through the service layer  
AND no extra latency is added beyond the single Redis GET

### Scenario 4: Write attempted when item has no active lock

WHEN a user calls a write endpoint for a work item that has no active lock (Redis key absent)  
THEN the `require_lock_holder` dependency raises `HTTPException(status_code=423)` with body:

```json
{
  "error": {
    "code": "NOT_IN_EDIT_MODE",
    "message": "You must acquire the edit lock before making changes.",
    "lock": null
  }
}
```

AND no write to PostgreSQL occurs  
AND the client handles this case by prompting the user to re-acquire the lock

### Scenario 5: Safe methods bypass lock check entirely

WHEN an authenticated user calls `GET` or `HEAD` on any work item endpoint  
THEN the `require_lock_holder` dependency is NOT applied  
AND the read proceeds without any Redis interaction from the lock system  
AND read performance is unaffected by locking

### Scenario 6: Redis unavailable during write — fail-closed

WHEN Redis is unreachable at the time of a write request  
AND `LOCK_FAIL_OPEN=false` (default)  
THEN `require_lock_holder` raises `HTTPException(status_code=503)` with `{ "error": { "code": "LOCK_STORE_UNAVAILABLE" } }`  
AND no write to PostgreSQL occurs  
AND a `WARNING` log is emitted with `correlation_id` for every blocked request

### Scenario 7: Redis unavailable during write — fail-open emergency mode

WHEN Redis is unreachable  
AND `LOCK_FAIL_OPEN=true` (emergency admin override)  
THEN `require_lock_holder` logs `WARNING lock_fail_open_active` and passes without raising  
AND writes are allowed without lock validation  
AND every such request emits a structured log with `lock_enforcement=bypassed` tag  
AND the startup log warns: "LOCK_FAIL_OPEN is enabled — lock enforcement is disabled"

### Scenario 8: Bulk write operations respect lock per item

WHEN a bulk write endpoint processes multiple work items  
THEN `require_lock_holder` is checked for each `work_item_id` in the batch  
AND any item in the batch that fails the check causes the entire request to return `423 Locked` with a list of which items are locked  
AND no partial writes occur (all-or-nothing within a single request)

### Scenario 9: Lock check does not disclose cross-workspace items

WHEN `require_lock_holder` is checking a `work_item_id` that does not belong to the authenticated user's workspace  
THEN the dependency resolves the work item via workspace-scoped repository (returns None on mismatch)  
AND raises `HTTPException(status_code=404)` — the same as if the item does not exist  
AND never returns `423` for a cross-workspace item (that would disclose its existence)

---

## Implementation Notes

### `require_lock_holder` dependency signature

```python
# app/presentation/dependencies/lock.py

async def require_lock_holder(
    work_item_id: UUID,
    workspace_id: UUID = Depends(get_current_workspace_id),
    current_user: AuthenticatedUser = Depends(get_current_user),
    lock_service: LockService = Depends(get_lock_service),
) -> None:
    """
    FastAPI dependency. Raises 423 if caller is not the lock holder.
    Raises 503 if Redis is unavailable and LOCK_FAIL_OPEN is false.
    Raises 404 if work_item_id does not belong to workspace.
    Must be applied to all write endpoints on work_items, sections, task_nodes.
    """
```

Usage on every mutable endpoint:

```python
@router.patch("/work-items/{work_item_id}")
async def update_work_item(
    work_item_id: UUID,
    body: WorkItemUpdateRequest,
    _: None = Depends(require_lock_holder),
    service: WorkItemService = Depends(get_work_item_service),
):
    ...
```

### Endpoints requiring `require_lock_holder`

| Method | Path pattern | Enforcement |
|--------|-------------|-------------|
| PATCH | `/work-items/:id` | Yes |
| PUT | `/work-items/:id` | Yes |
| DELETE | `/work-items/:id` | Yes |
| POST | `/work-items/:id/transitions` | Yes |
| POST | `/work-items/:id/sections` | Yes |
| PATCH | `/work-items/:id/sections/:sid` | Yes |
| DELETE | `/work-items/:id/sections/:sid` | Yes |
| POST | `/work-items/:id/task-nodes` | Yes |
| PATCH | `/work-items/:id/task-nodes/:nid` | Yes |
| DELETE | `/work-items/:id/task-nodes/:nid` | Yes |
| GET | `/work-items/:id` | No |
| GET | `/work-items/:id/lock` | No |
| POST | `/work-items/:id/lock` | No (this IS the acquire endpoint) |
| DELETE | `/work-items/:id/lock` | No (requires holder check inside LockService, not this dependency) |

### 423 vs 409 disambiguation

- `423 Locked`: item is locked and caller is not the holder. Caller should acquire lock first.
- `409 Conflict`: lock already held when attempting to acquire. Used only on `POST /lock`.
- The client must handle both: `423` → show lock banner; `409` → show "currently editing" UI.
