# EP-22 — Frontend Implementation Plan

TDD-driven. Follow RED → GREEN → REFACTOR for every step. Specs: `specs/post-create-landing/spec.md`, `specs/type-preview/spec.md`, `specs/suggestion-bridge/spec.md`, `specs/splitview-scope/spec.md`. Design: `design.md` §5–8, §12.

> **[EP-19 adoption]** This task file consumes shared design system primitives. Use semantic tokens (no raw Tailwind colors), i18n dictionary entries (no English literals), and reuse `DiffHunk` from EP-07 for the pending-suggestion UX.

---

## Phase 0 — Kick-off

- [ ] [PREP] Read `proposal.md`, `design.md`, and the 5 spec files
- [ ] [PREP] Inventory every reference to `ClarificationTab` / `clarificacion` tab across the codebase; list test fixtures that assert the tab's presence
- [ ] [PREP] Confirm `WorkItemDetailLayout`, `ChatPanel`, `SplitViewContext`, `SpecificationSectionsEditor`, and `DiffHunk` all exist and are stable
- [ ] [PREP] Verify `useSections(workItemId)` hook shape (we need it to build the outbound snapshot)

---

## Phase 1 — SplitViewContext extension

### 1.1 Shape + emit/clear API

- [ ] [RED] Tests (`__tests__/components/detail/split-view-context.test.tsx`): ≥5 cases
  - `emitSuggestion` stores a pending suggestion keyed by `section_type`
  - Re-emit for the same `section_type` replaces the previous entry
  - `clearSuggestion(type)` removes the entry
  - `highlightedSectionId` still works independently
  - Default value does not crash consumers
- [ ] [GREEN] Extend `frontend/components/detail/split-view-context.tsx` with `pendingSuggestions`, `emitSuggestion`, `clearSuggestion`, plus the `PendingSuggestion` type (see design §5.1)
- [ ] [GREEN] Extend `WorkItemDetailLayout` to own the state and provide the new context value
- [ ] [REFACTOR] Split the context file into `split-view-context.tsx` (the React context) and `pending-suggestion.ts` (the types) if file length grows

---

## Phase 2 — ChatPanel WS interception (US-223 inbound)

### 2.1 Intercept `suggested_sections`

