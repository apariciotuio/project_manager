# EP-08 Backend Tasks — Teams, Assignments, Notifications & Inbox

Tech stack: Python 3.12+, FastAPI, SQLAlchemy async, PostgreSQL 16+, Celery + Redis

---

## API Contract (interface with frontend)

### Team response
```json
{
  "data": {
    "id": "uuid",
    "workspace_id": "uuid",
    "name": "string",
    "description": "string | null",
    "status": "active | deleted",
    "can_receive_reviews": false,
    "created_at": "iso8601",
    "members": [
      { "user_id": "uuid", "display_name": "string", "role": "member | lead", "joined_at": "iso8601" }
    ]
  }
}
```

### Notification response
```json
{
  "data": {
    "id": "uuid",
    "type": "review.assigned | review.team_assigned | review.responded | item.returned | item.blocked | assignment.changed | ...",
    "state": "unread | read | actioned",
    "actor_id": "uuid | null",
    "subject_type": "work_item | review | block | team",
    "subject_id": "uuid",
    "deeplink": "/items/uuid",
    "quick_action": { "action": "approve", "endpoint": "/api/v1/...", "method": "POST", "payload_schema": {} },
    "extra": {},
    "created_at": "iso8601",
    "read_at": "iso8601 | null",
    "actioned_at": "iso8601 | null"
  }
}
```

### Inbox response
```json
{
  "data": {
    "tiers": {
      "1": { "label": "Pending reviews", "items": [], "count": 0 },
      "2": { "label": "Returned items", "items": [], "count": 0 },
      "3": { "label": "Blocking items", "items": [], "count": 0 },
      "4": { "label": "Decisions needed", "items": [], "count": 0 }
    },
    "total": 0
  }
}
```

### InboxItem shape
```json
{
  "item_id": "uuid",
  "item_type": "string",
  "item_title": "string",
  "owner_id": "uuid",
  "current_state": "string",
  "priority_tier": 1,
  "tier_label": "Pending reviews",
  "event_age": "iso8601",
  "deeplink": "/items/uuid",
  "quick_action": null,
  "source": "direct | team",
  "team_id": "uuid | null"
}
```

### SSE stream event
```
event: notification_created
data: { "id": "uuid", "type": "...", "state": "unread", ... }

event: inbox_count_updated
data: { "total": 5, "by_tier": { "1": 2, "2": 1, "3": 1, "4": 1 } }
```

### Error shapes
- 409: `{ "error": { "code": "LAST_LEAD_REMOVAL", "message": "Cannot remove the last lead from a team" } }`
- 409: `{ "error": { "code": "STALE_ACTION", "message": "Review has already been resolved" } }`

---

## Group A — Teams (US-080)

### Acceptance Criteria — Teams

See also: specs/teams/spec.md (US-080)

**Domain**

WHEN `Team` is constructed with empty `name`
THEN `InvariantError` raised

WHEN `TeamMembership` is constructed
THEN `role` defaults to `member`, `joined_at` set to construction time

**TeamService**

WHEN `create(name, workspace_id, created_by)` and name already exists in workspace
THEN `ConflictError(409, TEAM_NAME_CONFLICT)`; creator is auto-added as lead

WHEN `add_member(team_id, user_id)` with an already-active member
THEN idempotent: no error, no duplicate row (partial unique index `WHERE removed_at IS NULL`)

WHEN `add_member` with a suspended user
THEN `ValidationError(422)` — suspended user cannot receive team assignments

WHEN `remove_member` and target is the last lead
THEN `LastLeadError(409, LAST_LEAD_REMOVAL)`

WHEN `update_role` demoting the last lead
THEN `LastLeadError(409, LAST_LEAD_REMOVAL)`

WHEN `delete(team_id)` and team has open pending reviews
THEN `ConflictError` — cannot delete team with unresolved reviews

**Controllers**

POST /api/v1/teams:
- 201: full team shape with `members: [{ user_id, role='lead', joined_at }]` (creator as lead)
- 409: `TEAM_NAME_CONFLICT`
- 422: empty name

GET /api/v1/teams:
- 200: list of active teams; deleted teams excluded unless `?include_inactive=true`

GET /api/v1/teams/{id}:
- 200: team with full `members` list
- 404: team not found

PATCH /api/v1/teams/{id}:
- 200: updated team
- 403: non-lead, non-admin

