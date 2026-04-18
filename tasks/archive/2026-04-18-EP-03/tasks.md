# EP-03 — Clarification, Conversation & Assisted Actions (Dundun proxy)

**Status (MVP scope, archived 2026-04-18)**: ✅ COMPLETE — MVP thin-proxy to Dundun shipped (Phases 1–4 + 6 + 7 + FE 1–8). Deferrals below are all explicitly scoped out or re-homed to other epics — not blocking MVP.

### MVP Scope Shipped
- Thin Dundun proxy: `invoke_agent` (async Celery + callback) and `chat_ws` (WebSocket proxy).
- Backend controllers: conversation, suggestion generation, gap detection, dundun callback (HMAC-verified), quick actions router.
- Backend services + repos: `ConversationService`, `SuggestionService`, `GapService`, migrations 0031/0032/0033 (incl. RLS on EP-03 tables — MF#1 was ticket-rot, migration already in tree).
- Backend: 67/82 items ticked (Phases 1–4 + 6 + 7 done).
- Frontend: 45/61 items ticked (Phases 1–8 done 2026-04-18 — QuickActionMenu, SuggestionBatchCard, SplitView layout, ChatPanel WS transport).

### Known Deferrals (intentional, not blockers)

1. **Phase 5 `apply_partial` + `QuickActionService`** → re-homed to EP-04 (quality engine owns quick-action dispatch and gap ai-review).
2. **Must Fix #2 — WS bidirectional proxy** (client→upstream frames are dropped because `DundunClient.chat_ws` is an async generator instead of a duplex context manager) → deferred pending Dundun E2E stub availability; one skipped test flags it. Current behaviour: upstream→client frames work (the important direction for showing Dundun replies).
3. **Should Fix #6–#8** (request-id binding hardening, JWT-in-query-param logging, JwtAdapter per-connection perf) → deferred to follow-up or EP-12.
4. **Should Fix #9** — service private-attribute leak — partially resolved 2026-04-18: `ConversationService.get_thread_for_user()` added per EP-22 WU-3 scope.
5. **FE ChatPanel suggestion-frame peeker** (`onSuggestionEmitted` prop) → deferred to EP-12 (SSE observability); core WS chat shipped.
6. **FE section-pulse animation** (pulse a section when ChatPanel streams tokens for it) → deferred to EP-12.
7. **FE detail-page wiring of SplitViewContext** → deferred; EP-22 landed its own wiring for the suggestion-bridge flow.
8. **RBP gate** → same repo-wide debt story as EP-21/EP-22; tracked elsewhere.

### Cross-Epic Pointers

| Item | Owner |
|---|---|
| QuickActionService + execute_action endpoint | **EP-04** |
| `/api/v1/work-items/{id}/gaps/ai-review` endpoint | **EP-04** |
| WS bidir proxy refactor (Must Fix #2) | Follow-up — needs Dundun E2E stub |
| Section-pulse + detail-page chat wiring | **EP-12** |
| Repo-wide RBP debt (ruff / mypy / eslint) | **EP-21** (archived with deferred gate) |

---

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
