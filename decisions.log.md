# Decisions Log

Record of user decisions that overrode an agent concern. See `CLAUDE.md` §"Decision Logging Protocol".

---

## Decision Record

**Date:** 2026-04-15
**User:** @David
**Context:** M0 bootstrap — user instructed to remove Redis (replaced by Postgres) and remove MinIO (deferred to EP-16).

### Agent Concern
Celery with a Postgres broker (`sqla+postgresql://`) is functional but slower and less battle-tested than Redis under bursty workloads. At the stated scale (<100 users, <50 workspaces) the performance gap is not a blocker, but several downstream needs previously planned on Redis (dashboard cache TTL, SSE state, rate limit counters, OAuth state single-use) now need Postgres-native replacements (in-process LRU+TTL, LISTEN/NOTIFY, pg-backed tables). Source-of-truth docs (`assumptions.md`, `progress.md`, `tech_info.md`) currently state Redis — they drift until re-aligned. The real broker wiring is not exercised until M2 (EP-03 Dundun async), so the decision is effectively deferred: `CELERY_TASK_ALWAYS_EAGER=true` is the default in M0 and M2 confirms the broker choice then.

### User Decision
Remove Redis from the stack entirely — Postgres handles every stateful concern. Drop MinIO from M0; plan object storage at EP-16 when attachments land.

### Risk Level
Medium — Celery + Postgres broker has known scaling ceilings. At the project's target scale it is fine. If scale assumptions change, the broker choice must be revisited at M2 before production rollout.

---

## Decision Record

**Date:** 2026-04-15
**User:** @David
**Context:** EP-00 post-review hardening — refresh token rotation deferred.

### Agent Concern
`AuthService.refresh_token` reuses the same raw refresh token on every call. A stolen refresh cookie is usable for the full 30-day TTL without detection. Industry baseline (OAuth 2.0 BCP, draft-ietf-oauth-security-topics) is to rotate refresh tokens on every use and invalidate the prior token; reuse of an already-rotated token is then a clear signal of theft and should revoke the entire session family. Current implementation has no such detection.

### User Decision
Defer refresh rotation to EP-10 (session management / device trust). At EP-00 scope, refresh tokens are stored as SHA-256 hashes and carry a 30-day absolute expiry; theft window exists but is accepted for the current scale and threat model.

### Risk Level
Medium — a compromised refresh cookie grants 30-day persistent access until the user logs out or the token expires. No automated detection of reuse. Must be revisited before opening the platform to external users.

---

## Decision Record

**Date:** 2026-04-16
**User:** @David
**Context:** EP-03 Phase 8 security review — proceeding through remaining epics without first closing the workspace-RLS gap on the 3 new EP-03 tables.

### Agent Concern
Migrations 0014/0015/0016 (`conversation_threads`, `assistant_suggestions`, `gap_findings`) do not follow the workspace RLS pattern used by 0009 (`work_items`, `state_transitions`, `ownership_history`). As a result, `workspace_id` is not stored on those tables and the `app.current_workspace` session variable does not filter them. Within-workspace IDOR is possible if a user can guess (or harvest) a UUID for a resource in another workspace. On a VPN-only deployment with <100 users and random UUIDs, exploitation is impractical — but the house pattern must hold, and the fix is mechanical (≈2-3 h): migration 0017 + ORM/mapper/repo updates + two-tenant integration tests. Additionally, `_UpstreamWS.send` in the WS proxy silently drops client→upstream frames because `asend()` on a plain async generator discards the sent value.

### User Decision
Proceed through EP-04 .. EP-19 implementation instead of pausing to close the Phase 8 Must-Fix items. Document them in `tasks/EP-03/phase_8_security_findings.md` and revisit as a dedicated ticket after the full epic sweep. User is explicitly signing off on "do all epics, I'll review and modify later."

### Risk Level
Medium — VPN-only + random UUIDs make active exploitation unlikely, but the RLS gap is a structural divergence from the rest of the schema and must be closed before any external exposure. WS client→upstream direction is currently a no-op (test already skips the bidirectional case, so no one is relying on it yet).

---

## Decision Record

**Date:** 2026-04-18
**User:** @David
**Context:** EP-12 reintroduced Redis (rate limiter, SSE pub/sub, CacheService) against the 2026-04-15 decision "remove Redis entirely". User flagged mid-session; Redis-out re-affirmed.

### Agent Concern
Reintroducing Redis violated a prior explicit decision. I (Fermi) did not push back when EP-12 design brought Redis back and even built a new CacheService on top (Agent I). Postgres-only replacements have known limits (8KB NOTIFY payload, per-connection listener, rate-limit contention under burst) but are acceptable at target scale (<100 users).

### User Decision
Rip Redis out. Plan-task in flight (`tasks/redis-removal/plan.md`). Delete CacheService + redis_cache_adapter + redis_pubsub. Replace with PG LISTEN/NOTIFY bus, PG rate-limit buckets table, PG job_progress table.

### Risk Level
Medium — PG LISTEN/NOTIFY strains beyond ~100 concurrent SSE subscribers. Revisit at M2. Wasted work: rate limiter (commit f0fa6d1), SseHandler, job progress controller, CacheService. Accepted cost.

---
