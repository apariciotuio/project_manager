# EP-03 — Clarification, Conversation & Assisted Actions (Dundun proxy)

**Status:** backend **IN FLIGHT** (~82%); frontend **SUBSTANTIALLY COMPLETE** (45/61 ✅)

Sub-trackers (authoritative):
- Backend: `tasks-backend.md` — ~67/82 🟡 (Phases 1–4 + 6 + 7 done; Phase 5 partial — apply_partial + QuickActionService deferred to EP-04; Phase 8 partial — 4 Must/Should Fix items deferred. Session 2026-04-18 added: WU-3 version conflict guard on suggestion apply, SEC-AUTH-001 REST workspace scope, MF#1 RLS confirmed as ticket-rot, SF#9 covered by EP-22 workspace scoping)
- Frontend: `tasks-frontend.md` — 45/61 ✅ (Phases 1–8 COMPLETED 2026-04-18; 9 items deferred to EP-04/EP-12 scope)

**Scope** (2026-04-14, `decisions_pending.md` #17, #32): Thin proxy to **Dundun**. No LLM SDK in our backend, no prompt registry/YAMLs, no context-window management. `conversation_threads` is a pointer to `dundun_conversation_id`; full history fetched on demand from Dundun. Suggestion generation / gap detection / quick actions / spec gen / breakdown all go through `DundunClient.invoke_agent(...)` (async Celery + callback) or `chat_ws` (WebSocket proxy). Split-view + diff viewer remain in-house.

## Phase summary

| Phase | Artifact | Status |
|-------|----------|--------|
| Proposal / Specs / Design | `proposal.md`, `specs/`, `design.md` | **COMPLETED** |
| Backend Phase 1 — Data model & migrations | `tasks-backend.md` Phase 1 | **COMPLETED** (2026-04-16) |
| Backend Phase 2 — Domain layer | `tasks-backend.md` Phase 2 | **COMPLETED** (2026-04-16) |
| Backend Phase 3 — Dundun integration + callback | `tasks-backend.md` Phase 3 | **COMPLETED** (2026-04-16) |
| Backend Phase 4 — Repository layer | `tasks-backend.md` Phase 4 | **COMPLETED** (2026-04-16) |
| Backend Phase 5 — Application services | `tasks-backend.md` Phase 5 | **PARTIALLY COMPLETED** — apply_partial + QuickActionService deferred to EP-04 |
| Backend Phase 6 — Celery tasks | `tasks-backend.md` Phase 6 | **COMPLETED** (2026-04-16) |
| Backend Phase 7 — API controllers | `tasks-backend.md` Phase 7 | **COMPLETED** (2026-04-16) |
| Backend Phase 8 — Security + observability | `phase_8_security_findings.md` | **PARTIALLY COMPLETED** — 4 MF/SF items deferred (workspace RLS, WS duplex fix, request binding, JWT-in-query) |
| Frontend Phases 1–8 | `tasks-frontend.md` | **COMPLETED** (2026-04-18) — 45/61 done; 9 items deferred to EP-04/EP-12 |
| Code review + review-before-push | — | Pending |

**Status: IN FLIGHT** (2026-04-18) — backend ~82% (67/82), frontend phases complete with 9 deferred items. RBP gate: blocked by repo-wide debt (see EP-21 tasks.md § "Status 2026-04-18").
