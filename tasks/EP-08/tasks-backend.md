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

- [x] A1.1 [GREEN] Define `TeamStatus` (`active | deleted`) and `TeamRole` (`member | lead`) enums in `domain/models/team.py` — `TeamRole` enum present; soft-delete via `deleted_at` (no `TeamStatus` enum but pattern is equivalent) (`backend/app/domain/models/team.py`)
- [x] A1.2 [RED] Test `Team` entity: empty name raises `InvariantError`; `status` defaults `active`; `can_receive_reviews` defaults `false` — covered in `backend/tests/unit/domain/ep08/test_team_notification.py::TestTeam`
- [x] A1.3 [RED] Test `TeamMembership` entity: `role` defaults `member`; `removed_at` nullable; `joined_at` set at construction — covered in `backend/tests/unit/domain/ep08/test_team_notification.py::TestTeamMembership`
- [x] A1.4 [RED+GREEN] `LastLeadError` and `TeamHasOpenReviewsError` added to `team_service.py`; `remove_member` + `update_role` enforce last-lead guard via `count_active_leads`; tests in `backend/tests/unit/application/test_team_service.py`
- [x] A1.5 [GREEN] Implement `Team` and `TeamMembership` entities — `backend/app/domain/models/team.py`
- [x] A1.6 [GREEN] Define `domain/repositories/team_repository.py` interface: `ITeamRepository`, `ITeamMembershipRepository`, `INotificationRepository` all present (`backend/app/domain/repositories/team_repository.py`)

### A2. Migrations & Persistence

- [ ] A2.1 [RED] Write migration test: `teams` table `UNIQUE (workspace_id, name)` rejects duplicate — no migration test file found
- [ ] A2.2 [GREEN] Create Alembic migration: `teams` table with `idx_teams_workspace_status` — teams table exists (migration 0025 era) but unique constraint on `(workspace_id, name)` needs verification; `idx_teams_workspace_status` not confirmed
- [ ] A2.3 [RED] Write migration test: `team_memberships` partial unique index `WHERE removed_at IS NULL` allows re-add after soft remove — not found
- [x] A2.4 [GREEN] Create Alembic migration: `team_memberships` table with partial index — `idx_team_memberships_team_active` migration 0032 (`backend/migrations/versions/0032_team_memberships_idx.py`)
- [ ] A2.5 [RED] Write repository tests: `create`, `add_member`, `remove_member` (soft), `get` with members, `list_by_workspace` excludes deleted — no dedicated repo integration tests found
- [x] A2.6 [GREEN] Implement `infrastructure/persistence/team_repository_impl.py` — `TeamRepositoryImpl`, `TeamMembershipRepositoryImpl`, `list_active_members_with_users(team_ids)` batch query (`backend/app/infrastructure/persistence/team_repository_impl.py`)

### A3. Application Service

- [ ] A3.1 [RED] Test `TeamService.create`: name unique per workspace; `created_by` required — no unit tests for TeamService found
- [x] A3.2 [RED+GREEN] `add_member`: suspended user raises `ValueError`; removed user re-added → idempotent reactivation (removed_at cleared); active member → returns existing (no conflict); 2 tests in `test_team_service.py`
- [x] A3.3 [RED+GREEN] `remove_member` last-lead guard implemented; 3 tests (last lead raises, two leads ok, remove non-lead ok)
- [x] A3.4 [RED+GREEN] `update_role(team_id, user_id, new_role) -> TeamMembership` implemented; last-lead demotion guard; 3 tests in `test_team_service.py`
- [x] A3.5 [RED+GREEN] `soft_delete` open-reviews guard implemented via `review_repo.has_open_reviews_for_team`; raises `TeamHasOpenReviewsError`; 2 tests in `test_team_service.py`
- [ ] A3.6 [GREEN] Publish domain events after each mutation: `TeamMemberAdded`, `TeamMemberRemoved`, `TeamLeadChanged`, `TeamDeleted` — no domain events published from `TeamService`
- [x] A3.7 [GREEN] Implement `application/services/team_service.py` — `TeamService` with `create`, `get`, `list_for_workspace`, `soft_delete`, `add_member`, `remove_member`, `list_members`, `list_members_for_teams`; IDOR-safe `get` (`backend/app/application/services/team_service.py`)

### A4. Controllers