DELETE /api/v1/teams/{id}:
- 200: `{ "data": { "status": "deleted" } }`
- 403: non-admin
- 409: team has open pending reviews

POST /api/v1/teams/{id}/members:
- 200: updated member list
- 409: already a member
- 422: suspended user

DELETE /api/v1/teams/{id}/members/{user_id}:
- 200: updated member list
- 409: `LAST_LEAD_REMOVAL`

PATCH /api/v1/teams/{id}/members/{user_id}/role:
- 200: updated member
- 409: `LAST_LEAD_REMOVAL` when demoting last lead

### A1. Domain Layer

- [ ] A1.1 [GREEN] Define `TeamStatus` (`active | deleted`) and `TeamRole` (`member | lead`) enums in `domain/models/team.py`
- [ ] A1.2 [RED] Test `Team` entity: empty name raises `InvariantError`; `status` defaults `active`; `can_receive_reviews` defaults `false`
- [ ] A1.3 [RED] Test `TeamMembership` entity: `role` defaults `member`; `removed_at` nullable; `joined_at` set at construction
- [ ] A1.4 [RED] Test entity invariant: last lead removal rejected by service (not entity — entity is a plain data object, service enforces constraint)
- [ ] A1.5 [GREEN] Implement `Team` and `TeamMembership` entities
- [ ] A1.6 [GREEN] Define `domain/repositories/team_repository.py` interface: `create`, `get`, `list_by_workspace`, `update`, `soft_delete`, `add_member`, `remove_member`, `get_members`, `get_member`

### A2. Migrations & Persistence

- [ ] A2.1 [RED] Write migration test: `teams` table `UNIQUE (workspace_id, name)` rejects duplicate
- [ ] A2.2 [GREEN] Create Alembic migration: `teams` table with `idx_teams_workspace_status`
- [ ] A2.3 [RED] Write migration test: `team_memberships` partial unique index `WHERE removed_at IS NULL` allows re-add after soft remove
- [ ] A2.4 [GREEN] Create Alembic migration: `team_memberships` table with both indexes
- [ ] A2.5 [RED] Write repository tests: `create`, `add_member`, `remove_member` (soft), `get` with members, `list_by_workspace` excludes deleted
- [ ] A2.6 [GREEN] Implement `infrastructure/persistence/team_repository_impl.py` — async SQLAlchemy
  - [x] **Partial (N+1 fix):** `list_active_members_with_users(team_ids)` batch-fetch method added (`backend/app/infrastructure/persistence/team_repository_impl.py:131`, interface in `backend/app/domain/repositories/team_repository.py:44`) — replaces per-team member resolve loop

### A3. Application Service

- [ ] A3.1 [RED] Test `TeamService.create`: name unique per workspace; `created_by` required
- [ ] A3.2 [RED] Test `TeamService.add_member`: active user added; suspended user rejected; already member is idempotent (no error, no duplicate)
- [ ] A3.3 [RED] Test `TeamService.remove_member`: sets `removed_at`; last lead removal → raises `LastLeadError`
- [ ] A3.4 [RED] Test `TeamService.update_role`: demoting last lead → raises `LastLeadError`; promote member to lead → succeeds
- [ ] A3.5 [RED] Test `TeamService.delete`: soft delete (`status=deleted`); team with open pending reviews → raises `ConflictError`
- [ ] A3.6 [GREEN] Publish domain events after each mutation: `TeamMemberAdded`, `TeamMemberRemoved`, `TeamLeadChanged`, `TeamDeleted`
- [ ] A3.7 [GREEN] Implement `application/services/team_service.py`
  - [x] **Partial:** `TeamService.get(team_id, *, workspace_id)` now returns `TeamNotFoundError` for both missing AND cross-workspace (IDOR mitigation, `backend/app/application/services/team_service.py:65`). `TeamService.list_members_for_teams(team_ids)` batch helper exists (`backend/app/application/services/team_service.py:80`)

### A4. Controllers

