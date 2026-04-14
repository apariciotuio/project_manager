# EP-03 Frontend Tasks — Clarification, Conversation & Assisted Actions (Dundun proxy)

Branch: `feature/ep-03-frontend`
Refs: EP-03
Depends on: EP-00 frontend, EP-01 frontend (WorkItem types), EP-03 backend API

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

- [ ] Implement `src/types/conversation.ts`: `ConversationThread`, `ConversationMessage`, `MessageType`, `AuthorType` — all typed exactly as above
- [ ] Implement `src/types/suggestion.ts`: `SuggestionSet`, `SuggestionItem`, `SuggestionStatus`
- [ ] Implement `src/types/gap.ts`: `GapFinding`, `GapReport` (`{ work_item_id, findings, score }`)

---

## Phase 2 — API Client Functions

File: `src/lib/api/conversation.ts`, `src/lib/api/suggestions.ts`, `src/lib/api/gaps.ts`

- [ ] Implement `getThreads(workItemId?: string, type?: 'element' | 'general'): Promise<ConversationThread[]>`
- [ ] Implement `createThread(data): Promise<ConversationThread>`
- [ ] Implement `getThread(threadId: string, page: number): Promise<{ thread: ConversationThread, messages: ConversationMessage[], total: number }>`
- [ ] Implement `sendMessage(threadId: string, content: string): Promise<{ message_id: string }>`
- [ ] Implement `archiveThread(threadId: string): Promise<void>`
- [ ] Implement `triggerAiReview(workItemId: string): Promise<{ job_id: string }>`
- [ ] Implement `getGapQuestions(workItemId: string): Promise<GapFinding[]>`
- [ ] Implement `generateSuggestionSet(workItemId: string): Promise<{ set_id: string }>`
- [ ] Implement `getSuggestionSet(setId: string): Promise<SuggestionSet>`
- [ ] Implement `applySuggestions(setId: string, acceptedItemIds: string[]): Promise<{ new_version: number, applied_sections: string[] }>`
- [ ] Implement `executeQuickAction(workItemId: string, section: string, action: string): Promise<{ action_id: string, result: string }>`
- [ ] Implement `undoQuickAction(workItemId: string, actionId: string): Promise<void>`
- [ ] Implement SSE stream client in `src/lib/api/sse-client.ts`: `streamThread(threadId, onToken, onDone, onError): () => void` — returns cleanup function that closes `EventSource`. **Use shared `useSSE(channel, onMessage)` hook from `src/lib/sse.ts` (owned by EP-12). Do not implement a standalone EventSource directly.**
- [ ] [RED] Write unit tests using MSW: `sendMessage` happy path, `applySuggestions` happy path and 409 throws `VersionConflictError`, SSE client calls `onToken` per event and `onDone` on done event

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

- [ ] [RED] Write component tests:
  - Renders blocking gaps with red indicator, warnings with yellow
  - Shows completeness score percentage
  - "Run AI Review" button triggers `triggerAiReview()` and shows loading state
  - After AI review triggered, shows "Review in progress..." status
  - Dismissible: each gap has dismiss button (client-side dismiss, not persisted)
  - Dundun-sourced gaps labeled "AI" badge; rule-based gaps labeled "Rule" badge
- [ ] [GREEN] Implement `src/components/clarification/gap-panel.tsx`:
  - Fetches gap findings via `getGapQuestions(workItemId)` using React Query
  - Groups: blocking first, then warnings, then info
  - "Run AI Review" calls `triggerAiReview()` then waits for an SSE event on the work-item channel (EP-08) signalling that `/api/v1/dundun/callback` has written new findings
  - Error state: "Gap analysis unavailable" with retry

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

## Phase 4 — ClarificationQuestion Component

Component: `src/components/clarification/clarification-question.tsx`

Props:
```typescript
interface ClarificationQuestionProps {
  finding: GapFinding
  onAnswered: (dimension: string) => void
  onSkip: () => void
}
```

- [ ] [RED] Write component tests: renders question text, submit button disabled when answer empty, skip dismisses question, calling `onAnswered` after submit
- [ ] [GREEN] Implement `ClarificationQuestion`:
  - Displays `finding.message` as the question
  - Answer textarea
  - "Submit Answer" → sends message to element thread via `sendMessage()`; on success calls `onAnswered(finding.dimension)`
  - "Skip" → calls `onSkip()` (no API call)

---

## Phase 5 — ConversationThread Component

Component: `src/components/conversation/conversation-thread.tsx`

Props:
```typescript
interface ConversationThreadProps {
  threadId: string
  workItemId?: string
}
```