- [ ] [RED] Tests (`__tests__/components/clarification/chat-panel-suggestions.test.tsx`): ≥6 cases using `MockWebSocket` or the existing fake
  - `response` frame with one valid suggestion → `emitSuggestion` called exactly once with the correct shape
  - `response` frame with multiple suggestions → `emitSuggestion` called once per entry
  - `response` frame with `suggested_sections` absent → no emit
  - `response` frame with `suggested_sections: []` → no emit
  - Unknown `section_type` (not in work item's templates) → dropped silently
  - `highlightedSectionId` set to the first suggestion's section id (resolved by section_type → section_id map)
- [ ] [GREEN] Inside `chat-panel.tsx` WS `onmessage` branch for `type === "response"`, iterate `frame.signals?.suggested_sections` and call `splitView.emitSuggestion(...)` for each
- [ ] [GREEN] Add a `section_type → section_id` lookup (from the sections cache) to resolve the highlight target; skip entries without a matching section
- [ ] [REFACTOR] Extract interception into a pure helper `routeSuggestedSections(frame, sectionsByType, splitView)` unit-testable in isolation

---

## Phase 3 — ChatPanel outbound `sections_snapshot` (US-224)

### 3.1 Attach snapshot on send

- [ ] [RED] Tests (`__tests__/components/clarification/chat-panel-send-snapshot.test.tsx`): ≥4 cases
  - Send includes `context.sections_snapshot` keyed by `section_type` with current content
  - Empty sections list → snapshot is `{}` (object, not absent)
  - Updated textbox value (not yet autosaved) flows into the snapshot
  - Shape is `{ type: "message", content, context: { sections_snapshot } }`
- [ ] [GREEN] Pass sections via `SplitViewContext` or a fresh `useSections(workItemId)` call inside `ChatPanel`; modify `handleSend` to build the snapshot and include it in the WS payload
- [ ] [REFACTOR] Extract `buildOutboundFrame(text, sections) → OutboundFrame` helper for testability

---

## Phase 4 — PendingSuggestionCard (US-223 Accept/Reject/Edit)

### 4.1 New component

- [ ] [RED] Tests (`__tests__/components/work-item/pending-suggestion-card.test.tsx`): ≥7 cases
  - Renders `DiffHunk` with current vs proposed
  - Renders rationale string
  - Accept button calls `onAccept`
  - Reject button calls `onReject` with no network expectation
  - Edit button calls `onEdit`
  - `conflictMode=true` renders the "mientras escribías" banner prefix; main card appears only after "ver propuesta" click (tested separately)
  - Keyboard-accessible (buttons focusable, Enter triggers handler)
- [ ] [GREEN] Create `frontend/components/work-item/pending-suggestion-card.tsx` per design §5.3
- [ ] [GREEN] Import `DiffHunk` from EP-07 location
- [ ] [REFACTOR] Semantic tokens only; i18n strings in `i18n/es/workspace.ts` under `itemDetail.specification.suggestion.*`

---

## Phase 5 — SpecificationSectionsEditor consumption

### 5.1 Render pending suggestion

- [ ] [RED] Tests (`__tests__/components/work-item/specification-sections-editor-suggestions.test.tsx`): ≥6 cases
  - No pending suggestion → editor renders normally
  - Pending suggestion for section S → card renders above S's textarea
  - Accept → `patchSection` called with proposed content; suggestion cleared from context
  - Reject → suggestion cleared; no network call
  - Edit → textarea value replaced with proposal; suggestion cleared; autosave debounce still works
  - Editor in no-write-access mode → pending suggestion is not shown (read-only state doesn't receive AI proposals)
- [ ] [GREEN] Add `useSplitView()` in `SectionRow`; subscribe to `pendingSuggestions[section.section_type]`
- [ ] [GREEN] Render `<PendingSuggestionCard>` above the textarea when a pending suggestion exists
- [ ] [REFACTOR] Extract a `usePendingSuggestion(sectionType)` hook for readability

### 5.2 Conflict mode (concurrent user edit)

- [ ] [RED] Tests (≥3 cases):
  - User typing in S (focus + `value !== section.content`) → suggestion arrives → banner renders, diff card hidden
  - Click "ver propuesta" → diff renders comparing `value` (local buffer) vs `proposed_content`
  - Accept after local edit → EP-04 save of buffer is NOT cancelled; proposal commits on top via its own save (last-write-wins)
- [ ] [GREEN] Detect conflict mode via a ref tracking whether the textarea has focus or dirty buffer
- [ ] [GREEN] Wire conflict banner → click reveals `<PendingSuggestionCard conflictMode>`

---

## Phase 6 — WorkItemDetailLayout collapse persistence (US-225 collapse)

### 6.1 Collapse control + per-item storage

- [ ] [RED] Tests (`__tests__/components/detail/work-item-detail-layout-collapse.test.tsx`): ≥5 cases
  - Collapse button present on desktop
  - Click → chat panel hidden, content expands
  - Persists `split-view:chat-collapsed:{workItemId}=1` in localStorage
  - Second mount with same `workItemId` starts collapsed
  - Second mount with different `workItemId` starts expanded
- [ ] [GREEN] Extend `work-item-detail-layout.tsx` with a collapse toggle button and per-item key read/write
- [ ] [REFACTOR] Extract `useCollapsedPersistence(workItemId)` hook

---

## Phase 7 — Detail page wiring (US-220) + Clarificación removal (US-225)

### 7.1 Page refactor

- [ ] [RED] Tests (`__tests__/app/workspace/items/detail-page.test.tsx`): ≥6 cases
  - Renders `WorkItemDetailLayout` on desktop
  - `ChatPanel` on the left slot
  - Right slot renders the existing spec/tasks/reviews/comments/history navigation (now inside the content area)
  - NO `<TabsTrigger value="clarificacion">` in the DOM
  - NO `<ClarificationTab>` component rendered
  - Renders correctly for all states (Draft / IN_CLARIFICATION / READY / IN_PROGRESS / DONE)
- [ ] [GREEN] Refactor `frontend/app/workspace/[slug]/items/[id]/page.tsx` per design §7:
  - Wrap the detail body in `<WorkItemDetailLayout workItemId={id} threadId={threadId}>`
  - Move the right-panel tabs (Especificación / Tareas / Revisiones / Comentarios / Historial / Versiones / Sub-items / Auditoría / Adjuntos) inside the layout's content slot
  - Remove `<TabsTrigger value="clarificacion">` and `<TabsContent value="clarificacion">`
  - Remove the `import { ClarificationTab } from '@/components/clarification/clarification-tab'` line
- [ ] [GREEN] Fetch the element thread id (needed by `WorkItemDetailLayout`) via `useThread(workItemId)` (existing hook)

### 7.2 Clarificación component deletion

- [ ] [GREEN] Delete `frontend/components/clarification/clarification-tab.tsx`
- [ ] [GREEN] Delete / update `frontend/components/clarification/__tests__/clarification-tab.test.tsx` if present
- [ ] [GREEN] Grep for any remaining `ClarificationTab` / `clarificacion` string literals; scrub dead references
- [ ] [GREEN] Update i18n dictionaries `i18n/es/workspace.ts` — remove `itemDetail.tabs.clarificacion` if present; ensure no orphaned keys

---

## Phase 8 — Primer message UX verification (US-221)

### 8.1 Rendered as user bubble

- [ ] [RED] Tests (`__tests__/components/clarification/chat-panel-primer.test.tsx`): ≥3 cases
  - Thread history returns one entry with `role=user, content=original_input` → rendered as a standard user bubble
  - No "(primer)" / "(system)" label visible
  - Empty history → empty-state placeholder renders (not the bubble)
- [ ] [GREEN] No FE code change expected — the bubble rendering already treats `role=user` uniformly. Tests confirm there is no accidental branding regression.

---

## Phase 9 — Integration + polish

### 9.1 End-to-end happy path (component-level)

- [ ] [RED] Test (`__tests__/flows/ep22-happy-path.test.tsx`):
  - Mount `items/[id]/page.tsx` with a fresh work item
  - WS receives a `response` with a suggestion for `problem_statement`
  - Assert the section scrolls into view, pulse highlight active, pending card rendered
  - Click Accept → `patchSection` called; card disappears; section content updated
- [ ] [GREEN] Fix any integration wiring gaps surfaced by the test

### 9.2 Collapse + suggestion interaction

- [ ] [RED] Test: collapse chat panel → suggestion still emitted and pending card shown in content (user can accept from the content panel alone)
- [ ] [GREEN] Confirm `SplitViewContext` consumption is independent of the chat panel's visibility

### 9.3 i18n

- [ ] [GREEN] Add keys under `i18n/es/workspace.ts`:
  - `itemDetail.specification.suggestion.accept` = "Aceptar"
  - `itemDetail.specification.suggestion.reject` = "Rechazar"
  - `itemDetail.specification.suggestion.edit` = "Editar"
  - `itemDetail.specification.suggestion.rationaleLabel` = "Motivo"
  - `itemDetail.specification.suggestion.conflictBanner` = "Dundun propuso un cambio mientras escribías — ver propuesta"
  - `itemDetail.splitView.collapseChatAria` = "Contraer chat"
  - `itemDetail.splitView.expandChatAria` = "Expandir chat"
- [ ] [GREEN] Lints: `no-literal-user-strings` passes on changed files

### 9.4 A11y + perf

- [ ] [GREEN] Lighthouse a11y ≥95 on detail page (existing gate)
- [ ] [GREEN] `size-limit` unchanged or within budget

---

## Phase 10 — Finalization

- [ ] [TEST] Full frontend suite green
- [ ] [TEST] `tsc --noEmit` clean (no new errors)
- [ ] [SEC] Verify `PendingSuggestionCard` renders proposed content as plain text (no markdown HTML injection via dangerouslySetInnerHTML; existing pattern in EP-07 `DiffHunk` is safe)
- [ ] [REVIEW] `code-reviewer`
- [ ] [REVIEW] `review-before-push`
- [ ] Update `tasks.md` — all checkboxes ticked; status COMPLETED (YYYY-MM-DD)

---

## Definition of Done

- Detail page renders `WorkItemDetailLayout` for all work items in all states
- Clarificación tab is fully gone (component deleted, tests updated, i18n scrubbed)
- `ChatPanel` intercepts `signals.suggested_sections` and emits to `SplitViewContext`
- `ChatPanel` outbound messages include `context.sections_snapshot`
- `PendingSuggestionCard` renders inline in `SpecificationSectionsEditor` with Accept/Reject/Edit
- Conflict mode (user mid-edit) shows a banner instead of auto-replacing content
- Chat panel collapse state persists per (user, work_item_id) in localStorage
- Primer message (`original_input`) renders as a normal user bubble
- ≥35 new frontend tests — all green