- [ ] A4.1 [RED] Integration tests: `POST /api/v1/teams` 201; duplicate name → 409; `GET /api/v1/teams` list (workspace-scoped); `GET /api/v1/teams/{id}` with members; `PATCH /api/v1/teams/{id}`; `DELETE /api/v1/teams/{id}`
- [ ] A4.2 [RED] Integration tests: `POST /api/v1/teams/{id}/members`; `DELETE /api/v1/teams/{id}/members/{user_id}`; `PATCH /api/v1/teams/{id}/members/{user_id}/role`; last lead removal → 409
- [ ] A4.3 [GREEN] Implement `presentation/controllers/team_controller.py`
  - [x] **Partial:** list_teams + get_team embed `members` via batch query (`backend/app/presentation/controllers/team_controller.py:124-131, 145-153`); workspace scoping enforced on `get_team`; `NO_WORKSPACE` 401 replacing prior `assert` pattern
- [ ] A4.4 [REFACTOR] Extract input validation to `TeamValidator` — enum allowlist, UUID validation

---

## Group B — Notifications (US-082, US-084)

### Acceptance Criteria — Notifications

See also: specs/notifications/spec.md (US-082, US-084)

**Domain — Notification state FSM**
- `unread → read` allowed
- `unread → actioned` allowed
- `read → actioned` allowed
- `read → unread` rejected
- `actioned → read` rejected
- `actioned → unread` rejected

**Idempotency**
WHEN `bulk_insert_idempotent` is called with a duplicate `idempotency_key`
THEN `INSERT ... ON CONFLICT DO NOTHING` fires; count returns 0 for that row; no error raised

**Fan-out worker**
WHEN team review fan-out task processes a team with N active members
THEN exactly N `INSERT notifications` are issued; suspended members skipped

WHEN Celery task retried after partial success
THEN already-inserted notifications are skipped via `ON CONFLICT DO NOTHING`; no duplicate records

WHEN task fails 3 consecutive times
THEN full payload logged to dead-letter queue; no silent discard

**SSE**
WHEN a user has an active SSE connection (`/api/v1/notifications/stream`)
THEN a `notification_created` event is pushed immediately after each notification INSERT

WHEN the user disconnects
THEN the Redis subscription is cleaned up; no resource leak

WHEN the SSE stream-token endpoint is called
THEN a JWT with 5-minute TTL is returned; the stream endpoint validates this token

**NotificationService**
WHEN `list(recipient_id, page)` is called with a different user's `recipient_id`
THEN `ForbiddenError(403)` — IDOR check is mandatory

WHEN `mark_read(notification_id)` on already-read notification
THEN idempotent: no error, no second DB write

WHEN `mark_all_read(user_id)` is called
THEN only notifications belonging to `user_id` are updated

WHEN `execute_action(notification_id, action)` on a review already resolved
THEN `StaleActionError(409, STALE_ACTION)`; notification transitions to `actioned` with stale flag

**Controllers**

GET /api/v1/notifications:
- 200: paginated list, `state` filter applied; only caller's notifications
- 403: `user_id` != caller (IDOR)

GET /api/v1/notifications/unread-count:
- 200: `{ "data": { "count": N } }`

PATCH /api/v1/notifications/{id}/read:
- 200: updated notification
- 404: notification not found for caller

POST /api/v1/notifications/mark-all-read:
- 200: `{ "data": { "updated_count": N } }`

POST /api/v1/notifications/{id}/action:
- 200: `{ "data": { "result": {...}, "notification": { "state": "actioned" } } }`
- 409: `STALE_ACTION`

GET /api/v1/notifications/stream:
- SSE text/event-stream; requires valid short-lived token
- 401: missing or expired token
- Disconnect: Redis subscription cleaned up

### B1. Domain Layer

- [ ] B1.1 [GREEN] Define `NotificationType` enum (all types from spec: `review.assigned`, `review.team_assigned`, `review.responded`, `item.returned`, `item.blocked`, `item.unblocked`, `assignment.changed`, `team.joined`, `team.left`, `team.lead_assigned`)
- [ ] B1.2 [GREEN] Define `NotificationState` enum: `unread | read | actioned`
- [ ] B1.3 [RED] Test `Notification` entity: state transitions `unread→read` and `unread→actioned` allowed; `read→unread` rejected; `actioned→read` rejected
- [ ] B1.4 [RED] Test idempotency key: `sha256(recipient_id + domain_event_id)` deterministic
- [ ] B1.5 [GREEN] Implement `domain/models/notification.py`
- [ ] B1.6 [GREEN] Define `domain/repositories/notification_repository.py` interface: `bulk_insert_idempotent`, `find_by_recipient`, `unread_count`, `mark_read`, `mark_all_read`, `find_by_id`
  - [x] **Partial:** `INotificationRepository.create` now documents the seed idempotency contract (new key persists; duplicate returns pre-existing row, `backend/app/domain/repositories/notification_repository.py:13-21`). Bulk-insert and other methods still pending.

