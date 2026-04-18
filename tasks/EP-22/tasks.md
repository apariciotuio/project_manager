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

- [ ] Backend Phase 1 (migration + signals schema)
- [ ] Backend Phase 2 (primer subscriber)
- [ ] Backend Phase 3 (WS outbound snapshot)
- [ ] Backend Phase 4 (WS inbound signals validation)
- [ ] Backend Phase 5 (contract test + docs)
- [ ] Backend Phase 6 (finalization)
- [ ] Frontend Phase 1 (SplitViewContext)
- [ ] Frontend Phase 2 (ChatPanel inbound interception)
- [ ] Frontend Phase 3 (ChatPanel outbound snapshot)
- [ ] Frontend Phase 4 (PendingSuggestionCard)
- [ ] Frontend Phase 5 (Section editor consumption)
- [ ] Frontend Phase 6 (collapse persistence)
- [ ] Frontend Phase 7 (page wiring + Clarificación removal)
- [ ] Frontend Phase 8 (primer UX verification)
- [ ] Frontend Phase 9 (integration + polish)
- [ ] Frontend Phase 10 (finalization)
- [ ] Dundun PR #1 (schema)
- [ ] Dundun PR #2 (prompt)

## Dependencies

- EP-02 (capture) — done
- EP-03 (conversation + SplitView component) — done
- EP-04 (spec sections editor) — done
- EP-07 (diff viewer) — done (reused for pending suggestion)
- Dundun repo — cross-repo PRs described in `design.md` §9
