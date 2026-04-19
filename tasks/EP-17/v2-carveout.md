# EP-17 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Edit Locking & Collaboration Control shipped:
- Migration `0119_lock_unlock_requests.py`
- Domain models: `section_lock.py`, `lock_unlock_request.py`
- Repositories: `lock_repository_impl.py`, `lock_unlock_request_repository_impl.py` + mappers
- Controller: `lock_controller.py` (11 endpoints: acquire, release, extend, list, list-by-work-item, acquire-force, request-unlock, list-unlock-requests, grant, deny, cancel)
- Frontend: lock dialogs + list badges + lock-loss banner + G3/G5/G6/G7 shipped (`tasks-frontend.md` line 195 "**Status: COMPLETED — core shipped 2026-04-19**"); 57+ lock-related tests green

## Audit logging (consumer-first deferral)

- **`LockEventRepository` + audit table population on lock events** — the lock surface emits no dedicated audit rows today. General-purpose `AuditService` already captures state transitions; lock-specific audit adds granularity for admin investigation. Add when an admin-ops consumer lands (matches the EP-08 per-epic adoption pattern for domain events).

## FE polish (already documented as v2 in EP-12 closeout)

- **G11 axe-core audit on lock dialogs** — matches the EP-12/EP-19 axe-core CI-gate carveout.
- **G10 full draft capture** — core draft capture shipped; edge cases (e.g., pasted HTML, attachments mid-draft) deferred.

---

MVP scope (section-level locking with TTL, explicit release, extend, force-acquire, unlock-request workflow with grant/deny/cancel, lock-loss banner, badge surfacing on list + detail, WorkItemCard integration, FE dialogs) shipped and in production.