### B2. Migration & Persistence

- [ ] B2.1 [RED] Write migration test: `notifications` UNIQUE on `idempotency_key`; all indexes present
- [ ] B2.2 [GREEN] Create Alembic migration: `notifications` table
- [ ] B2.3 [RED] Write repository tests: `bulk_insert_idempotent` uses `INSERT ... ON CONFLICT DO NOTHING`; `unread_count` returns correct count; `mark_read` sets `read_at` and transitions state; `mark_all_read` bulk updates
- [ ] B2.4 [GREEN] Implement `infrastructure/persistence/notification_repository_impl.py`

### B3. Fan-out Worker

- [ ] B3.1 [RED] Test fan-out: direct assignment → 1 notification INSERT; team assignment → N inserts (one per active member); suspended user → skipped
- [ ] B3.2 [RED] Test idempotency: Celery task retried → `ON CONFLICT DO NOTHING` prevents duplicate; final state unchanged
- [ ] B3.3 [RED] Test: dead-letter logging on 3 consecutive failures
- [ ] B3.4 [GREEN] Implement `infrastructure/adapters/celery_tasks.py`: `fan_out_notification(event: dict)` task — resolves recipients, bulk inserts, publishes to Redis pub/sub per recipient

### B4. In-Process Event Bus

- [ ] B4.1 [RED] Test: register handler → handler called on `publish`; multiple handlers for same event type → all called; unregistered event type → no error
- [ ] B4.2 [GREEN] Implement `domain/events/bus.py`: `EventBus` with `register(event_type, handler)` and `publish(event)` — synchronous in-process dispatch
- [ ] B4.3 [GREEN] Implement event handlers for each domain event → enqueue Celery fan-out task
- [ ] B4.4 [GREEN] Map all triggering events to handlers (see spec triggering events table)

### B5. SSE Real-Time Delivery

- [ ] B5.1 [RED] Test `sse_publisher.py`: publishes serialized notification payload to Redis channel `notifications:{user_id}` after each INSERT
- [ ] B5.2 [GREEN] Implement `infrastructure/adapters/sse_publisher.py` — Redis pub/sub `PUBLISH`
- [ ] B5.3 [RED] Test SSE endpoint: authenticated connection receives events; disconnect cleans up Redis subscription; short-lived token validated
- [ ] B5.4 [GREEN] Implement `GET /api/v1/notifications/stream` — async generator, subscribes to `notifications:{user_id}`, forwards events
- [ ] B5.5 [GREEN] Implement `POST /api/v1/notifications/stream-token` — issues short-lived JWT (5min TTL) for SSE auth (EventSource cannot set Authorization header)

### B6. NotificationService

- [ ] B6.1 [RED] Test `list`: paginates; `state` filter works; only recipient's notifications returned (IDOR check)
- [ ] B6.2 [RED] Test `mark_read`: sets state=read; already read → idempotent
- [ ] B6.3 [RED] Test `mark_all_read`: bulk update only for requesting user's notifications
- [ ] B6.4 [RED] Test `execute_action`: validates action type; calls `QuickActionDispatcher.dispatch(action_type, subject_id, actor_id)`; transitions notification to `actioned`; review already resolved → raises `StaleActionError(409)` — `NotificationService` must NOT directly depend on `ReviewResponseService`, `WorkItemService`, etc. (Fixed per backend_review.md SD-4)
- [ ] B6.4a [GREEN] Implement `application/services/quick_action_dispatcher.py` — `dispatch(action_type: str, subject_id: UUID, actor_id: UUID) -> dict` maps action types to downstream service calls; `NotificationService` depends only on `QuickActionDispatcher`, not on individual domain services
- [ ] B6.5 [GREEN] Implement `application/services/notification_service.py`

### B7. Controllers

