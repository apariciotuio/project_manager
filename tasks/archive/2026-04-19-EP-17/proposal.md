# EP-17 — Edit Locking + Collaboration Control

## Business Need

The product is explicitly asynchronous (see PRD section 7.6 — "la colaboración es asíncrona"). But async collaboration doesn't mean concurrent editing on the same content. Without coordination: ⚠️ originally MVP-scoped — see decisions_pending.md
- User A opens item X, starts editing
- User B opens item X, starts editing
- Both save — last-write-wins silently destroys A's work (or B's, depending on order)

The PRD emphasizes "control humano en todo momento" and "ownership claro". Edit locking makes this explicit: while someone edits, others see the lock and can't overwrite. They can:
- Wait
- Request unlock (soft — notifies current editor)
- Ask an admin to force unlock (hard — audit trail)

## Objectives

- Acquire edit lock on a work item when a user enters edit mode
- Display lock indicator ("Maria is editing") to other users with a badge/banner
- Prevent save operations by non-lock-holders (server-side enforcement)
- Lock expires automatically after inactivity (e.g., 5 minutes no activity)
- Allow unlock request: sends notification to current lock holder
- Allow admin (superadmin or workspace admin) to force unlock with audit
- Optional: section-level locks (edit one section, not the whole item) — deferred ⚠️ originally MVP-scoped — see decisions_pending.md

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-170 | Acquire edit lock when entering edit mode | Must |
| US-171 | See lock indicator when another user is editing | Must |
| US-172 | Request unlock (notifies current editor) | Must |
| US-173 | Release lock when leaving edit mode or after inactivity | Must |
| US-174 | Admin force-unlock with audit trail | Must |
| US-175 | Heartbeat to extend lock during active editing | Must |

## Acceptance Criteria

- WHEN a user clicks "Edit" on a work item THEN system attempts to acquire lock
- WHEN lock is free THEN user enters edit mode, lock is held for 5 min (extendable via heartbeat)
- WHEN lock is held by another user THEN user sees "Maria is currently editing (started 2 min ago)" — edit button disabled
- WHEN a non-lock-holder attempts a write API call on a locked item THEN server rejects with 423 Locked
- WHEN the user with lock has no activity for 5 min (no heartbeat) THEN lock auto-releases
- WHEN a user clicks "Request unlock" THEN current lock holder receives notification with explanation field
- WHEN lock holder receives unlock request AND releases OR does not respond in 2 min THEN lock auto-releases
- WHEN admin clicks "Force unlock" THEN dialog requires reason, lock is released, audit event recorded, former holder notified
- AND heartbeat runs every 30s while edit mode is active (extends lock TTL)
- AND the lock is visible in list view as a small indicator (not just on detail page)

## Technical Notes

- **New table**: `work_item_locks`: work_item_id (PK), holder_user_id, acquired_at, expires_at, last_heartbeat_at, requested_by_user_id (for unlock requests), requested_at, request_reason
- **Alternative**: Redis for lock state (TTL, fast, pub-sub) with DB fallback for persistence. **Recommend**: Redis primary (lock key with TTL), DB audit only when forced. Redis key: `lock:work_item:{id}` → `{holder_id, acquired_at, expires_at}`. TTL 5 min, extended on heartbeat.
- **Server enforcement**: middleware or service guard on all write endpoints for work_items, sections, task_nodes — if lock exists and holder != current_user: 423 Locked
- **Client**: enter edit mode triggers `POST /api/v1/work-items/:id/lock`. Exit mode triggers `DELETE`. Heartbeat every 30s via `POST /:id/lock/heartbeat`
- **Stale-lock detection**: heartbeat-based. No heartbeat for 2× interval = expired, auto-release
- **Unlock request flow**:
  - `POST /:id/lock/request-unlock` (body: reason) → notifies holder via EP-08 notification + SSE
  - Holder sees banner "Juan is asking to edit (reason: ...)". Can click "Release" or dismiss. Auto-release after 2 min if no action.
- **Force unlock**: `POST /:id/lock/force-release` — requires `capability: force_unlock` (workspace admin or superadmin) — audit event with reason
- **Real-time**: SSE broadcasts lock state changes to subscribers of that work item (shared SSE infra from EP-12)
- **Admin unlock UI**: supportive — in admin support tools (EP-10)

## API Endpoints

- `POST /api/v1/work-items/:id/lock` — acquire
- `DELETE /api/v1/work-items/:id/lock` — release (by holder)
- `POST /api/v1/work-items/:id/lock/heartbeat` — extend TTL
- `POST /api/v1/work-items/:id/lock/request-unlock` — soft request
- `POST /api/v1/work-items/:id/lock/force-release` — admin hard release
- `GET /api/v1/work-items/:id/lock` — current lock status

## Dependencies

- EP-01 (work items)
- EP-08 (notifications, SSE)
- EP-10 (admin capabilities — `force_unlock`, admin support tools)
- EP-12 (security middleware, rate limiting, shared SSE)

## Complexity Assessment

**Medium-High** — Distributed locking is tricky, but Redis TTL + heartbeat is well-understood. Main complexity is UX (clear lock indicators, smooth acquire/release, handling lock loss gracefully).

## Risks

- Network flakiness: user loses lock mid-edit due to missed heartbeats — needs graceful client recovery ("your lock expired, please refresh")
- Redis outage: decide fail-open (allow edits, risk conflicts) vs fail-closed (block edits, safe) — **recommend fail-closed with manual admin override**
- UX frustration if locks aren't released cleanly
- Attack: DoS by holding locks — mitigated by force-unlock + rate limit on acquire

## Open Questions

- Section-level locking (allow parallel edits to different sections)? **Decision: work-item level only** ⚠️ originally MVP-scoped — see decisions_pending.md
- Should lock apply to comments too? **Decision: no — comments are append-only, no lock needed** ⚠️ originally MVP-scoped — see decisions_pending.md
- Should lock apply to state transitions? **Decision: yes — state transition is a write** ⚠️ originally MVP-scoped — see decisions_pending.md
