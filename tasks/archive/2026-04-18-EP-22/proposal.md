# EP-22 — Chat-first Capture Flow

## Business Need

Creating a work item today dumps the user on a tab-based detail page with an empty chat and an editor hidden behind a tab. The capture is disconnected from the assistive layer (Dundun) — users have to re-type or paraphrase their initial input into the chat to start the clarification loop. The intended experience is **chat-first**: after a minimal creation step, the user lands on a split view where Dundun is already primed with the original input and a type-aware preview is editable on the right. Iteration happens bidirectionally — either by typing into the preview or by chatting with Dundun; what Dundun produces flows back into the preview.

## Objectives

- Minimal friction creation: `/items/new` keeps only title + type + project/parent (current form, unchanged)
- Post-create landing on a split view (chat left, preview right), not on a tabs layout
- Dundun thread is auto-primed with `original_input` as the first user message on creation — user never has to retype
- Right panel renders the type-specific template (EP-04 sections) in editable preview mode from the first render
- Dundun suggestions flow into the preview: the suggestion's target section is highlighted, the proposed content is pre-loaded into the editor, user accepts/edits/rejects inline
- SplitView is the default layout in **all** states; the "Clarificación" tab is retired (chat lives permanently in the left panel)

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-220 | Land on SplitView immediately after creation | Must |
| US-221 | Chat is primed with original_input as first message (visible user bubble) | Must |
| US-222 | Right panel shows type-specific template in editable preview | Must |
| US-223 | Dundun suggestions auto-populate into the target section of the preview | Must |
| US-224 | Preview edits are reflected in Dundun's context on next turn (full snapshot) | Should |
| US-225 | SplitView is available in every state; tab "Clarificación" is removed | Must |

## Acceptance Criteria

- WHEN a user submits the creation form THEN they are redirected to `/workspace/{slug}/items/{id}` rendered inside `WorkItemDetailLayout` (split view), not the tabs layout
- WHEN a work item is created AND has a non-empty `original_input` THEN a backend subscriber to `WorkItemCreatedEvent` posts that text as a user message to the newly-created Dundun thread and the frontend renders it as a visible user bubble in the chat
- WHEN the user opens the split view THEN the right panel renders the spec sections for the item's type (from EP-04) in editable mode, pre-populated with the template defaults from EP-02
- WHEN Dundun emits a response with structured section suggestions (via `ConversationSignals.suggested_sections`) THEN the right panel scrolls to the target section, highlights it, and pre-loads the proposed content into the editor as a pending draft (not committed)
- WHEN the user accepts a suggestion inline THEN the section content is committed via the existing EP-04 section patch endpoint and a new version is recorded
- WHEN the user edits the preview and sends a new chat message THEN the current full snapshot of section contents is sent alongside the message so Dundun has fresh context
- AND the "Clarificación" tab is removed from the detail page in all states — chat is always in the left panel
- AND SplitView is available in all workflow states (Draft, IN_CLARIFICATION, READY, IN_PROGRESS, DONE, etc.) — the user can collapse the chat panel per-item if they want a content-only view

## Technical Notes

### Backend
- New subscriber on `WorkItemCreatedEvent` → `ConversationService.get_or_create_thread` + post user message to Dundun with `original_input` as content. The message is persisted in Dundun's conversation history like any other user turn.
- New endpoint or param on the chat proxy: each user message forwarded to Dundun carries `context.sections_snapshot` — a JSON map `{section_type: content}` of the current work item's sections. BE reads from `work_item_sections` table right before forwarding.
- Extend Dundun's `ConversationSignals` (in Dundun repo) with `suggested_sections: list[{section_type: str, proposed_content: str, rationale: str}]`. Dundun's agent prompts are updated to emit these signals when the response contains per-section recommendations. Our BE forwards these signals transparently to FE in the existing `{type: "response", ..., signals}` WS frame.