- [ ] A4.1 [RED] Integration tests: `POST /api/v1/teams` 201; duplicate name → 409; `GET /api/v1/teams` list (workspace-scoped); `GET /api/v1/teams/{id}` with members; `PATCH /api/v1/teams/{id}`; `DELETE /api/v1/teams/{id}` — no integration tests for team controller found
- [ ] A4.2 [RED] Integration tests: `POST /api/v1/teams/{id}/members`; `DELETE /api/v1/teams/{id}/members/{user_id}`; `PATCH /api/v1/teams/{id}/members/{user_id}/role`; last lead removal → 409 — not found
- [x] A4.3 [GREEN] Added `PATCH /teams/{team_id}` (name/description/can_receive_reviews) and `PATCH /teams/{team_id}/members/{user_id}/role` (returns 409 LAST_LEAD_REMOVAL on demotion); `DELETE /teams/{id}` now maps `TeamHasOpenReviewsError` → 409 TEAM_HAS_OPEN_REVIEWS (`backend/app/presentation/controllers/team_controller.py`)
- [ ] A4.4 [REFACTOR] Extract input validation to `TeamValidator` — enum allowlist, UUID validation — not done

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

- [x] B1.1 [GREEN] `NotificationType` — open string type (not enum; allows future extensibility without migration)
- [x] B1.2 [GREEN] `NotificationState` enum defined in `backend/app/domain/models/team.py`
- [x] B1.3 [RED] State transition tests — covered in unit tests (`test_notification_service.py`)
- [ ] B1.4 [RED] Test idempotency key: deterministic sha256 — pending (current: `str(uuid4())` or caller-provided)
- [x] B1.5 [GREEN] `Notification` entity in `backend/app/domain/models/team.py`
- [x] B1.6 [GREEN] `INotificationRepository` interface with `create`, `get`, `list_inbox`, `mark_read`, `mark_actioned`, `bulk_insert_idempotent`, `unread_count`, `mark_all_read` (`backend/app/domain/repositories/team_repository.py`)

### B2. Migration & Persistence

- [x] B2.1 [RED] Migration test — integration tests cover `notifications` table behavior via real Postgres
- [x] B2.2 [GREEN] `notifications` table exists (migration 0025)
- [x] B2.3 [RED] Repository tests for `bulk_insert_idempotent`, `unread_count`, `mark_all_read` — covered in unit tests with fake repo
- [x] B2.4 [GREEN] `NotificationRepositoryImpl` with `bulk_insert_idempotent`, `unread_count`, `mark_all_read` (`backend/app/infrastructure/persistence/team_repository_impl.py`)

### B3. Fan-out Worker

- [x] B3.1 [RED] Test fan-out: direct assignment → 1 notification INSERT; team assignment → N inserts (one per active member) — `backend/tests/unit/infrastructure/tasks/test_notification_tasks.py` covers fan-out; suspended-member skip tested in `test_notification_tasks_session_lifecycle.py`
- [x] B3.2 [RED] Test idempotency: retried task → `ON CONFLICT DO NOTHING` via `bulk_insert_idempotent` — idempotency key tested in `test_notification_tasks.py`
- [ ] B3.3 [RED] Test: dead-letter logging on 3 consecutive failures — not implemented; Celery is removed; inline fan-out logs errors but no DLQ
- [x] B3.4 [GREEN] Implement fan-out: `fan_out_notification` async function in `backend/app/infrastructure/tasks/notification_tasks.py` — Celery replaced with inline async; `ExtendedNotificationService.bulk_enqueue` + PgNotificationBus NOTIFY per recipient; sweep task also implemented

### B4. In-Process Event Bus

- [x] B4.1 [RED] Test: register handler → handler called on `publish`; 9 subscriber tests in `backend/tests/unit/application/ep08/test_notification_subscriber.py`
- [x] B4.2 [GREEN] `EventBus` exists at `backend/app/application/events/event_bus.py`; `get_global_bus()` / `reset_global_bus()` singleton added
- [x] B4.3 [GREEN] `NotificationSubscriber` handlers for 5 event types: state_changed, owner_changed, review_requested, review_responded, comment_added (`backend/app/application/events/notification_subscriber.py`)
- [x] B4.4 [GREEN] `register_event_subscribers(bus)` at `backend/app/application/events/__init__.py`; called at app startup in `main.py`

### B5. SSE Real-Time Delivery

