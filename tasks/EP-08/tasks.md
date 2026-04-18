# EP-08 — Implementation Tasks

## Status: IN PROGRESS (2026-04-18) — 44/93 items shipped (audit + guards). Remaining: Inbox full (Group C), AssignmentService, SSE /notifications/stream, QuickActionDispatcher, TeamService unit tests. See `tasks-backend.md`.

Dependencies: EP-00 (auth, JWT sessions), EP-01 (work_items), EP-06 (review_requests, review_responses)

---

## Group A — Teams (US-080)

### A1. Domain layer

- [ ] Define `TeamStatus` and `TeamRole` enums in `domain/models/team.py`
- [ ] Define `Team` entity with invariants: name required, status defaults active, created_by required
- [ ] Define `TeamMembership` entity with invariants: role defaults member, removed_at nullable
- [ ] Define `ITeamRepository` interface in `domain/repositories/team_repository.py`
- [ ] [TDD] Write failing tests for Team entity invariants (empty name, duplicate member, last lead removal)

### A2. Infrastructure — persistence

- [ ] [TDD RED] Write failing repository tests: create team, add member, remove member, get with members
- [ ] Write SQLAlchemy ORM models for `teams` and `team_memberships`
- [ ] Create Alembic migration: `teams`, `team_memberships` tables with indexes (see design.md schema)
- [ ] Implement `TeamRepository` (SQLAlchemy async)
- [ ] [TDD GREEN] Pass repository tests

### A3. Application service

- [ ] [TDD RED] Write failing service tests: create team, add member, remove last lead rejection, delete team with open reviews
- [ ] Implement `TeamService`: create, update, delete, add_member, remove_member, update_role
- [ ] Implement suspended-user guard in add_member
- [ ] Implement last-lead guard in remove_member and role demotion
- [ ] Publish domain events: `TeamMemberAdded`, `TeamMemberRemoved`, `TeamLeadChanged`, `TeamDeleted`
- [ ] [TDD GREEN] Pass service tests

### A4. API layer

- [ ] [TDD RED] Write failing integration tests for all team endpoints (auth, RBAC, 409/422/403 cases)
- [ ] Implement `TeamController` with all endpoints (POST, GET list, GET detail, PATCH, DELETE, member endpoints)
- [ ] Wire Pydantic request/response schemas
- [ ] [TDD GREEN] Pass integration tests
- [ ] [REFACTOR] Extract input validation to dedicated validators

---

## Group B — Notifications (US-082, US-084)

### B1. Domain layer

- [ ] Define `NotificationType`, `NotificationState` enums
- [ ] Define `Notification` entity with idempotency key, deeplink, quick_action (optional JSONB)
- [ ] Define `INotificationRepository` interface
- [ ] [TDD] Write failing tests for Notification entity: state transitions (unread→read→actioned), idempotency key generation

### B2. Infrastructure — persistence

- [ ] [TDD RED] Write failing repository tests: bulk insert, get by recipient, unread count, mark read
- [ ] Write SQLAlchemy ORM model for `notifications`
- [ ] Create Alembic migration: `notifications` table with indexes (see design.md schema)
- [ ] Implement `NotificationRepository` (SQLAlchemy async)
- [ ] [TDD GREEN] Pass repository tests

### B3. Fan-out worker

- [ ] [TDD RED] Write failing tests for fan-out task: correct recipients for direct vs team assignment, idempotency on retry, skip suspended users
- [ ] Implement `fan_out_notification` Celery task in `infrastructure/adapters/celery_tasks.py`
- [ ] Implement recipient resolution: direct user vs team member lookup
- [ ] Implement suspended-user skip logic
- [ ] Implement idempotency: `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING`
- [ ] [TDD GREEN] Pass fan-out tests

### B4. In-process event bus + event handlers

- [ ] Implement simple event bus (dict of event_type → list of handlers) in `domain/events/bus.py`
- [ ] Implement event handlers for each domain event → enqueue Celery fan-out task
- [ ] Map all triggering events (see spec) to corresponding handlers
- [ ] [TDD] Write tests for handler registration and dispatch

### B5. SSE real-time delivery

- [ ] Implement Redis pub/sub publisher in `infrastructure/adapters/sse_publisher.py` — publishes after each notification INSERT
- [ ] Implement SSE stream endpoint `GET /api/v1/notifications/stream` with async generator
- [ ] Implement short-lived stream token endpoint `POST /api/v1/notifications/stream-token` (SSE auth workaround)
- [ ] [TDD] Write tests for SSE endpoint: connection, event push, disconnection cleanup

### B6. Application service