### Frontend
- Wire `items/[id]/page.tsx` through `WorkItemDetailLayout` (components exist; only import + wrap missing).
- `ChatPanel` intercepts `signals.suggested_sections` from `response` frames; calls `SplitViewContext.emitSuggestion(section_type, content, rationale)`.
- `SpecificationSectionsEditor` gains a "pending suggestion" mode: shows proposed content in a diff view (reuses EP-07 diff viewer) with Accept / Reject / Edit actions inline.
- `ChatPanel.sendMessage` reads section snapshot from the work item cache and includes it in the outbound message payload (field `context.sections_snapshot`).
- Remove "Clarificación" tab from `items/[id]/page.tsx`. No replacement — the chat IS the clarification surface.
- Creation form redirect target unchanged (`/items/{id}`) — the change is what that route renders.

### Cross-repo (Dundun)
- Add `suggested_sections: list[SuggestedSection]` to `ConversationSignals` in `dundun/src/dundun/temporal/shared/entities/callback.py`.
- Update agent prompt(s) in `dundun/src/dundun/prompts/` to emit suggestions when applicable.
- No new WS frame type needed — the existing `response` frame already carries `signals`.

## Dependencies

- EP-02 (capture — done)
- EP-03 (conversation + SplitView component — done, 3 items deferred for this EP: `ChatPanel wrapper`, `Move SpecificationPanel into content slot`, `ConversationThread inside ChatPanel`)
- EP-04 (spec sections editor — done)
- EP-07 (diff viewer — reused for pending-suggestion UX)
- **Dundun repo** (add `suggested_sections` to `ConversationSignals`; prompt update)

## Complexity Assessment

**Medium** — backend subscriber is small, frontend wiring is mostly import + context plumbing. The non-trivial parts are (a) the Dundun `ConversationSignals` extension + prompt update (cross-repo) and (b) the inline diff/accept UX in the section editor.

## Decisions (closed)

1. **Suggestion transport (Q1)**: extend `ConversationSignals.suggested_sections` in Dundun. No new WS frame, no polling fallback. Dundun's signals channel is the natural extension point — `conversation_ended` already uses it. Small PR in Dundun repo.
2. **Primer message UX (Q2)**: visible user bubble. The `original_input` is sent as a real user message to Dundun; the chat renders it as a normal user turn. Transparent to Dundun's history, honest to the user.
3. **Preview-as-context (Q3)**: full snapshot every turn. Start simple — every outbound chat message carries `context.sections_snapshot`. If token cost becomes a problem, optimise to diffs later.
4. **Clarificación tab (Q4)**: removed entirely. Chat lives in the left panel in all states. No duplication, no drawer, no secondary tab.
5. **SplitView scope (Q5)**: all states. User can collapse the chat panel per-item if they want content-only. Uniform UX across the lifecycle.

## Risks

- **Dundun prompt quality**: suggestions are only as good as Dundun's prompt. If Dundun emits malformed or wrong-section suggestions, the preview surfaces garbage. Mitigation: schema-validate `suggested_sections` on BE before forwarding.
- **Token cost**: full-snapshot context every turn can bloat prompts for items with 10+ large sections. Mitigation: log payload sizes; switch to diffs if p95 > N tokens.
- **Race conditions**: user edits preview while a Dundun suggestion arrives for the same section. Mitigation: reuse EP-02 staleness pattern (warning banner, last-write-wins).
- **Cross-repo coordination**: changes needed in Dundun repo. Mitigation: PR ready before FE wiring starts; BE can forward `signals.suggested_sections` through the proxy even if Dundun hasn't shipped yet (empty list = no-op).
- **Collapse state**: needs persisting per user per item; minor storage, not risky.

## Out of Scope

- Multi-user collaborative editing in the preview (EP-17 edit locks handle the single-editor case)
- Rich-text editor upgrades (markdown textarea stays for MVP)
- Dundun agent prompt authoring beyond the minimum needed to emit `suggested_sections`
- Optimised diff-based context transport (deferred unless token cost forces it)
- Voice input, file attachments in chat (out of scope)