- [ ] B7.1 [RED] Integration tests: `GET /notifications` pagination + state filter; `GET /notifications/unread-count`; `PATCH /notifications/{id}/read`; `POST /notifications/mark-all-read`; `POST /notifications/{id}/action` stale → 409
- [ ] B7.2 [GREEN] Implement `presentation/controllers/notification_controller.py`

---

## Group C — Inbox (US-083)

### Acceptance Criteria — Inbox

See also: specs/inbox/spec.md (US-083)

**InboxService**

WHEN `get_inbox(user_id)` is called
THEN Tier 1: review_requests where `reviewer_id = user` (reviewer_type=user) OR `team_id IN (user active teams)` (reviewer_type=team) AND `status = pending`
AND team reviews resolved by another member via review_responses are excluded from Tier 1
THEN Tier 2: work_items where `owner_id = user` AND `state = 'changes_requested'` (Fixed per backend_review.md ALG-5 — `returned` is not a valid WorkItemState)
THEN Tier 3: review_responses where `responder_id = user` AND `decision = changes_requested` AND linked review_request still `pending` (Fixed per backend_review.md ALG-6 — removed phantom `blocks` table reference; Tier 3 now reflects reviewer's pending-feedback items using existing schema)
THEN Tier 4: work_items where `owner_id = user` AND `state IN ('draft', 'in_clarification')` AND `completeness_score < 50` (Fixed per backend_review.md ALG-6 — removed phantom `decision_owner_id` and `awaiting_decision` state; replaced with needs-attention signal using existing schema)
AND items appearing in multiple tiers are deduplicated: only the lowest (highest-priority) tier keeps it

WHEN user has no team memberships
THEN Tier 1 from team reviews returns empty (empty IN clause handled as no-match, not DB error)

WHEN user has no inbox items
THEN all tiers return `{ items: [], count: 0 }`; `total = 0`

WHEN `get_counts(user_id)` is called
THEN returns per-tier counts and `total` matching the full `get_inbox` result

**Performance**
WHEN inbox query runs against a 500-item dataset
THEN `EXPLAIN ANALYZE` shows index scan (not seq scan) on all four tier queries
AND p99 response time < 300ms

**Controllers**

GET /api/v1/inbox:
- 200: `{ "data": { "tiers": { "1": {...}, "2": {...}, "3": {...}, "4": {...} }, "total": N } }`
- Type filter: `?type=work_item` returns only matching item types across all tiers
- State filter applied; tier counts reflect filter
- Cursor pagination per tier (page size 20)

GET /api/v1/inbox/count:
- 200: `{ "data": { "by_tier": { "1": N, "2": N, "3": N, "4": N }, "total": N } }`

### C0. InboxRepository (must be done before C1)

- [ ] C0.1 [GREEN] Define `domain/repositories/inbox_repository.py` interface: `get_inbox(user_id: UUID, workspace_id: UUID) -> list[InboxItem]`; `get_counts(user_id: UUID, workspace_id: UUID) -> dict[int, int]` (Fixed per backend_review.md LV-3 — SQL must not live in application service)
- [ ] C0.2 [RED] Write repository tests: UNION query returns correct tier labels; Tier 2 uses `state='changes_requested'` not `'returned'`; workspace_id scoping applied to all tiers
- [ ] C0.3 [GREEN] Implement `infrastructure/persistence/inbox_repository_impl.py` — UNION query with all four tiers; de-duplication at SQL level via `ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY tier ASC)`

### C1. InboxService

- [ ] C1.1 [RED] Test `get_inbox`: Tier 1 includes direct + team pending reviews; team-resolved reviews excluded from Tier 1; Tier 2 `changes_requested` items owned by user; Tier 3 reviewer's unresolved change-request items; Tier 4 low-completeness owned items; de-duplication keeps lowest tier (Fixed per backend_review.md ALG-5, ALG-6)
- [ ] C1.2 [RED] Test `get_inbox` edge cases: empty team membership → no team tier 1 items; user with no items → all tiers empty
- [ ] C1.3 [RED] Test `get_counts`: per-tier count correct; `total` correct
- [ ] C1.4 [GREEN] Implement `application/services/inbox_service.py` — calls `InboxRepository.get_inbox()`, handles application-layer de-duplication and pagination; NO SQL in service layer (Fixed per backend_review.md LV-3)

### C2. Performance Validation

- [ ] C2.1 [GREEN] Create additive Alembic migration: inbox-required indexes — `review_requests(reviewer_id, status) WHERE reviewer_id IS NOT NULL AND status='pending'`; `review_requests(team_id, status) WHERE reviewer_type='team' AND status='pending'`; `work_items(owner_id, state, workspace_id) WHERE deleted_at IS NULL`; NOTE: removed phantom indexes on `blocks` and `work_items(decision_owner_id)` — those columns/tables do not exist (Fixed per backend_review.md ALG-6)
- [ ] C2.2 [GREEN] Run `EXPLAIN ANALYZE` on inbox UNION query with 500-item test dataset; verify index scan (not seq scan) for each tier
- [ ] C2.3 [GREEN] Add missing indexes if p99 > 300ms

### C3. Controllers

- [ ] C3.1 [RED] Integration tests: `GET /api/v1/inbox` → tiers shape; `GET /api/v1/inbox/count` → per-tier + total; type filter; state filter; cursor pagination per tier
- [ ] C3.2 [GREEN] Implement `presentation/controllers/inbox_controller.py`

---

## Group D — Assignments (US-081)

### Acceptance Criteria — Assignments

See also: specs/assignments/spec.md (US-081)

**AssignmentService**

WHEN `assign_owner(item_id, user_id, actor_id)` is called with a suspended user
THEN `ValidationError(422)` — suspended users cannot receive assignments

WHEN `assign_owner` with a user not in the workspace
THEN `ValidationError(422)`

WHEN `assign_owner` succeeds
THEN `assignment.changed` event published; both new and previous owner notified

WHEN `suggest_owner` has no matching routing rule
THEN returns `None` — no error, no auto-assignment

WHEN `suggest_reviewer` with suspended/deleted target in rule
THEN that rule is skipped; next matching rule evaluated

WHEN `bulk_assign(item_ids, user_id)` and user is suspended
THEN all items rejected; HTTP 422 (all-or-nothing for suspended target)

WHEN `bulk_assign` with some items failing validation and others succeeding
THEN HTTP 207 with per-item `{ item_id, success: bool, error?: string }` list

**Controllers**

PATCH /api/v1/items/{id}/owner:
- 200: updated work item shape
- 403: caller lacks assignment permission
- 422: suspended target

GET /api/v1/items/{id}/suggested-reviewer:
- 200: `{ "data": { "suggested_reviewer": { "type": "user|team", "id": "uuid" } } }` or `{ "suggested_reviewer": null }`

GET /api/v1/items/{id}/suggested-owner:
- 200: same shape as suggested-reviewer

POST /api/v1/items/bulk-assign:
- 200: all succeeded
- 207: partial success; `{ "data": { "results": [{ "item_id": "...", "success": true/false, "error": "..." }] } }`
- 422: suspended target (all rejected)

### D1. Domain Layer

- [ ] D1.1 [GREEN] Define `RoutingRule` entity: `type` (`item_type | label`), `match_value`, `suggested_team_id | suggested_user_id`, `priority`, `project_id` scope (nullable)
- [ ] D1.2 [GREEN] Define `domain/repositories/routing_rule_repository.py` interface
- [ ] D1.3 [RED] Test routing rule evaluation: type match; label match; priority ordering (lower number = higher priority); suspended/deleted targets skipped; no match → `None`

### D2. Migration & Persistence

- [ ] D2.1 [GREEN] Create Alembic migration: `routing_rules` table
- [ ] D2.2 [RED] Write repository tests: `list_by_workspace` ordered by priority; filter by `project_id`
- [ ] D2.3 [GREEN] Implement `infrastructure/persistence/routing_rule_repository_impl.py`

### D3. AssignmentService

- [ ] D3.1 [RED] Test `assign_owner`: valid user set; suspended user → raises `ValidationError`; not workspace member → raises `ValidationError`; publishes `assignment.changed` event
- [ ] D3.2 [RED] Test `suggest_owner`: routing rule matches by `item_type` → returns first valid; no match → `None`
- [ ] D3.3 [RED] Test `suggest_reviewer`: routing rule matches by `item_type`; matches by label; no match → `None`; suspended/deleted target skipped
- [ ] D3.4 [RED] Test `bulk_assign`: all succeed → 200 with results; any suspended target → rejected, included in error list; partial success (some fail) → 207 with per-item status
- [ ] D3.5 [GREEN] Implement `application/services/assignment_service.py`

### D4. Controllers

- [ ] D4.1 [RED] Integration tests: `PATCH /items/{id}/owner`; `GET /items/{id}/suggested-reviewer`; `GET /items/{id}/suggested-owner`; `POST /items/bulk-assign` partial failure → 207
- [ ] D4.2 [GREEN] Implement `presentation/controllers/assignment_controller.py`

---

## Group E — Cross-Cutting

### E1. Notification Trigger Wiring

- [ ] E1.1 [GREEN] Wire `TeamService` events → fan-out: `TeamMemberAdded`, `TeamMemberRemoved`, `TeamLeadChanged`
- [ ] E1.2 [GREEN] Wire `AssignmentService.assignment.changed` → fan-out
- [ ] E1.3 [GREEN] Wire EP-06 review service events → fan-out: `review.assigned`, `review.team_assigned`, `review.responded`, `item.returned`
- [ ] E1.4 [GREEN] Wire EP-01 block events → fan-out: `item.blocked`, `item.unblocked`
- [ ] E1.5 [RED] Integration test: domain event published → Celery task enqueued → notification record created (end-to-end with real Redis + Celery in test environment)

### E2. Security

- [ ] E2.1 [RED] Test: all team endpoints enforce workspace-scoped access — user from workspace B cannot read/modify workspace A teams → 403
  - [x] **Partial:** `TeamService.get` enforces workspace scoping (cross-workspace read → `TeamNotFoundError` → 404, IDOR-safe) — `backend/app/application/services/team_service.py:65-75`
- [ ] E2.2 [RED] Test: `GET /notifications` — user A cannot read user B's notifications (IDOR check) → 403
- [ ] E2.3 [RED] Test: `GET /inbox` — strictly user-scoped, no cross-user data leakage
- [ ] E2.4 [GREEN] Verify all external inputs validated at controller boundary (enum allowlist, UUID format validation, string length limits)
- [ ] E2.5 [GREEN] Apply rate limiting to `PATCH /notifications/{id}/read` and `POST /notifications/{id}/action` endpoints

### E3. Observability

- [ ] E3.1 [GREEN] Structured log on every notification created: `type`, `recipient_id`, `subject_id`, `idempotency_key`
- [ ] E3.2 [GREEN] Structured log on every quick action executed: `notification_id`, `action_type`, `actor_id`, `result`
- [ ] E3.3 [GREEN] Celery dead-letter queue configured; task failures logged with full payload
- [ ] E3.4 [GREEN] Histogram metric: `notification_fan_out_duration_ms` per `notification_type`

---

## Reconciliation notes (2026-04-17)

**Opportunistic EP-08 slice; full backend still pending.** EP-08 was not formally delivered. Today's pass only touched pieces adjacent to EP-12/EP-10 hardening work. Specifically shipped:

- **`GET /api/v1/workspaces/members`** — workspace member picker endpoint with 500-row hard cap (`backend/app/presentation/controllers/workspace_controller.py:75-120`). Used by frontend pickers that previously required pasting UUIDs. Out of scope for EP-08's plan text (belongs to EP-00/EP-10 member surface) but relevant context for the `?teamless=bool` filter mentioned in the contract above.
- **N+1 fix on team list/get** — `list_active_members_with_users(team_ids)` batch query in repository; `TeamService.list_members_for_teams` helper; controller uses it for both single-team and list endpoints. Addresses a performance regression introduced when the team picker went live.
- **Workspace scoping on `get_team`** — closes an IDOR: cross-workspace reads return `TeamNotFoundError` instead of leaking the team payload.
- **Partial index `idx_team_memberships_team_active`** — migration 0032 (`backend/migrations/versions/0032_team_memberships_idx.py`). Backs the `_resolve_members` query under the N+1 fix.
- **`INotificationRepository.create` idempotency contract** — documented on the interface docstring; existing behaviour, now explicit. Consumed by the seed path; full `bulk_insert_idempotent` is still missing.

Everything else in Groups A/B/C/D/E (full notification fan-out, inbox UNION query, assignment service, routing rules, SSE stream, Celery dead-letter wiring) remains un-ticked and un-shipped. Over half the plan is untouched. When EP-08 goes into formal delivery, re-plan against current schema — the notification/inbox tables may need revisiting.
