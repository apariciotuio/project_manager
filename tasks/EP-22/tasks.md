# EP-22 — Chat-first Capture Flow — Task Index

> Epic proposal: `proposal.md` (closed). Decisions #1–#5 are closed — no re-negotiation.
> Design: `design.md`. Specs: `specs/*/spec.md`.

## Artifact Checklist

| Artifact | Path | Status |
|---|---|---|
| Proposal | `tasks/EP-22/proposal.md` | [x] Closed |
| Spec — Post-create landing (US-220) | `specs/post-create-landing/spec.md` | [x] Drafted |
| Spec — Chat prime (US-221) | `specs/chat-prime/spec.md` | [x] Drafted |
| Spec — Type preview (US-222) | `specs/type-preview/spec.md` | [x] Drafted |
| Spec — Suggestion bridge (US-223 + US-224) | `specs/suggestion-bridge/spec.md` | [x] Drafted |
| Spec — SplitView scope (US-225) | `specs/splitview-scope/spec.md` | [x] Drafted |
| Design | `design.md` | [x] Drafted |
| Backend tasks | `tasks-backend.md` | [x] Drafted |
| Frontend tasks | `tasks-frontend.md` | [x] Drafted |

## Story Coverage Matrix

| User Story | Spec | Backend Phase | Frontend Phase |
|---|---|---|---|
| US-220 — Land on SplitView | post-create-landing | n/a (FE wiring only) | Phase 7 |
| US-221 — Primer message | chat-prime | Phase 2, 5 | Phase 8 (verification) |
| US-222 — Editable type preview | type-preview | n/a (EP-04 endpoints unchanged) | Phase 7 (right-panel wiring) |
| US-223 — Suggestions flow into preview | suggestion-bridge | Phase 1.2, 4 | Phase 1, 2, 4, 5 |
| US-224 — Preview edits flow to Dundun | suggestion-bridge | Phase 3 | Phase 3 |
| US-225 — SplitView in all states, tab removed | splitview-scope | n/a | Phase 6, 7 |

## Execution Phases (Summary)

| Phase | Owner | Goal |
|---|---|---|
| Planning | Architect | Produce specs + design + tasks (this document) |
| Cross-repo — Dundun schema | Dundun team | PR #1: `suggested_sections` field added to `ConversationSignals` (backward-compatible) |
| Backend | BE agent | Primer subscriber, WS proxy enrichment, signals validation |
| Frontend | FE agent | SplitView wiring, suggestion bridge, Clarificación removal, collapse persistence |
| Cross-repo — Dundun prompt | Dundun team | PR #2: prompt emits `suggested_sections` when relevant |
| Code review | code-reviewer + review-before-push | Two-review gate before push |
| Archive | — | Move to `tasks/archive/` when merged |

## Progress — Planning

- [x] Proposal closed (decisions 1–5)
- [x] Spec — US-220
- [x] Spec — US-221
- [x] Spec — US-222
- [x] Spec — US-223 + US-224
- [x] Spec — US-225
- [x] Design
- [x] Backend tasks
- [x] Frontend tasks

**Status — Planning: COMPLETED** (2026-04-18)

## Progress — Implementation

