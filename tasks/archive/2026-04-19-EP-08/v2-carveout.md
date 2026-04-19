# EP-08 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Core teams, assignments, notifications, and inbox shipped:
- Backend: `TeamService`, `AssignmentService` + `assignment_controller.py` (bulk-assign, suggested-owner, suggested-reviewer), `ExtendedNotificationService`, inbox UNION query, `InboxRepositoryImpl`, `InboxService` (cache-aside wired in EP-12 follow-up commit b0bca06)
- Frontend: `tasks-frontend.md` line 528 "**Status: COMPLETED 2026-04-17**"

## Refactor / polish (low priority)

- **A4.4 — `TeamValidator` extraction** (`tasks-backend.md` line 198): enum allowlist + UUID validation currently inline in `TeamService`. Extract when a second consumer appears (matches the EP-12 `require_capabilities` per-epic adoption pattern).
- **A3.6 / E1.1 / E1.4 — Domain events + fan-out wiring for team and block mutations** (`tasks-backend.md` lines 190, 477, 480): `TeamService` emits no domain events today; block events are not wired. Consumer-first: add when the first real consumer needs them.

## Test-harness gaps (integration)

- **A2.1 / A2.3 / A2.5 — Repo + migration integration tests** (`tasks-backend.md` lines 176, 178, 180): unit tests cover behavior; dedicated migration/repo integration tests are nice-to-have but not blocking.
- **C0.2 — Inbox repository integration test** (`tasks-backend.md` line 376): C3.1 end-to-end already exercises the UNION + tier labels via real DB.
- **E1.5 — End-to-end domain-event → notification test** (`tasks-backend.md` line 481): depends on A3.6 event emission landing first.

## Celery-removal redesign (same pattern as EP-04/EP-07)

- **B3.3 — Dead-letter logging on 3 consecutive failures** (`tasks-backend.md` line 298): Celery was ripped out; inline fan-out logs errors but no DLQ mechanism. Re-design with PG-native retry/back-off if volume demands it.
- **E3.3 — DLQ on fan-out** (`tasks-backend.md` line 495): same as above.
- **B5.3 — SSE notifications endpoint** (`tasks-backend.md` line 312): `job_progress_controller.py` is a separate SSE channel; the `/notifications/stream` variant needs the same `SseHandler` wiring. Add when the UI consumer demands real-time push (today polls via inbox refresh).

## Observability (EP-12 CI-gate carveout pattern)

- **C2.1 — Inbox index migration** (`tasks-backend.md` line 388): candidate indexes listed (`review_requests(reviewer_id, status)`, `work_items(owner_id, state, workspace_id)`); add once EXPLAIN ANALYZE shows seq-scan pain at production volume.
- **C2.2 / C2.3 — EXPLAIN ANALYZE on inbox UNION + add missing indexes if p99 > 300ms** (`tasks-backend.md` lines 389, 390).
- **E3.4 — `notification_fan_out_duration_ms` histogram** (`tasks-backend.md` line 496): matches EP-12 observability (stdlib logging + correlation_id is the whole obs story per decision #27).

## Security / hardening (low risk)

- **B1.4 — Deterministic sha256 idempotency key** (`tasks-backend.md` line 283): current path uses `str(uuid4())` or caller-provided; functional replay protection works; sha256 is a hardening step.
- **E2.5 — Rate limiting on notification mutation endpoints** (`tasks-backend.md` line 489): `PgRateLimiter` covers global limits; per-endpoint tuning is an ops task.

## Frontend polish (56 items)

All 56 FE unchecked items are under the COMPLETED status line at 528 — they are sub-tasks of shipped phases. Cosmetic drift in the checklist, not in the product.

---

MVP scope (teams CRUD + soft-remove memberships, AssignmentService with bulk + suggested picks, notifications persistence + listing + fan-out, inbox with tier labels + cache) shipped and in production.