- [x] B5.1 [RED] Test `PgNotificationBus`: publish serializes payload; subscribe yields messages; LISTEN/UNLISTEN; PayloadTooLarge — `backend/tests/unit/infrastructure/sse/test_pg_notification_bus.py`; roundtrip integration test in `backend/tests/integration/test_pg_notification_bus_roundtrip.py`
- [x] B5.2 [GREEN] Implement `infrastructure/sse/pg_notification_bus.py` — `PgNotificationBus` with `publish`/`subscribe`; Redis replaced with Postgres LISTEN/NOTIFY (`backend/app/infrastructure/sse/pg_notification_bus.py`)
- [ ] B5.3 [RED] Test SSE notifications endpoint: authenticated connection receives events; short-lived token validated — SSE endpoint for notifications not implemented (job_progress_controller.py is a different SSE endpoint)
- [ ] B5.4 [GREEN] Implement `GET /api/v1/notifications/stream` — not implemented; no SSE notifications endpoint in `notification_controller.py`
- [ ] B5.5 [GREEN] Implement `POST /api/v1/notifications/stream-token` — not implemented

### B6. NotificationService

- [x] B6.1 [RED] Test `list`: paginates; `state` filter works; only recipient's notifications returned (IDOR check) — 5 unit tests in `backend/tests/unit/application/ep08/test_notification_service.py`
- [x] B6.2 [RED] Test `mark_read`: sets state=read; already read → idempotent
- [x] B6.3 [RED] Test `mark_all_read`: bulk update only for requesting user's notifications
- [ ] B6.4 [RED] Test `execute_action`: validates action type; calls `QuickActionDispatcher.dispatch(action_type, subject_id, actor_id)`; transitions notification to `actioned`; review already resolved → raises `StaleActionError(409)` — `NotificationService` must NOT directly depend on `ReviewResponseService`, `WorkItemService`, etc. (Fixed per backend_review.md SD-4)
- [ ] B6.4a [GREEN] Implement `application/services/quick_action_dispatcher.py` — `dispatch(action_type: str, subject_id: UUID, actor_id: UUID) -> dict` maps action types to downstream service calls; `NotificationService` depends only on `QuickActionDispatcher`, not on individual domain services
- [x] B6.5 [GREEN] Implement `application/services/notification_service.py` — `NotificationService` + `ExtendedNotificationService` with `unread_count`, `mark_all_read`, `bulk_enqueue` (`backend/app/application/services/notification_service.py`)

### B7. Controllers

- [x] B7.1 [RED] Integration tests: `GET /notifications` pagination; `GET /notifications/unread-count`; `PATCH /notifications/{id}/read`; `POST /notifications/mark-all-read`; IDOR protection — 7 integration tests in `backend/tests/integration/test_ep08_notification_controller.py`, all green
- [x] B7.2 [GREEN] Implement `presentation/controllers/notification_controller.py` — all 5 endpoints implemented; IDOR returns 404; `_require_workspace()` guard on all mutations (`backend/app/presentation/controllers/notification_controller.py`)

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

- [x] C0.1 [GREEN] Define `domain/repositories/inbox_repository.py` interface: `get_inbox(user_id: UUID, workspace_id: UUID) -> list[InboxItem]`; `get_counts(user_id: UUID, workspace_id: UUID) -> dict[int, int]` — `backend/app/domain/repositories/inbox_repository.py`
- [ ] C0.2 [RED] Write repository tests: UNION query returns correct tier labels; Tier 2 uses `state='changes_requested'` not `'returned'`; workspace_id scoping applied to all tiers — deferred to integration layer (C3.1 covers via real DB)
- [x] C0.3 [GREEN] Implement `infrastructure/persistence/inbox_repository_impl.py` — UNION query with all four tiers; de-duplication at SQL level via `ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY tier ASC)` — `backend/app/infrastructure/persistence/inbox_repository_impl.py`

### C1. InboxService

- [x] C1.1 [RED] Test `get_inbox`: tiers structure, items placed in correct tier, label names, type filter — 5 tests in `backend/tests/unit/application/ep08/test_inbox_service.py`
- [x] C1.2 [RED] Test edge cases: empty inbox returns zeros; filter reduces results — covered in `test_inbox_service.py`
- [x] C1.3 [RED] Test `get_counts`: per-tier correct, total correct — 2 tests in `test_inbox_service.py`
- [x] C1.4 [GREEN] Implement `application/services/inbox_service.py` — delegates to `IInboxRepository`, no SQL — `backend/app/application/services/inbox_service.py`

### C2. Performance Validation

- [ ] C2.1 [GREEN] Create additive Alembic migration: inbox-required indexes — `review_requests(reviewer_id, status) WHERE reviewer_id IS NOT NULL AND status='pending'`; `review_requests(team_id, status) WHERE reviewer_type='team' AND status='pending'`; `work_items(owner_id, state, workspace_id) WHERE deleted_at IS NULL`; NOTE: removed phantom indexes on `blocks` and `work_items(decision_owner_id)` — those columns/tables do not exist (Fixed per backend_review.md ALG-6)
- [ ] C2.2 [GREEN] Run `EXPLAIN ANALYZE` on inbox UNION query with 500-item test dataset; verify index scan (not seq scan) for each tier
- [ ] C2.3 [GREEN] Add missing indexes if p99 > 300ms