- [x] Backend Phase 1 (migration + signals schema) — mig 0122 + `dundun_signals.py` (2026-04-18)
- [x] Backend Phase 2 (primer subscriber) — `chat_primer_subscriber.py` + registered (2026-04-18)
- [x] Backend Phase 3 (WS outbound snapshot) — `_enrich_outbound_frame` in conversation_controller (2026-04-18)
- [x] Backend Phase 4 (WS inbound signals validation) — `_enrich_inbound_frame` + validator (2026-04-18)
- [x] Backend Phase 5 (contract test + docs) — 42 BE tests green (2026-04-18)
- [~] Backend Phase 6 (finalization) — security-scan ✅ (4 SEC items closed), code-reviewer ✅ (1 MF + 3 SF closed); RBP blocked by repo-wide debt (see EP-21 tasks.md)
- [x] Frontend Phase 1 (SplitViewContext) — `split-view-context.tsx` with pendingSuggestions (2026-04-18)
- [x] Frontend Phase 2 (ChatPanel inbound interception) — routeSuggestedSections (2026-04-18)
- [x] Frontend Phase 3 (ChatPanel outbound snapshot) — sections_snapshot attached (2026-04-18)
- [x] Frontend Phase 4 (PendingSuggestionCard) — Accept/Reject/Edit (2026-04-18)
- [x] Frontend Phase 5 (Section editor consumption) — conflict mode + revelation (2026-04-18)
- [x] Frontend Phase 6 (collapse persistence) — localStorage per work-item (2026-04-18)
- [x] Frontend Phase 7 (page wiring + Clarificación removal) — detail-page tests assert tab absent (2026-04-18)
- [x] Frontend Phase 8 (primer UX verification) — 2026-04-18
- [x] Frontend Phase 9 (integration + polish) — 50 FE tests green (2026-04-18)
- [~] Frontend Phase 10 (finalization) — RBP blocked by repo-wide debt (see EP-21 tasks.md)
- [ ] Dundun PR #1 (schema) — external, tracked cross-repo
- [ ] Dundun PR #2 (prompt) — external, tracked cross-repo (depends on PR #1)

**Status — Backend Phases 1–5: COMPLETED** (2026-04-18)
**Status — Frontend Phases 1–9: COMPLETED** (2026-04-18)
**Pending gates**: BE security-scan + code-reviewer + review-before-push; FE review-before-push.
**Pending cross-repo**: Dundun PR #1 (schema) and PR #2 (prompt). FE degrades gracefully to no-op while pending.

## Spec Drift Resolved (2026-04-18)

- `dundun-specifications.md` §2.2 + §9 updated: `chat_ws` is live transport for BE→Dundun hop (no longer "speculative / out of scope").
- `backend/app/domain/ports/dundun.py` docstring for `chat_ws`: removed `SHOULD raise NotImplementedError` note.

## Security Fixes Applied (2026-04-18)

Security-scan + code-reviewer gates produced 1 Must Fix + 4 Should Fix. All closed:

- [x] SEC-CONF-001 — `DUNDUN_SERVICE_KEY` / `PUPPET_SERVICE_KEY` required in prod (startup validator). +4 tests in `test_settings_production_required.py`.
- [x] SEC-AUTH-001 (WS) — WS proxy verifies `thread.workspace_id == user.workspace_id` alongside user_id check. +1 integration test in `test_conversation_ws.py` asserts close code 4403.
- [x] SEC-AUTH-001 (REST, Must Fix) — `ConversationService.get_thread_for_user` extended with `workspace_id` param; REST endpoints pass `current_user.workspace_id` via new `_require_workspace` guard (401 if missing). Authz moved from controller to service layer. +4 unit tests in `test_conversation_service.py`, +1 integration test in `test_conversation_controller.py` (GET + history cross-workspace → 404; DELETE skipped due to pre-existing CSRF/rate-limit test-infra issue — covered at service unit level).
- [x] SEC-INVAL-001 — `suggested_sections` list capped at 25 items; overflow dropped with warn log. +3 tests.
- [x] SEC-LOG-001 — `_safe_error_summary` replaces raw `str(exc)` in `validate_signals` logs — only field path + error type, never raw input. +2 tests (leak canary + format).

## Known Pre-existing Test-Infra Debt (not introduced by EP-22)

- `tests/integration/test_conversation_controller.py`: 12 tests fail on `main` due to PgRateLimiter (10 req/min/IP, EP-12) exhausting budget across tests that POST `/api/v1/threads`. All tests pass in isolation. Out of EP-22 scope — tracked as separate test-infra cleanup.

## Dependencies

- EP-02 (capture) — done
- EP-03 (conversation + SplitView component) — done
- EP-04 (spec sections editor) — done
- EP-07 (diff viewer) — done (reused for pending suggestion)
- Dundun repo — cross-repo PRs described in `design.md` §9