- [ ] [RED] Write component tests:
  - Renders message list with user/assistant distinction
  - Streaming assistant message: appends progress frames incrementally
  - Loading skeleton on initial fetch of history
  - Error state with retry button
  - Empty state: "Start the conversation by sending a message"
  - Input textarea disabled while assistant is responding
  - Final `{"type":"response", "message_id": ...}` frame finalizes the bubble
- [ ] [GREEN] Implement `src/components/conversation/conversation-thread.tsx`:
  - History fetched via `getThreadHistory(threadId)` (delegates to Dundun) on mount
  - WebSocket via `useConversationWs(threadId)`: opens on mount, closes on unmount; reconnects with exponential backoff on transient drops
  - Streaming state: append content from `progress` frames to the last assistant bubble
  - Auto-scroll to bottom on new frame
- [ ] [GREEN] Implement `MessageComposer` sub-component: textarea, send button, Ctrl+Enter to submit; disabled when `isStreaming = true`

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

## Phase 6 — SuggestionPreviewPanel Component

Component: `src/components/suggestions/suggestion-preview-panel.tsx`

Props:
```typescript
interface SuggestionPreviewPanelProps {
  suggestionSet: SuggestionSet
  onApplied: (result: { new_version: number, applied_sections: string[] }) => void
  onDismiss: () => void
}
```

- [ ] [RED] Write component tests:
  - Renders one card per `SuggestionItem`
  - Each card shows `current_content` vs `proposed_content` as diff view
  - Individual accept/reject per item
  - "Apply Selected" button disabled until at least one item accepted
  - "Apply Selected" disabled when set is expired
  - Submit calls `applySuggestions()` with accepted item IDs only
  - 409 conflict: shows "Content changed since suggestions were generated. Regenerate?" banner
  - Expired set: shows "These suggestions have expired" with "Generate new" button
- [ ] [GREEN] Implement `SuggestionPreviewPanel`:
  - Diff display: side-by-side or inline diff using simple string comparison (no diff library needed — highlight entire proposed block) ⚠️ originally MVP-scoped — see decisions_pending.md
  - Accept/reject per item via local state (not API call per toggle)
  - Single "Apply Selected" API call with all accepted IDs
  - Version conflict (409): inline conflict banner, "Regenerate" calls `generateSuggestionSet()`
  - On successful apply: invalidate `['workItem', workItemId]`, `['sections', workItemId]`, `['completeness', workItemId]`, `['versions', workItemId]`, `['timeline', workItemId]`
- [ ] [GREEN] Implement `SuggestionDiffCard` sub-component: section label, current content (strikethrough area), proposed content (highlighted area), accept/reject toggle buttons

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

- [ ] [RED] Write component tests:
  - Renders only applicable actions for the given section type
  - Loading spinner replaces action buttons during execution
  - "Undo" toast appears on success with countdown (10s)
  - Undo button calls `undoQuickAction()` before countdown expires
  - After 10s countdown expires, undo toast disappears
  - Empty `sectionContent` disables all actions (nothing to act on)
- [ ] [GREEN] Implement `QuickActionMenu`:
  - Dropdown or inline button group
  - On action click: calls `executeQuickAction()`, shows spinner, on success calls `onActionApplied(result)`
  - Undo toast: uses `setTimeout` for 10s countdown; cleanup on unmount
  - Error state: inline error message per action failure

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

- [ ] Add `GapPanel` to detail page sidebar
- [ ] Add `ConversationThread` panel below the main content area (element thread for this work item)
- [ ] Add "Get Suggestions" button: calls `generateSuggestionSet()`, shows loading, renders `SuggestionPreviewPanel` when set is ready
- [ ] Add `QuickActionMenu` to each section editor (will be used fully in EP-04; stub the integration point here)
- [ ] Polling for suggestion set completion: poll `getSuggestionSet(set_id)` every 2s while status is `pending`; stop polling when status changes; show loading skeleton on `SuggestionPreviewPanel` while pending
  - **Progress indicator stages**: first 2s show spinner only; after 2s switch to text cycling through "Analyzing…", "Generating suggestions…", "Almost done…" (4s per stage)
  - **Soft timeout at 20s**: show "Taking longer than usual" message alongside progress text; do not cancel
  - **Hard timeout at 45s**: cancel polling, show error state "Generation timed out" with "Retry" button that re-calls `generateSuggestionSet()` and resets progress
  - Acceptance criteria:
    - WHEN suggestion generation exceeds 20s THEN "Taking longer than usual" message appears alongside the progress text
    - WHEN suggestion generation exceeds 45s THEN timeout error state appears with Retry button; polling stops
    - WHEN Retry is clicked THEN a new generation job starts and progress indicator resets to initial state