- [ ] [TDD RED] Write failing service tests: get notifications, mark read, mark all read, execute quick action, stale action rejection
- [ ] Implement `NotificationService`: list, unread_count, mark_read, mark_all_read, execute_action
- [ ] Implement quick action execution: validate action type, call downstream service, transition notification to actioned
- [ ] Implement stale action guard (review already resolved → 409)
- [ ] [TDD GREEN] Pass service tests

### B7. API layer

- [ ] [TDD RED] Write failing integration tests for notification endpoints
- [ ] Implement `NotificationController` with all endpoints
- [ ] [TDD GREEN] Pass integration tests

---

## Group C — Inbox (US-083)

### C1. Inbox aggregation query

- [ ] [TDD RED] Write failing tests for inbox query: correct tier assignment, de-duplication across tiers, empty team membership handling, team-resolved review exclusion
- [ ] Implement `InboxService.get_inbox(user_id)` using UNION query (see design.md)
- [ ] Implement de-duplication logic (item in multiple tiers → keep lowest tier)
- [ ] Implement `InboxService.get_counts(user_id)` for badge endpoint
- [ ] [TDD GREEN] Pass inbox service tests

### C2. Performance validation

- [ ] EXPLAIN ANALYZE inbox UNION query with test dataset (500 items, 10 teams)
- [ ] Verify all required indexes exist (see design.md index list)
- [ ] Add missing indexes if p99 > 300ms target not met

### C3. API layer

- [ ] [TDD RED] Write failing integration tests for inbox endpoints: tiers, pagination, type filter, count endpoint
- [ ] Implement `InboxController`: GET /api/v1/inbox (grouped, paginated), GET /api/v1/inbox/count
- [ ] Implement cursor-based pagination per tier
- [ ] Implement type and state filters
- [ ] [TDD GREEN] Pass integration tests

---

## Group D — Assignments (US-081)

### D1. Routing rules domain

- [ ] Define `RoutingRule` entity: type (item_type | label), match_value, suggested_team_id or suggested_user_id, priority, project_id scope
- [ ] Define `IRoutingRuleRepository` interface
- [ ] [TDD] Write failing tests for routing rule evaluation: type match, label match, priority ordering, skip suspended targets

### D2. Infrastructure — persistence

- [ ] [TDD RED] Write failing repository tests for routing rules
- [ ] Write SQLAlchemy ORM model for `routing_rules`
- [ ] Create Alembic migration: `routing_rules` table
- [ ] Implement `RoutingRuleRepository`
- [ ] [TDD GREEN] Pass tests

### D3. Application service

- [ ] [TDD RED] Write failing service tests: assign owner (success, suspended rejection, 403), suggest owner, suggest reviewer (type match, label match, no match), bulk assign (success, suspended rejects all)
- [ ] Implement `AssignmentService`: assign_owner, assign_reviewer, suggest_owner, suggest_reviewer, bulk_assign
- [ ] Implement routing rule evaluator: priority order, skip suspended/deleted targets, return first valid match
- [ ] Publish `assignment.changed` domain event on owner change
- [ ] [TDD GREEN] Pass service tests

### D4. API layer

- [ ] [TDD RED] Write failing integration tests for assignment endpoints
- [ ] Implement assignment endpoints: PATCH owner, POST review (with reviewer), GET suggestions, POST bulk-assign
- [ ] [TDD GREEN] Pass integration tests

---

## Group E — Cross-cutting

### E1. Notification triggers wiring

- [ ] Wire `TeamService` events to notification fan-out (team.joined, team.left, team.lead_assigned)
- [ ] Wire `AssignmentService` events to notification fan-out (assignment.changed)
- [ ] Wire review service events (EP-01) to notification fan-out (review.assigned, review.team_assigned, review.responded, item.returned, item.blocked, item.unblocked)
- [ ] [TDD] Integration test: end-to-end from domain event to notification record creation

### E2. Security review

- [ ] Authorization: verify all team endpoints enforce workspace-scoped access
- [ ] Authorization: verify notification endpoints are strictly user-scoped (no IDOR — user A cannot read user B's notifications)
- [ ] Authorization: verify inbox is strictly user-scoped
- [ ] Input validation: all external inputs validated at controller boundary (allowlist on enums, UUIDs validated)
- [ ] Rate limiting: mark read and quick action endpoints

### E3. Observability

- [ ] Structured log on every notification created: type, recipient_id, subject_id, idempotency_key
- [ ] Structured log on every quick action executed: notification_id, action_type, actor_id, result
- [ ] Celery task failure logging to dead-letter queue with full payload
- [ ] Metric: notification fan-out task duration histogram

### E4. Final review gates

- [ ] Run `code-reviewer` agent
- [ ] Run `review-before-push` workflow
- [ ] All tests passing, lint clean, types checked
