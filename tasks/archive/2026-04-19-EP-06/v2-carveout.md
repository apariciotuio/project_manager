# EP-06 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Reviews, Validations & Flow to Ready shipped through Phase 6:
- Backend services: `ReviewRequestService`, `ReviewResponseService`, `ReviewService`, `ReadyGateService`, `ValidationService` in `backend/app/application/services/`
- Backend tests: 57 unit + 26 integration (per `tasks-backend.md` line 398 "**Status: COMPLETED 2026-04-17**")
- Frontend: `review-request-card.tsx`, `review-respond-dialog.tsx`, `validations-checklist.tsx`, `ready-gate-blockers.tsx` in `frontend/components/work-item/` (per `tasks-frontend.md` line 389 "**Status: COMPLETED 2026-04-17**")

## Phase 5 — SSE fan-out of review events

Originally "BLOCKED on EP-08 SSE infra". EP-08 SSE shipped (`SseHandler` + `PgNotificationBus`), so the blocker is gone — but wiring review events (submitted, responded, escalated, expired) into real-time SSE fan-out is **polish on top of the synchronous review flow that already ships**. Consumers see updates today via inbox polling + explicit refetch on the review detail page. TTL and freshness match product expectations.

Re-open when a real-time collaborative-review UX lands (multi-reviewer live status dashboard), or when the inbox polling approach hits latency complaints.

## Phase 7 — Full E2E integration flows

The plan called for end-to-end scenario tests (happy-path, rejection-loop, validator-conflict, idempotency-on-second-approve). Phase 6 already delivers **26 integration tests** exercising the core transitions, plus per-service unit suites. Dedicated multi-actor E2E is deferred — it requires stand-alone Dundun + SSE + notification stubs that only stabilize post-EP-08.

## Phase 8 — Consolidated gates

The `code-reviewer` and `review-before-push` gates have been run **per commit** since 2026-04-17; a single consolidated Phase 8 pass is redundant. The commit history for EP-06 shows review findings addressed inline.

## Minor deferrals

- **N+1 query audit** on review-heavy endpoints — `QueryCounterMiddleware` fires in dev/staging already; no violations observed during Phase 6 integration runs.
- **Error-message consistency** sweep — low-risk cosmetic; no regressions filed.

---

MVP scope (review requests, responses, validations, ready gate, owner reassignment, override justification columns on `work_items`, per-phase integration tests) shipped and in production.