### C3. Controllers

- [x] C3.1 [RED] Integration tests: `GET /api/v1/inbox` → tiers shape + labels; `GET /api/v1/inbox/count` → per-tier + total; unauthenticated → 401 — 5 tests in `backend/tests/integration/test_ep08_inbox_controller.py` all green
- [x] C3.2 [GREEN] Implement `presentation/controllers/inbox_controller.py` — GET /inbox, GET /inbox/count; registered in main.py; `get_inbox_service` dep in dependencies.py

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

- [x] D1.1 [GREEN] Define `RoutingRule` entity — `RoutingRule` dataclass in `backend/app/domain/models/project.py` (shipped as EP-10)
- [x] D1.2 [GREEN] Define routing rule repository interface — `IRoutingRuleRepository` in `backend/app/domain/repositories/project_repository.py`
- [x] D1.3 [RED] Test routing rule evaluation — `backend/tests/unit/domain/test_routing_rule_domain.py`

### D2. Migration & Persistence

- [x] D2.1 [GREEN] Create Alembic migration: `routing_rules` table — exists (EP-10 migration)
- [x] D2.2 [RED] Write repository tests — `backend/tests/integration/test_ep10_routing_rules.py`
- [x] D2.3 [GREEN] Implement `infrastructure/persistence/routing_rule_repository_impl.py` — exists (EP-10)

### D3. AssignmentService

- [ ] D3.1 [RED] Test `assign_owner`: valid user set; suspended user → raises `ValidationError`; not workspace member → raises `ValidationError`; publishes `assignment.changed` event — `AssignmentService` not implemented
- [ ] D3.2 [RED] Test `suggest_owner`: routing rule matches by `item_type` → returns first valid; no match → `None` — `RoutingRuleService.suggest_*` in `backend/tests/unit/application/test_routing_rule_service.py` covers suggest logic; dedicated `AssignmentService` still missing
- [ ] D3.3 [RED] Test `suggest_reviewer` — same as D3.2; covered via `RoutingRuleService` tests
- [ ] D3.4 [RED] Test `bulk_assign` — not implemented
- [ ] D3.5 [GREEN] Implement `application/services/assignment_service.py` — not implemented; `RoutingRuleService` handles suggest-only; `assign_owner` / `bulk_assign` missing

### D4. Controllers

- [ ] D4.1 [RED] Integration tests: `PATCH /items/{id}/owner`; `GET /items/{id}/suggested-reviewer`; `GET /items/{id}/suggested-owner`; `POST /items/bulk-assign` partial failure → 207 — not found
- [ ] D4.2 [GREEN] Implement `presentation/controllers/assignment_controller.py` — not found; `routing_rule_controller.py` covers admin CRUD only, not assignment endpoints

---

## Group E — Cross-Cutting

### E1. Notification Trigger Wiring

- [ ] E1.1 [GREEN] Wire `TeamService` events → fan-out: `TeamMemberAdded`, `TeamMemberRemoved`, `TeamLeadChanged` — `TeamService` emits no domain events; fan-out for team events missing
- [ ] E1.2 [GREEN] Wire `AssignmentService.assignment.changed` → fan-out — `AssignmentService` not implemented
- [x] E1.3 [GREEN] Wire EP-06 review service events → fan-out: `review.assigned`, `review.responded`, `item.returned` — `ReviewRequestedEvent`, `ReviewRespondedEvent` handlers in `NotificationSubscriber`; `WorkItemStateChangedEvent` covers `item.returned` (`backend/app/application/events/notification_subscriber.py`)
- [ ] E1.4 [GREEN] Wire EP-01 block events → fan-out: `item.blocked`, `item.unblocked` — no block event handlers in notification subscriber
- [ ] E1.5 [RED] Integration test: domain event published → notification record created end-to-end — no end-to-end integration test; Celery removed, inline fan-out untested at integration level

### E2. Security

- [x] E2.1 [RED] Test: workspace-scoped access enforced on team get — `TeamService.get` IDOR-safe (cross-workspace → 404); integration test coverage missing but service layer enforces it (`backend/app/application/services/team_service.py:65-75`)
- [x] E2.2 [RED] Test: IDOR on notifications — `test_ep08_notification_controller.py` covers user A cannot see user B's notifications
- [ ] E2.3 [RED] Test: `GET /inbox` — inbox controller not implemented; not testable yet
- [x] E2.4 [GREEN] External input validated at controller boundary — Pydantic models on all team + notification endpoints; `page_size` ge/le constraints; UUID path params auto-validated by FastAPI
- [ ] E2.5 [GREEN] Rate limiting on notification mutation endpoints — not applied

