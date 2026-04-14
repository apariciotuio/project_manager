# EP-03 Frontend Tasks — Clarification, Conversation & Assisted Actions

Branch: `feature/ep-03-frontend`
Refs: EP-03
Depends on: EP-00 frontend, EP-01 frontend (WorkItem types), EP-03 backend API

---

## API Contract (Blocked by: EP-03 backend)

**SSE stream:** `GET /api/v1/threads/{thread_id}/stream` — `text/event-stream`
```
event: token
data: {"content": "partial..."}

event: done
data: {"message_id": "uuid"}

event: error
data: {"code": "LLM_TIMEOUT", "message": "..."}
```

**Thread response:**
```typescript
interface ConversationThread {
  id: string
  thread_type: 'element' | 'general'
  work_item_id: string | null
  owner_user_id: string
  title: string | null
  status: 'active' | 'archived'
  created_at: string
  updated_at: string
}

interface ConversationMessage {
  id: string
  thread_id: string
  author_type: 'human' | 'assistant' | 'system'
  author_user_id: string | null
  content: string
  message_type: 'text' | 'summary' | 'system_error' | 'gap_question' | 'suggestion_card'
  token_count: number
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
  - LLM-sourced gaps labeled "AI" badge; rule-based gaps labeled "Rule" badge
- [ ] [GREEN] Implement `src/components/clarification/gap-panel.tsx`:
  - Fetches gap findings via `getGapQuestions(workItemId)` using React Query
  - Groups: blocking first, then warnings, then info
  - "Run AI Review" calls `triggerAiReview()` then polls `getSuggestionSet` or waits for SSE notification
  - Error state: "Gap analysis unavailable" with retry

### Acceptance Criteria — GapPanel

See also: specs/clarification/spec.md (US-030)

WHEN `GapPanel` renders with findings where 2 are blocking and 3 are warnings
THEN blocking findings are rendered first (red indicator)
AND warning findings follow (yellow indicator)
AND no info-severity findings are shown in the blocking section

WHEN a gap has `source = "llm"`
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
  - Renders message list with human/assistant distinction
  - Streaming assistant message: renders incrementally as tokens arrive
  - Loading skeleton on initial fetch
  - Error state with retry button
  - Empty state: "Start the conversation by sending a message"
  - Input textarea disabled while assistant is responding
  - `onDone` event from SSE appends final message with correct `message_id`
- [ ] [GREEN] Implement `src/components/conversation/conversation-thread.tsx`:
  - Message list fetched via `getThread()` (paginated, load-more at top)
  - SSE via `streamThread()`: on mount starts stream, on unmount calls cleanup function (tear down `EventSource`)
  - Streaming state: append tokens to last assistant message in local state
  - Message types: `summary` rendered differently (collapsed header); `gap_question` renders as `ClarificationQuestion`; `system_error` renders as inline error banner
  - Auto-scroll to bottom on new message
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

WHEN SSE `event: token` events arrive
THEN the partial content is appended to the last assistant message bubble incrementally
AND the message bubble does NOT re-render from scratch on each token (no flash)

WHEN SSE `event: done` arrives
THEN the streaming message's `message_id` is set to the value from the event
AND the MessageComposer is re-enabled

WHEN SSE `event: error` arrives (e.g., LLM_TIMEOUT)
THEN an inline error banner is appended as a `system_error` message type
AND the MessageComposer is re-enabled
AND a "Retry" option is shown

WHEN the component unmounts while SSE stream is active
THEN the `EventSource` is closed (cleanup function called)
AND no further state updates occur after unmount

WHEN a `summary` type message is in the list
THEN it is rendered as a collapsed "Earlier context summarised" header
AND clicking it expands to show the summary text

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
  - Diff display: side-by-side or inline diff using simple string comparison (no diff library needed at MVP — highlight entire proposed block)
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

## Definition of Done

- [ ] All component tests pass
- [ ] `tsc --noEmit` clean (no `any` types)
- [ ] Zod schemas validate all API responses at runtime (add Zod parse in API client functions)
- [ ] SSE `EventSource` connection closed on component unmount (no memory leaks)
- [ ] Suggestion apply: 409 conflict handled gracefully with user-visible message
- [ ] Quick action undo: countdown visible and functional; undo reverses content correctly
- [ ] Gap panel shows blocking gaps before warnings; AI-sourced gaps labeled distinctly