- [ ] [RED] Write component tests: spinner shows at 0s, progress text shows after 2s, soft timeout message at 20s, hard timeout error at 45s, Retry re-triggers generation, polling stops on hard timeout

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

- [ ] [RED] Write component tests:
  - Desktop (≥768px): renders both `ChatPanel` (left) and content panel (right) simultaneously
  - Desktop: `ChatPanel` default width is 40% of container
  - Desktop: resizable divider is rendered and draggable
  - Desktop: after drag, new width is persisted to `localStorage` under key `split-view:chat-width`
  - Desktop: on next render, persisted width is read from `localStorage` and applied
  - Mobile (<768px): only tab switcher renders at top — no simultaneous panel display
  - Mobile: default active tab is "Chat"; "Content" tab switches to content panel
  - Mobile: `ChatPanel` is NOT rendered as a bottom sheet on mobile
  - Mobile: no horizontal overflow at 375px viewport
- [ ] [GREEN] Implement `WorkItemDetailLayout`:
  - Desktop: flex layout, left = `ChatPanel` (default 40% width, min 280px, max 70%), right = content slot
  - Desktop: draggable divider using `onMouseDown` + `document.addEventListener('mousemove')` — no drag library needed; persist final width in `localStorage`
  - Mobile: render `Tabs` (Chat | Content), only one panel visible at a time; tab state in local `useState`
  - Read persisted width from `localStorage` on mount; default to 40% if key absent
- [ ] [GREEN] Implement `ResizableDivider` sub-component: vertical bar with `cursor: col-resize`, `aria-label="Resize panels"`, keyboard support (←/→ arrow keys adjust by 5%)

### ChatPanel Integration

- [ ] [GREEN] Implement `ChatPanel` wrapper in `src/components/detail/chat-panel.tsx`:
  - Wraps existing `ConversationThread` (from Phase 5 of EP-03)
  - Emits `onSuggestionEmitted(suggestionBatchId: string, sectionId: string)` when a `suggestion_card` message arrives via SSE
  - Props: `{ threadId: string; workItemId: string; onSuggestionEmitted: (batchId: string, sectionId: string) => void }`
- [ ] [RED] Write tests: `onSuggestionEmitted` fires when SSE delivers a `suggestion_card` message; `ConversationThread` rendered inside; no bottom sheet on mobile

### Content Panel Sync

- [ ] [GREEN] In `WorkItemDetailLayout`, wire `onSuggestionEmitted` → pass `highlightedSectionId` state to content panel children via React context (`SplitViewContext`)
- [ ] [GREEN] Content panel consumers read `highlightedSectionId` from `SplitViewContext`; when non-null, scroll target section into view (`scrollIntoView({ behavior: 'smooth' })`) and apply `ring-2 ring-blue-400 animate-pulse` CSS classes for 3 seconds, then remove
- [ ] [RED] Write tests:
  - When `highlightedSectionId` changes THEN affected section receives pulse animation class
  - After 3000ms THEN animation class is removed
  - When `onSuggestionEmitted` fires THEN `highlightedSectionId` is set to the emitted `sectionId`
- [ ] [GREEN] "Apply this change" button inside `suggestion_card` chat messages → calls `applySuggestions()` from existing EP-03 suggestion flow; on success, content panel re-fetches via `queryClient.invalidateQueries`
- [ ] [RED] Write tests: "Apply this change" button click calls `applySuggestions()`; content panel invalidates cache on success

### Integration: Work Item Detail Page

Update: `src/app/workspace/[slug]/work-items/[id]/page.tsx`

- [ ] [GREEN] Wrap existing detail page content in `WorkItemDetailLayout`, passing element `threadId` and `workItemId`
- [ ] [GREEN] Move `SpecificationPanel` (EP-04) + task tree (EP-05) into the content slot
- [ ] [GREEN] `ConversationThread` is rendered inside `ChatPanel` (left panel), not below main content as in Phase 8 baseline
- [ ] [RED] Test: detail page on desktop renders `WorkItemDetailLayout` with both panels; on mobile renders tab switcher

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

- [ ] All component tests pass
- [ ] `tsc --noEmit` clean (no `any` types)
- [ ] Zod schemas validate all API responses at runtime (add Zod parse in API client functions)
- [ ] SSE `EventSource` connection closed on component unmount (no memory leaks)
- [ ] Suggestion apply: 409 conflict handled gracefully with user-visible message
- [ ] Quick action undo: countdown visible and functional; undo reverses content correctly
- [ ] Gap panel shows blocking gaps before warnings; AI-sourced gaps labeled distinctly