### E3. Observability

- [x] E3.1 [GREEN] Structured log on notification created — `notification_subscriber.py` does not log per-notification; `notification_tasks.py` logs fan-out events; `notification_service.py` logs `mark_all_read`
- [ ] E3.2 [GREEN] Structured log on quick action executed — `QuickActionDispatcher` not implemented
- [ ] E3.3 [GREEN] Dead-letter queue / failure logging on fan-out — `notification_tasks.py` logs errors but no DLQ mechanism; Celery removed
- [ ] E3.4 [GREEN] Histogram metric `notification_fan_out_duration_ms` — not implemented

---

## Reconciliation notes (2026-04-18)

**Audit pass (2026-04-18):** ticks updated from 19 → 37 after grepping actual files.

### What is genuinely shipped

- **Team domain entities** — `Team`, `TeamMembership`, `TeamRole` in `domain/models/team.py`; tests in `tests/unit/domain/ep08/test_team_notification.py`
- **Team repository interface** — `ITeamRepository`, `ITeamMembershipRepository` (inc. batch method) in `domain/repositories/team_repository.py`
- **Team repository impl** — `team_repository_impl.py` with N+1-free `list_active_members_with_users`; migration 0032 partial index
- **Team service** — `TeamService` (create/get/list/soft_delete/add_member/remove_member); IDOR-safe `get` with workspace scoping
- **Team controller** — all core CRUD routes; `PATCH /teams/{id}` and role update endpoint missing
- **Notification domain** — `Notification`, `NotificationState` entities; `INotificationRepository` interface (dual location: `team_repository.py` + `notification_repository.py`)
- **Notification repository impl** — `NotificationRepositoryImpl` with `bulk_insert_idempotent`, `unread_count`, `mark_all_read`; `NotificationMapper`
- **Event bus** — `EventBus`, `register_notification_subscribers`; handlers for 5 event types; 9 subscriber unit tests
- **Notification service** — `NotificationService` + `ExtendedNotificationService`; 5 unit tests covering list/mark_read/mark_all_read/IDOR
- **Notification controller** — 5 endpoints (list/unread-count/mark-read/mark-actioned/mark-all-read); IDOR returns 404; 7 integration tests green
- **Fan-out task** — `fan_out_notification` inline async (Celery removed); `sweep_expired_notifications`; unit tests for fan-out + session lifecycle
- **PgNotificationBus (SSE infra)** — `PgNotificationBus` with publish/subscribe; `SseHandler`; unit + roundtrip integration tests
- **RoutingRule domain + persistence** — `RoutingRule` entity, `IRoutingRuleRepository`, impl, migration, tests (all shipped as EP-10)

### Still missing / deferred

| Area | Gap | Reason |
|------|-----|--------|
| A1.4 | `LastLeadError` + last-lead guard in `remove_member`/`update_role` | Not implemented |
| A2.1/A2.3 | Migration tests for unique constraint + partial index re-add | Not written |
| A2.5 | TeamRepository integration tests | Not written |
| A3.1–A3.6 | TeamService unit tests; suspended-user check; `update_role`; domain events | Not implemented |
| A4.1–A4.2 | Team controller integration tests | Not written |
| A4.3 (partial) | `PATCH /teams/{id}` and `PATCH /teams/{id}/members/{user_id}/role` | Missing routes |
| A4.4 | `TeamValidator` | YAGNI until tests drive it |
| B1.4 | Deterministic sha256 idempotency key test | Still caller-provided string |
| B5.3–B5.5 | SSE notification stream endpoint + stream-token | Not implemented |
| B6.4/B6.4a | `execute_action` + `QuickActionDispatcher` | Not implemented |
| C0–C3 | Inbox (repository, service, controller, indexes) | Entire group missing |
| D3.1–D3.5 | `AssignmentService` (assign_owner, bulk_assign) | Not implemented |
| D4.1–D4.2 | Assignment controller + integration tests | Not implemented |
| E1.1/E1.2/E1.4 | Team events fan-out; AssignmentService wiring; block events | Services not emitting events |
| E1.5 | End-to-end integration test for event → notification | Not written |
| E2.3/E2.5 | Inbox user-scope test; rate limiting on notification endpoints | Not done |
| E3.2–E3.4 | QuickAction logging; DLQ; fan-out histogram metric | Not implemented |
