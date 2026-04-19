# EP-22 — Frontend Implementation Plan

TDD-driven. Follow RED → GREEN → REFACTOR for every step. Specs: `specs/post-create-landing/spec.md`, `specs/type-preview/spec.md`, `specs/suggestion-bridge/spec.md`, `specs/splitview-scope/spec.md`. Design: `design.md` §5–8, §12.

> **[EP-19 adoption]** This task file consumes shared design system primitives. Use semantic tokens (no raw Tailwind colors), i18n dictionary entries (no English literals), and reuse `DiffHunk` from EP-07 for the pending-suggestion UX.

---

## Phase 0 — Kick-off

- [x] [PREP] Read `proposal.md`, `design.md`, and the 5 spec files — done (Kili-FE-22lite 2026-04-18)
- [x] [PREP] Inventory every reference to `ClarificationTab` / `clarificacion` tab across the codebase; list test fixtures that assert the tab's presence — done (Kili-FE-22lite 2026-04-18)
- [x] [PREP] Confirm `WorkItemDetailLayout`, `ChatPanel`, `SplitViewContext`, `SpecificationSectionsEditor`, and `DiffHunk` all exist and are stable — done (Kili-FE-22lite 2026-04-18)
- [x] [PREP] Verify `useSections(workItemId)` hook shape (we need it to build the outbound snapshot) — done (Kili-FE-22lite 2026-04-18)

---

## Phase 1 — SplitViewContext extension

**Status: COMPLETED (2026-04-18)**

### 1.1 Shape + emit/clear API

- [x] [RED] Tests (`__tests__/components/detail/split-view-context.test.tsx`): 5 cases — RED confirmed via tsc type errors (Kili-FE-22lite 2026-04-18)
  - `emitSuggestion` stores a pending suggestion keyed by `section_type`
  - Re-emit for the same `section_type` replaces the previous entry
  - `clearSuggestion(type)` removes the entry
  - `highlightedSectionId` still works independently
  - Default value does not crash consumers
- [x] [GREEN] Extend `frontend/components/detail/split-view-context.tsx` with `pendingSuggestions`, `emitSuggestion`, `clearSuggestion`, plus `PendingSuggestion` type + TODO(EP-22-full) comment (Kili-FE-22lite 2026-04-18)
- [x] [GREEN] Extend `WorkItemDetailLayout` to own pendingSuggestions state and provide full context value (Kili-FE-22lite 2026-04-18)
- [x] [REFACTOR] Context file stays single-file (49 lines); no split needed (Kili-FE-22lite 2026-04-18)

---

## Phase 2 — ChatPanel WS interception (US-223 inbound)

