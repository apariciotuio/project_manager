# EP-03 Frontend Tasks — Clarification, Conversation & Assisted Actions (Dundun proxy)

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `SeverityBadge` for gap severity (blocking/warning/info), `CopyButton` for copy-to-clipboard UX, `HumanError` for Dundun failures + WebSocket errors, semantic tokens, i18n `i18n/es/assistant.ts`. The split-view layout, chat stream rendering, and suggestion preview panel remain feature-specific. See `tasks/extensions.md#EP-19`.

Branch: `feature/ep-03-frontend`
Refs: EP-03
Depends on: EP-00 frontend, EP-01 frontend (WorkItem types), EP-03 backend API, EP-19 catalog

> **Scope (2026-04-14, decisions_pending.md #17, #32)**: Chat transport is **WebSocket** (proxied through our BE to Dundun `/ws/chat`). No SSE stream for chat, no `LLM_TIMEOUT` payload, no token-count display. Message history fetched on demand via `GET /api/v1/threads/{id}/history` (delegated to Dundun). Keep: diff viewer, split-view, suggestion UI, quick actions, gap panel.

---

## API Contract (Blocked by: EP-03 backend)

**Chat transport:** WebSocket `wss://<host>/ws/conversations/{thread_id}`. Frame schema is owned by Dundun and forwarded verbatim:
```
{"type": "progress", "content": "..."}
{"type": "response", "content": "...", "message_id": "<dundun-id>"}
{"type": "error", "code": "<dundun-error-code>", "message": "..."}
```

**Thread response:**
```typescript
interface ConversationThread {
  id: string
  work_item_id: string | null            // null for general threads
  user_id: string                        // threads are per-user (decision #17)
  dundun_conversation_id: string
  last_message_preview: string | null
  last_message_at: string | null
  created_at: string
}

interface ConversationMessage {
  // history is fetched from Dundun via GET /threads/{id}/history;
  // schema mirrors Dundun's message shape (no token_count, no prompt metadata in our DB)
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}
```

**Suggestion set:**
```typescript
interface SuggestionSet {
  id: string
  work_item_id: string
  status: 'pending' | 'partially_applied' | 'fully_applied' | 'rejected' | 'expired'
  created_at: string
  expires_at: string
  items: SuggestionItem[]
}

interface SuggestionItem {
  id: string
  section: string
  current_content: string
  proposed_content: string
  rationale: string | null
  status: 'pending' | 'accepted' | 'rejected'
}
```

**Gap report:**
```typescript
interface GapFinding {
  dimension: string
  severity: 'blocking' | 'warning' | 'info'
  message: string
  source: 'rule' | 'llm'
}
```

---

## Phase 1 — Type Definitions

- [x] Implement `src/types/conversation.ts`: `ConversationThread`, `ConversationMessage`, `MessageType`, `AuthorType` — all typed exactly as above (→ `frontend/lib/types/conversation.ts`)
- [x] Implement `src/types/suggestion.ts`: `SuggestionSet`, `SuggestionItem`, `SuggestionStatus` (→ `frontend/lib/types/suggestion.ts`)
- [x] Implement `src/types/gap.ts`: `GapFinding`, `GapReport` (`{ work_item_id, findings, score }`) (→ `frontend/lib/types/gap.ts`)

**Status: COMPLETED** (2026-04-17)

---

## Phase 2 — API Client Functions

File: `src/lib/api/conversation.ts`, `src/lib/api/suggestions.ts`, `src/lib/api/gaps.ts`

- [x] Implement `getThreads(workItemId?: string): Promise<ConversationThread[]>` (→ `lib/api/threads.ts`)
- [x] Implement `createThread(data): Promise<ConversationThread>`
- [x] Implement `getThreadHistory(threadId): Promise<ConversationMessage[]>` (replaces getThread pagination — WS-based chat; history on demand)
- [x] Implement `archiveThread(threadId: string): Promise<void>`
- [x] Implement `triggerAiReview(workItemId: string): Promise<{ job_id: string }>` (→ `lib/api/gaps.ts`)
- [x] Implement `getGapReport(workItemId: string): Promise<GapReport>` — stubs [] until EP-04 ships (TODO comment in file)
- [x] Implement `generateSuggestionSet(workItemId: string): Promise<{ set_id: string }>` (→ `lib/api/suggestions.ts`)
- [x] Implement `getSuggestionSet(setId: string): Promise<SuggestionSet>`
- [x] Implement `applySuggestions(setId: string, acceptedItemIds: string[]): Promise<ApplySuggestionsResult>` — throws ApiError(409) on conflict
- [x] Implement `updateSuggestionItemStatus(itemId, status): Promise<void>`
- [x] `sendMessage` via WS — shipped in `frontend/components/clarification/chat-panel.tsx:287` (`wsRef.current.send(JSON.stringify(frame))`) (stale-tick 2026-04-19)
- [ ] `executeQuickAction` / `undoQuickAction` — **→ v2-carveout.md** (EP-04 scope)
- [ ] SSE stream client — **→ v2-carveout.md** (EP-12 owned; not used by EP-03)
- [x] [RED→GREEN] Unit tests: 14 tests covering threads, suggestions, gaps API clients (→ `__tests__/lib/api/`)

**Status: COMPLETED** (2026-04-17)

---

## Phase 3 — GapPanel Component

Component: `src/components/clarification/gap-panel.tsx`

Props:
```typescript
interface GapPanelProps {
  workItemId: string
  workItemVersion: number
}
```

- [x] [RED→GREEN] Write component tests (7 tests): blocking before warnings, AI/Rule badges, dismiss client-side, run AI review loading state, completeness score, error state (→ `__tests__/components/clarification/gap-panel.test.tsx`)
- [x] [GREEN] Implement `frontend/components/clarification/gap-panel.tsx`: useGaps hook, severity sort, dismiss via local state, AI review button w/ loading, error state with retry

**Status: COMPLETED** (2026-04-17)

### Acceptance Criteria — GapPanel

See also: specs/clarification/spec.md (US-030)

WHEN `GapPanel` renders with findings where 2 are blocking and 3 are warnings
THEN blocking findings are rendered first (red indicator)
AND warning findings follow (yellow indicator)
AND no info-severity findings are shown in the blocking section

WHEN a gap has `source = "dundun"`
THEN it displays an "AI" badge next to the message

WHEN a gap has `source = "rule"`
THEN it displays a "Rule" badge

WHEN the user clicks the dismiss button on a gap
THEN that gap is removed from the displayed list
AND no API call is made (client-side only)
AND the gap reappears on next page load (not persisted)

WHEN "Run AI Review" is clicked
THEN `triggerAiReview(workItemId)` is called
AND the button shows a loading spinner and is disabled
AND a "Review in progress..." status message replaces the button

WHEN `getGapQuestions()` returns an error
THEN "Gap analysis unavailable" is shown with a retry button
AND no findings list is rendered

---

## Phase 4 — ClarificationQuestion Component — **→ v2-carveout.md** (ChatPanel handles Q&A flow via WS; standalone component not needed for MVP)

- [ ] [RED] Write component tests — **→ v2-carveout.md**
- [ ] [GREEN] Implement `ClarificationQuestion` — **→ v2-carveout.md**

---

## Phase 5 (plan) / Phase 4 (prompt scope) — ChatPanel Component

- [x] [RED→GREEN] ChatPanel (8 tests): empty state, historical messages, optimistic send, progress frame append, response finalization, disable during streaming, error banner, WS close on unmount (→ `__tests__/components/clarification/chat-panel.test.tsx`)
- [x] [GREEN] Implement `frontend/components/clarification/chat-panel.tsx`: WS lifecycle via useEffect, useThread hook for history, MessageBubble sub-component, Ctrl+Enter send, auto-scroll

**Status: COMPLETED** (2026-04-17)

### Acceptance Criteria — ConversationThread

See also: specs/conversation/spec.md (US-031)

WHEN the thread has no messages
THEN the empty state "Start the conversation by sending a message" is displayed
AND the MessageComposer is visible and enabled

WHEN the user submits a message
THEN the human message is immediately appended to the displayed list (optimistic)
AND the `MessageComposer` textarea is cleared
AND `MessageComposer` is disabled while streaming is in progress

WHEN WS `progress` frames arrive
THEN the partial content is appended to the last assistant message bubble incrementally
AND the bubble does NOT re-render from scratch on each frame (no flash)

WHEN a WS `response` frame arrives
THEN the streaming message's `message_id` is set to the value from the frame
AND the MessageComposer is re-enabled

WHEN a WS `error` frame arrives
THEN an inline error banner is appended (with Dundun's `code` + `message`)
AND the MessageComposer is re-enabled
AND a "Retry" option is shown

WHEN the component unmounts while the WS is open
THEN the WebSocket is closed (cleanup function called)
AND no further state updates occur after unmount

---

## Phase 5 (prompt scope) — SuggestionBatchCard Component

- [x] [RED→GREEN] SuggestionBatchCard (6 tests): one card per item, Apply Selected disabled until accepted, only accepted IDs sent, expired set disables apply, 409 conflict banner w/ regenerate (→ `__tests__/components/clarification/suggestion-batch-card.test.tsx`)
- [x] [GREEN] Implement `frontend/components/clarification/suggestion-batch-card.tsx`: expand/collapse, local accept/reject state, ApiError(409) handling, SuggestionDiffCard sub-component (current/proposed side-by-side)

**Status: COMPLETED** (2026-04-17)

---

## Phase 6 (prompt scope) — ClarificationTab + Work-Item Integration

- [x] [RED→GREEN] ClarificationTab (4 tests): renders chat+gap panels, Get Suggestions button visible only to canEdit (→ `__tests__/components/clarification/clarification-tab.test.tsx`)
- [x] [GREEN] Implement `frontend/components/clarification/clarification-tab.tsx`: composes ChatPanel + GapPanel + SuggestionBatchCard + generation progress stages
- [x] Add `clarificacion` tab to `app/workspace/[slug]/items/[id]/page.tsx` between Specification and Tasks; renders `ClarificationTab` only for canEdit check; all tabs now include clarification

**Status: COMPLETED** (2026-04-17)

---

## Phase 6 (plan) — SuggestionPreviewPanel Component (MERGED into prompt Phase 5)

Component: `src/components/suggestions/suggestion-preview-panel.tsx`

Props:
```typescript
interface SuggestionPreviewPanelProps {
  suggestionSet: SuggestionSet
  onApplied: (result: { new_version: number, applied_sections: string[] }) => void
  onDismiss: () => void
}
```

- [x] [RED] Write component tests: covered in suggestion-batch-card.test.tsx + suggestion-batch-card-apply.test.tsx (merged into Phase 5)
- [x] [GREEN] Implement `SuggestionPreviewPanel`: implemented as `SuggestionBatchCard` in `components/clarification/suggestion-batch-card.tsx` (merged into Phase 5; covers all ACs)
- [x] [GREEN] Implement `SuggestionDiffCard` sub-component: implemented as `SuggestionDiffCard` inside suggestion-batch-card.tsx

### Acceptance Criteria — SuggestionPreviewPanel

See also: specs/suggestions/spec.md (US-032)

WHEN `suggestionSet.items` contains 3 items
THEN 3 `SuggestionDiffCard` components are rendered
AND each shows the section label, current content block, and proposed content block

WHEN no items are accepted (all pending or rejected)
THEN "Apply Selected" button is disabled

WHEN at least 1 item is accepted
THEN "Apply Selected" button is enabled

WHEN `suggestionSet.status = "expired"`
THEN "Apply Selected" is disabled
AND "These suggestions have expired" message is shown
AND "Generate new" button calls `generateSuggestionSet()` on click

WHEN "Apply Selected" is clicked
THEN `applySuggestions(set_id, acceptedItemIds)` is called with ONLY the IDs of accepted items (not pending, not rejected)
AND rejected and pending items remain unchanged in the work item

WHEN `applySuggestions()` returns HTTP 409
THEN an inline banner: "Content changed since suggestions were generated. Regenerate?" is shown
AND a "Regenerate" button calls `generateSuggestionSet(workItemId)` on click

WHEN `applySuggestions()` resolves successfully
THEN `onApplied({ new_version, applied_sections })` is called
AND the panel can be dismissed
AND the following caches are invalidated: `['workItem', workItemId]`, `['sections', workItemId]`, `['completeness', workItemId]`, `['versions', workItemId]`, `['timeline', workItemId]`

WHEN "Reject all" or `onDismiss` is called
THEN no API call is made
AND the suggestion set status is NOT changed in this component (backend handles expiry separately)

---

## Phase 7 — QuickActionMenu Component

Component: `src/components/suggestions/quick-action-menu.tsx`

Props:
```typescript
interface QuickActionMenuProps {
  workItemId: string
  section: string
  sectionContent: string
  onActionApplied: (newContent: string) => void
}
```

Available actions per section type:
- `description`: rewrite, concretize, expand, shorten
- `acceptance_criteria`: generate_ac
- All text sections: rewrite, expand, shorten

- [x] [RED] Write component tests: 10 tests — section filtering, empty content, spinner, success+undo toast, undo countdown, undo click, error state, unmount cleanup (→ `__tests__/components/clarification/quick-action-menu.test.tsx`)
- [x] [GREEN] Implement `QuickActionMenu`: `components/clarification/quick-action-menu.tsx` — inline button group, executeQuickAction → spinner → onActionApplied, undo toast with 10s setTimeout, cleanup on unmount, inline error state; `lib/api/quick-actions.ts` with executeQuickAction/undoQuickAction

### Acceptance Criteria — QuickActionMenu

See also: specs/suggestions/spec.md (US-033)

WHEN `section = "acceptance_criteria"` and `sectionContent` is non-empty
THEN only `generate_ac` action button is rendered (not rewrite/concretize/expand/shorten)

WHEN `section = "description"` and `sectionContent` is non-empty
THEN `rewrite`, `concretize`, `expand`, `shorten` actions are rendered

WHEN `sectionContent = ""` (empty)
THEN all action buttons are disabled (non-interactive)
AND a tooltip explains "No content to act on"

WHEN an action is clicked
THEN all action buttons are replaced by a loading spinner
AND `executeQuickAction(workItemId, section, action)` is called

WHEN `executeQuickAction()` resolves successfully
THEN `onActionApplied(result.result)` is called with the new content
AND an "Undo" toast appears with a visible 10-second countdown

WHEN the Undo button in the toast is clicked within 10 seconds
THEN `undoQuickAction(workItemId, action_id)` is called
AND the section reverts to the pre-action content
AND the toast disappears

WHEN 10 seconds elapse without clicking Undo
THEN the toast disappears automatically
AND the section content remains as the action result

WHEN the component unmounts while the undo countdown is active
THEN the `setTimeout` is cleared (no state-update-after-unmount error)

WHEN `executeQuickAction()` returns an error
THEN an inline error message is shown next to the action that failed
AND the content is unchanged

---

## Phase 8 — Integration: Work Item Detail Page Extensions

Update: `src/app/workspace/[slug]/work-items/[id]/page.tsx` (extends EP-01 detail page)

- [x] Add `GapPanel` to detail page: implemented in `ClarificationTab` (Phase 6 prompt scope) — GapPanel renders in clarification tab
- [x] Add `ConversationThread` panel: `ChatPanel` in clarification tab (`ClarificationTab`) covers this
- [x] Add "Get Suggestions" button with `SuggestionBatchCard`: `ClarificationTab` has generate + polling + progress stages + soft/hard timeouts via `useSuggestions` hook
- [x] `QuickActionMenu` stub: implemented as `components/clarification/quick-action-menu.tsx` (Phase 7)
- [x] Polling + progress stages: `useSuggestions` hook handles polling, soft 20s timeout, hard 45s timeout, progress stage cycling
- [x] [RED→GREEN] Component tests: covered in `clarification-tab.test.tsx`; useSuggestions hooks tests cover timeout/polling behavior

---

## Group: Work Item Detail Split View Layout

Extension from: extensions.md (EP-03 / Req #10)
No backend changes required — existing EP-03 APIs support this.

### API types (no new endpoints)

```typescript
// Re-uses ConversationThread + ConversationMessage from Phase 1
// Re-uses SuggestionSet + SuggestionItem from Phase 1
// Re-uses SpecificationPanel from EP-04 (import, do not redefine)
// Re-uses task tree from EP-05 (import, do not redefine)
```

### WorkItemDetailLayout Component

Component: `src/components/detail/work-item-detail-layout.tsx`

Props:
```typescript
interface WorkItemDetailLayoutProps {
  workItemId: string
  threadId: string       // element thread for this work item
  children: React.ReactNode  // content panel slot
}
```

- [x] [RED] Write component tests: 10 tests — desktop both panels, resize divider, drag persists, reads localStorage, mobile tab switcher, default chat tab, tab switch, no divider mobile, keyboard ArrowRight/Left (→ `__tests__/components/detail/work-item-detail-layout.test.tsx`)
- [x] [GREEN] Implement `WorkItemDetailLayout`: `components/detail/work-item-detail-layout.tsx` — desktop flex + drag divider + localStorage persist; mobile tab switcher
- [x] [GREEN] Implement `ResizableDivider` sub-component: inline in work-item-detail-layout.tsx — cursor:col-resize, aria-label, keyboard ←/→ adjusts by 5%

### ChatPanel Integration

- [x] [GREEN] `SplitViewContext` created at `components/detail/split-view-context.tsx` — provides `highlightedSectionId` + setter; `WorkItemDetailLayout` wraps children in it
- [ ] [GREEN] ChatPanel wrapper with `onSuggestionEmitted` prop — **→ v2-carveout.md** (suggestion_card WS frame not in Dundun schema yet)
- [ ] [RED] Write tests — **→ v2-carveout.md**

### Content Panel Sync

- [x] [GREEN] `SplitViewContext` wires `highlightedSectionId` to content panel children
- [ ] [GREEN] Section pulse animation consumer — **→ v2-carveout.md** (requires EP-04 SpecificationSectionsEditor)
- [ ] [RED] Write tests — **→ v2-carveout.md**
- [ ] [GREEN] "Apply this change" in suggestion_card — **→ v2-carveout.md** (suggestion_card WS frame missing)
- [ ] [RED] Write tests — **→ v2-carveout.md**

### Integration: Work Item Detail Page

Update: `src/app/workspace/[slug]/work-items/[id]/page.tsx`

- [ ] [GREEN] Wrap existing detail page content in `WorkItemDetailLayout` — **→ v2-carveout.md** (EP-04/EP-05 slots must land first)
- [ ] [GREEN] Move `SpecificationPanel` (EP-04) + task tree (EP-05) into the content slot — **→ v2-carveout.md** (EP-04 dependency)
- [ ] [GREEN] `ConversationThread` rendered inside `ChatPanel` left panel — **→ v2-carveout.md**
- [ ] [RED] Test: detail page on desktop renders `WorkItemDetailLayout` — **→ v2-carveout.md**

### Acceptance Criteria — WorkItemDetailLayout

WHEN a user opens a work item detail page on a desktop viewport (≥768px)
THEN `ChatPanel` is visible at the left side at 40% default width (or persisted width)
AND the content panel (spec + tasks) is visible at the right side simultaneously

WHEN the user drags the divider to a new position
THEN the new width persists in `localStorage` under key `split-view:chat-width`
AND on the next page load the divider starts at the saved position

WHEN the viewport is <768px
THEN a "Chat" tab and a "Content" tab are rendered at the top of the page
AND only one panel is visible at a time
AND no bottom sheet is used for the chat panel on mobile

WHEN SSE delivers a `suggestion_card` message in the chat panel
THEN the content panel scrolls to the affected section
AND that section is highlighted with a blue pulse animation for 3 seconds

WHEN the user clicks "Apply this change" in a chat suggestion card
THEN `applySuggestions()` is called with the accepted suggestion IDs
AND the content panel updates inline without a page reload
AND the pulse animation resolves on the updated section

---

## Definition of Done

- [x] All component tests pass — 1096 tests passing (156 test files) as of 2026-04-18
- [x] `tsc --noEmit` — no new errors introduced; 7 pre-existing errors in hierarchy (unrelated to EP-03)
- [ ] Zod schemas validate all API responses at runtime — **→ v2-carveout.md** (not in EP-03 scope per design.md)
- [x] WebSocket closed on component unmount — ChatPanel useEffect cleanup closes WS
- [x] Suggestion apply: 409 conflict handled — `SuggestionBatchCard` shows conflict banner + Regenerate button
- [x] Quick action undo: countdown functional, clears on unmount — QuickActionMenu with 10s setTimeout
- [x] Gap panel shows blocking before warnings; AI badge on llm-sourced gaps — GapPanel severity sort implemented

**Status: COMPLETED** (2026-04-18)
