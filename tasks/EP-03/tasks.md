# EP-03 — Clarification, Conversation & Assisted Actions (Dundun proxy)

**Status:** backend **IN FLIGHT** (~75%); frontend **NOT STARTED**

Sub-trackers (authoritative):
- Backend: `tasks-backend.md` — 60/80 🟡 (Phases 1–3 done; remaining: SSE event stream, WS proxy integration tests, suggestion-apply hand-off to versioning, Celery callback hardening)
- Frontend: `tasks-frontend.md` — 0/56 ⬜ (untouched — chat panel, gap panel, suggestion preview, quick actions)

**Scope** (2026-04-14, `decisions_pending.md` #17, #32): Thin proxy to **Dundun**. No LLM SDK in our backend, no prompt registry/YAMLs, no context-window management. `conversation_threads` is a pointer to `dundun_conversation_id`; full history fetched on demand from Dundun. Suggestion generation / gap detection / quick actions / spec gen / breakdown all go through `DundunClient.invoke_agent(...)` (async Celery + callback) or `chat_ws` (WebSocket proxy). Split-view + diff viewer remain in-house.

## Phase summary

| Phase | Artifact | Status |
|-------|----------|--------|
| Proposal / Specs / Design | `proposal.md`, `specs/`, `design.md` | **COMPLETED** |
| Backend Phase 1 — Data model & migrations | `tasks-backend.md` Phase 1 | **COMPLETED** |
| Backend Phase 2 — Dundun client + auth | `tasks-backend.md` Phase 2 | **COMPLETED** |
| Backend Phase 3 — Threads + messages REST | `tasks-backend.md` Phase 3 | **COMPLETED** |
| Backend Phase 4 — Async agent invocations (Celery) | `tasks-backend.md` Phase 4 | **IN FLIGHT** — callback hardening pending |
| Backend Phase 5 — WebSocket chat proxy | `tasks-backend.md` Phase 5 | **IN FLIGHT** — integration tests pending |
| Backend Phase 6 — Suggestion apply + version hand-off | `tasks-backend.md` Phase 6 | Pending |
| Backend Phase 7 — SSE event stream for UI live updates | `tasks-backend.md` Phase 7 | Pending |
| Backend Phase 8 — Security + observability | `phase_8_security_findings.md` | **COMPLETED** |
| Frontend | `tasks-frontend.md` | **NOT STARTED** |
| Code review + review-before-push | — | Pending |