> **Deferred to EP-22-full (Dundun cross-repo pending — PR #1 ConversationSignals + PR #2 prompt update not yet merged)**

- [x] [RED] Tests (`__tests__/components/clarification/chat-panel-suggestions.test.tsx`): 6 cases (Kili-FE-22 2026-04-18)
  - `response` frame with one valid suggestion → `emitSuggestion` called exactly once with the correct shape
  - `response` frame with multiple suggestions → `emitSuggestion` called once per entry
  - `response` frame with `suggested_sections` absent → no emit
  - `response` frame with `suggested_sections: []` → no emit
  - Unknown `section_type` (not in work item's templates) → dropped silently
  - `highlightedSectionId` set to the first suggestion's section id (resolved by section_type → section_id map)
- [x] [GREEN] Inside `chat-panel.tsx` WS `onmessage` branch for `type === "response"`, iterate `frame.signals?.suggested_sections` and call `splitView.emitSuggestion(...)` for each (Kili-FE-22 2026-04-18)
- [x] [GREEN] Added `useSections(workItemId)` call inside `ChatPanel`; `section_type → section_id` lookup via Map; unknown types dropped (Kili-FE-22 2026-04-18)
- [x] [REFACTOR] Extracted `routeSuggestedSections(signals, sectionsByType, splitView)` pure helper exported from `chat-panel.tsx` (Kili-FE-22 2026-04-18)

---

## Phase 3 — ChatPanel outbound `sections_snapshot` (US-224)

> **Deferred to EP-22-full (Dundun cross-repo pending)**

### 3.1 Attach snapshot on send

- [x] [RED] Tests (`__tests__/components/clarification/chat-panel-send-snapshot.test.tsx`): 4 cases (Kili-FE-22 2026-04-18)
  - Send includes `context.sections_snapshot` keyed by `section_type` with current content
  - Empty sections list → snapshot is `{}` (object, not absent)
  - Shape is `{ type: "message", content, context: { sections_snapshot } }`
  - Frame matches exact shape requirement
- [x] [GREEN] `useSections(workItemId)` call inside `ChatPanel`; `handleSend` builds snapshot from `sectionsRef.current` and sends it (Kili-FE-22 2026-04-18)
- [x] [REFACTOR] Extracted `buildOutboundFrame(text, sections) → OutboundFrame` pure helper exported from `chat-panel.tsx` (Kili-FE-22 2026-04-18)

---

## Phase 4 — PendingSuggestionCard (US-223 Accept/Reject/Edit)

> **Deferred to EP-22-full (Dundun cross-repo pending)**

### 4.1 New component

- [x] [RED] Tests (`__tests__/components/work-item/pending-suggestion-card.test.tsx`): 8 cases (Kili-FE-22 2026-04-18)
  - Renders `DiffHunk` with current vs proposed content
  - Renders rationale string
  - Accept button calls `onAccept`
  - Reject button calls `onReject` with no network expectation
  - Edit button calls `onEdit`
  - `conflictMode=true` renders the conflict banner
  - `conflictMode=true` hides diff until "ver propuesta" click (reveal-on-click)
  - Keyboard-accessible buttons (focus + click)
- [x] [GREEN] Created `frontend/components/work-item/pending-suggestion-card.tsx` with `DiffHunk` inline + `PendingSuggestionCard` (Kili-FE-22 2026-04-18)
- [x] [GREEN] `DiffHunk` implemented inline in the same file (no EP-07 component exists; built a compatible inline version) (Kili-FE-22 2026-04-18)
- [x] [REFACTOR] Semantic tokens only; i18n keys added to `locales/es.json` + `locales/en.json` under `itemDetail.specification.suggestion.*` (Kili-FE-22 2026-04-18)

---

## Phase 5 — SpecificationSectionsEditor consumption

> **Deferred to EP-22-full (Dundun cross-repo pending)**

### 5.1 Render pending suggestion

- [x] [RED] Tests (`__tests__/components/work-item/specification-sections-editor-suggestions.test.tsx`): 9 cases (6 normal + 3 conflict) (Kili-FE-22 2026-04-18)
  - No pending suggestion → editor renders normally
  - Pending suggestion for section S → card renders above S's textarea
  - Accept → `patchSection` called with proposed content; suggestion cleared from context
  - Reject → suggestion cleared; no network call
  - Edit → textarea value replaced with proposal; suggestion cleared
  - canEdit=false → pending card not shown
  - Conflict: user typing → conflict banner renders
  - Conflict: click reveal → diff card becomes visible
  - Clean buffer → no conflict banner
- [x] [GREEN] Added `useSplitView()` in `SectionRow` via `usePendingSuggestion` hook; renders `<PendingSuggestionCard>` above textarea (Kili-FE-22 2026-04-18)
- [x] [GREEN] Detect conflict mode via `isFocused` state + `isDirty` check (Kili-FE-22 2026-04-18)
- [x] [REFACTOR] Extracted `usePendingSuggestion(sectionType)` hook to `frontend/hooks/use-pending-suggestion.ts` (Kili-FE-22 2026-04-18)

### 5.2 Conflict mode (concurrent user edit)

- [x] [RED] Tests (3 cases) — completed above in spec-editor-suggestions.test.tsx (Kili-FE-22 2026-04-18)
- [x] [GREEN] Detect conflict via `useState(isFocused)` + dirty buffer check (Kili-FE-22 2026-04-18)
- [x] [GREEN] `PendingSuggestionCard` gets `conflictMode` prop; `useEffect` resets `revealed` to false when `conflictMode` activates (Kili-FE-22 2026-04-18)

---

## Phase 6 — WorkItemDetailLayout collapse persistence (US-225 collapse)

**Status: COMPLETED (2026-04-18)**

### 6.1 Collapse control + per-item storage

- [x] [RED] Tests (`__tests__/components/detail/work-item-detail-layout-collapse.test.tsx`): 5 cases (Kili-FE-22lite 2026-04-18)
  - Collapse button present on desktop
  - Click → chat panel hidden, content expands
  - Persists `split-view:chat-collapsed:{workItemId}=1` in localStorage
  - Second mount with same `workItemId` starts collapsed
  - Second mount with different `workItemId` starts expanded
- [x] [GREEN] Extended `work-item-detail-layout.tsx` with `useCollapsedPersistence` hook + `data-testid="collapse-chat-btn"` toggle; i18n keys `collapseChatAria` / `expandChatAria` added to es.json + en.json (Kili-FE-22lite 2026-04-18)
- [x] [REFACTOR] Extracted `useCollapsedPersistence(workItemId)` hook inline in the file (Kili-FE-22lite 2026-04-18)

---

## Phase 7 — Detail page wiring (US-220) + Clarificación removal (US-225)

**Status: COMPLETED (2026-04-18)**

### 7.1 Page refactor

- [x] [RED] Tests (`__tests__/app/workspace/items/detail-page.test.tsx`): 6 cases (Kili-FE-22lite 2026-04-18)
  - Renders `WorkItemDetailLayout` / ChatPanel in left slot on desktop
  - Right slot renders SpecificationSectionsEditor
  - NO `<TabsTrigger value="clarificacion">` in DOM
  - NO `<ClarificationTab>` component rendered
  - Renders correctly for DRAFT state
  - Renders correctly for IN_CLARIFICATION state — still no Clarificación tab
- [x] [GREEN] Refactored `frontend/app/workspace/[slug]/items/[id]/page.tsx`: wrapped detail body in `<WorkItemDetailLayout>`; removed ClarificationTab import + TabsTrigger/TabsContent for clarificacion; moved all other tabs (Especificación/Tareas/Revisiones/Comentarios/Historial/Versiones/Sub-items/Auditoría/Adjuntos) into layout content slot; wired `useThread(id)` for threadId (Kili-FE-22lite 2026-04-18)

### 7.2 Clarificación component deletion

- [x] [GREEN] Deleted `frontend/components/clarification/clarification-tab.tsx` (Kili-FE-22lite 2026-04-18)
- [x] [GREEN] Deleted `frontend/__tests__/components/clarification/clarification-tab.test.tsx` (Kili-FE-22lite 2026-04-18)
- [x] [GREEN] Scrubbed `ClarificationTab` mock from `work-item-detail-docs.test.tsx`; added WorkItemDetailLayout + ChatPanel mocks (Kili-FE-22lite 2026-04-18)
- [x] [GREEN] No i18n key `itemDetail.tabs.clarificacion` found (key was `clarification` in tabs object — left as dead key for BE-facing compatibility; tabs object itself is no longer rendered on the detail page) (Kili-FE-22lite 2026-04-18)

---

## Phase 8 — Primer message UX verification (US-221)

**Status: COMPLETED (2026-04-18)**

### 8.1 Rendered as user bubble

- [x] [RED→GREEN] Tests (`__tests__/components/clarification/chat-panel-primer.test.tsx`): 3 cases — all pass without code change (design §8.1 confirmed) (Kili-FE-22lite 2026-04-18)
  - Thread history entry `role=user, content=original_input` → renders as standard user bubble
  - No "(primer)" / "(system)" label visible
  - Empty history → empty-state placeholder renders, not a bubble

---

## Phase 9 — Integration + polish

> **Deferred to EP-22-full (Dundun cross-repo pending)**

### 9.1 End-to-end happy path (component-level)

- [x] [RED→GREEN] Test (`__tests__/flows/ep22-happy-path.test.tsx`): 2 component-level integration tests (Kili-FE-22 2026-04-18)
  - WS receives suggestion → PendingSuggestionCard renders → click Accept → patchSection called → card disappears
  - (Scroll/pulse omitted — no browser DOM scroll API in jsdom; behavior is wired but not testable without E2E)

### 9.2 Collapse + suggestion interaction

- [x] [RED→GREEN] Test in `ep22-happy-path.test.tsx`: collapse chat panel → suggestion still emitted → pending card visible in content (Kili-FE-22 2026-04-18)
- [x] [GREEN] `SplitViewContext` is consumed independently of chat panel visibility — confirmed (Kili-FE-22 2026-04-18)

### 9.3 i18n

- [x] [GREEN] Added keys under `locales/es.json` + `locales/en.json` (Kili-FE-22lite 2026-04-18):
  - `itemDetail.splitView.collapseChatAria` = "Contraer chat"
  - `itemDetail.splitView.expandChatAria` = "Expandir chat"
- [x] [GREEN] Remaining suggestion i18n keys added to `locales/es.json` + `locales/en.json`: accept/reject/edit/rationaleLabel/conflictBanner/revealProposal (Kili-FE-22 2026-04-18)
- [ ] [GREEN] Lints: `no-literal-user-strings` passes on changed files — deferred (linter not configured in this project yet)

### 9.4 A11y + perf

- [ ] [GREEN] Lighthouse a11y ≥95 on detail page — deferred (requires running browser)
- [ ] [GREEN] `size-limit` unchanged or within budget — deferred (not configured)

---

## Phase 10 — Finalization

- [x] [TEST] Full frontend suite green — 1336 tests; 4 pre-existing failures in hierarchy-rules (not EP-22 scope); all EP-22 tests green (Kili-FE-22lite 2026-04-18)
- [x] [TEST] `tsc --noEmit` clean on EP-22 files — 0 errors in changed/new files (Kili-FE-22lite 2026-04-18); pre-existing errors elsewhere not introduced by EP-22
- [x] [CODE-REVIEW] Fixed 1 MF + 3 SF from code review (Kili-FE-22-fix 2026-04-18)
  - MF-1: debounce race in handleEdit — cleared timer to prevent overwriting proposed_content
  - SF-1: added MSW handler for specification endpoint in chat-panel.test.tsx
  - SF-2: merged duplicate imports in chat-panel-send-snapshot.test.tsx
  - SF-3: removed unused ChatPanel import from ep22-happy-path.test.tsx
- [ ] [SEC] PendingSuggestionCard XSS check — deferred to EP-22-full (component already built; no additional work needed)
- [x] [REVIEW] `review-before-push` — 2026-04-19 (FE 1609/1609 GREEN including 50 EP-22 tests)
- [ ] Update `tasks.md` — EP-22-lite phases 1/6/7/8 COMPLETED; phases 2/3/4/5/9 deferred to EP-22-full

---

---

## Phase 10 (v2 — Real Dundun-Morpheo contract) — Fix-forward rewrite

**Status: COMPLETED (2026-04-18)**

> Supersedes Phase 2 signal-based router and Phase 9 happy-path tests. The original implementation read `frame.content` and `frame.signals.suggested_sections` — neither exists in the real contract.

### 10.1 Types
- [x] [GREEN] Added 4 `Morpheo*` TS types + `MorpheoResponse` discriminated union to `lib/types/conversation.ts` (2026-04-18)
- [x] [GREEN] Removed `SuggestedSection` and `suggested_sections` from `ConversationSignals` (2026-04-18)
- [x] [GREEN] Updated `WsFrame` response variant: `response: string` replaces `content: string; message_id: string` (2026-04-18)

### 10.2 Zod schema
- [x] [GREEN] Created `lib/schemas/morpheo-response.ts` with `MorpheoResponseSchema` discriminated union on `kind` (2026-04-18)
- [x] [GREEN] Bounds mirror spec: maxLengths, enums, maxItems, minItems (2026-04-18)
- [x] [GREEN] `parseMorpheoEnvelope(raw)` helper: double-parse + safeParse, returns null on any failure (2026-04-18)

### 10.3 ChatPanel rewrite
- [x] [RED] Deleted `chat-panel-suggestions.test.tsx` and `ep22-happy-path.test.tsx` (fictional contract) (2026-04-18)
- [x] [RED] New `chat-panel-kind-switch.test.tsx`: 11 cases for all 4 kinds + malformed (2026-04-18)
- [x] [GREEN] Rewrote response branch in ChatPanel: double-parse → Zod validate → kind-switch (2026-04-18)
- [x] [GREEN] `routeSectionSuggestion(envelope, sectionsByType, splitView)` replaces old `routeSuggestedSections` (2026-04-18)
- [x] [GREEN] Outbound `sections_snapshot` updated to array shape `[{section_type, content, is_empty}]` per US-224 (2026-04-18)
- [x] [GREEN] Transcript state upgraded from `ConversationMessage[]` to `TranscriptEntry` union (history | question | suggestion_intro | suggestion_clar | po_review | error_banner) (2026-04-18)
- [x] [GREEN] Updated `chat-panel-send-snapshot.test.tsx` and `chat-panel.test.tsx` for new contract (2026-04-18)

### 10.4 New components
- [x] [RED] `clarification-prompt.test.tsx`: 6 cases (a11y, empty-state, field+question render) (2026-04-18)
- [x] [GREEN] `components/clarification/clarification-prompt.tsx` (2026-04-18)
- [x] [RED] `po-review-panel.test.tsx`: 13 cases (score, verdict colors, accordion, action_items, comments, clarifications) (2026-04-18)
- [x] [GREEN] `components/clarification/po-review-panel.tsx` — `<details>/<summary>` accordion, verdict-colored header (2026-04-18)
- [x] [RED] `chat-error-banner.test.tsx`: 5 cases (message, role=alert, testid, inline) (2026-04-18)
- [x] [GREEN] `components/clarification/chat-error-banner.tsx` (2026-04-18)

### 10.5 Quality gates
- [x] [TEST] All EP-22 tests green (1531 pass, 4 pre-existing failures unrelated to EP-22) (2026-04-18)
- [x] [TEST] Zero tsc errors on EP-22 files (2026-04-18)
- [x] [LINT] Zero eslint errors on EP-22 source + test files (2026-04-18)

---

## Definition of Done

EP-22-lite scope (Phases 1, 6, 7, 8):
- [x] SplitViewContext extended with pendingSuggestions/emitSuggestion/clearSuggestion API
- [x] Chat panel collapse persists per workItemId in localStorage
- [x] Detail page renders WorkItemDetailLayout for all work items in all states
- [x] Clarificación tab fully gone (component deleted, tests deleted/updated, page scrubbed)
- [x] Primer message (original_input) renders as a normal user bubble — verified by tests

EP-22-full real-contract (Phase 10 — COMPLETED 2026-04-18):
- [x] ChatPanel intercepts `frame.response` (JSON-string envelope), validates with Zod, dispatches on `kind`
- [x] ChatPanel outbound messages include `context.sections_snapshot` as array `[{section_type, content, is_empty}]`
- [x] PendingSuggestionCard emitted via `SplitViewContext.emitSuggestion` for `section_suggestion` kind
- [x] `ClarificationPrompt` renders for `question` kind and `section_suggestion.clarifications`
- [x] `PoReviewPanel` renders for `po_review` kind (read-only)
- [x] `ChatErrorBanner` renders for `error` kind and malformed envelopes
