# Suggestion Bridge Specs — EP-22

Covers **US-223** (Dundun suggestions flow into the target section of the preview) and **US-224** (preview edits are reflected in Dundun's context on next turn).

---

## Transport summary

- Dundun extends `ConversationSignals` with a new optional field `suggested_sections: list[SuggestedSection]`. See `design.md` §"ConversationSignals schema" for the shape.
- The existing `response` WS frame `{ "type": "response", "response": "...", "signals": {...} }` carries the suggestions. No new WS frame type is introduced.
- BE validates `suggested_sections` against a Pydantic model before forwarding to FE. Invalid items are dropped silently with a warn-level log.
- Outbound chat messages from the FE carry `context.sections_snapshot`: a map `{ section_type: content }` of the current sections. BE reads from `work_item_sections` right before forwarding to Dundun.

---

## US-223: Dundun suggestions auto-populate into the target section

### Scenario: Suggestion arrives → target section enters pending mode

WHEN an assistant `response` frame arrives with `signals.suggested_sections` containing at least one valid item
AND the FE has validated the suggestion shape
THEN `ChatPanel` calls `SplitViewContext.emitSuggestion(section_type, proposed_content, rationale)`
AND the right panel scrolls smoothly to the target section
AND the section card is highlighted for 3 seconds (reuses EP-03 pulse convention)
AND the section enters "pending suggestion" mode (the proposed content is held as a pending draft, NOT committed)

---

### Scenario: Diff view rendered for a pending suggestion

WHEN a section is in pending-suggestion mode
THEN a diff view (reuses EP-07 diff viewer — `DiffHunk`) is rendered above the section's normal editor
AND the diff compares `current_content` (live committed content) against `proposed_content`
AND the rationale text is shown beneath the diff
AND three actions are visible inline: `Accept`, `Reject`, `Edit`

---

### Scenario: User accepts a pending suggestion

WHEN the user clicks `Accept` on a pending suggestion
THEN the FE calls the EP-04 section patch endpoint `PATCH /work-items/{id}/sections/{section_id}` with `{ content: proposed_content }`
AND a new section version is recorded on the backend
AND the pending-suggestion UI is dismissed
AND the section now shows the committed content (`proposed_content`) with the generation_source badge reflecting the AI origin

---

### Scenario: User rejects a pending suggestion

WHEN the user clicks `Reject`
THEN the pending-suggestion UI is dismissed with NO network call
AND the section content is unchanged
AND the suggestion is not persisted; it is lost on reload (this is intentional — suggestions are ephemeral UX state, not a separate resource in EP-22 scope)

---

### Scenario: User chooses Edit on a pending suggestion

WHEN the user clicks `Edit`
THEN the section's textarea is populated with `proposed_content` (replacing any untyped content)
AND the pending-suggestion diff view is dismissed
AND the user can freely modify the text
AND the usual EP-04 autosave debounce persists the result on blur / after 600ms of idleness

---

### Scenario: Multiple suggestions in one response

WHEN a single `response` frame carries `suggested_sections` with entries for several distinct section_types
THEN each targeted section enters pending-suggestion mode independently
AND the right panel scrolls to the first targeted section (top-down order in the list)
AND pulses only the first one
AND the others sit silently in pending-mode waiting for the user to scroll to them

---

### Scenario: Conflict with concurrent user edits on the same section

WHEN the user is actively editing section S (has focus or unsaved local changes in S)
AND a suggestion arrives targeting S
THEN the pending-suggestion UI does NOT forcibly overwrite the user's in-flight edit
AND instead renders a banner above S: "Dundun proposed a change while you were typing — view proposal"
AND WHEN the user clicks "view proposal" THEN the diff view is rendered comparing the user's current buffer against the proposal
AND Accept / Edit / Reject behave as in the primary scenarios
AND last-write-wins: if the user saves locally first (normal autosave), then accepts the proposal, the proposal commits on top of the user's save

---

### Scenario: Unknown section_type in suggestion — dropped

WHEN `suggested_sections` contains an entry with a `section_type` that does not exist in this work item's type template
THEN that entry is dropped silently on the FE
AND the valid entries are processed normally

---

### Scenario: Malformed suggestion payload — BE drops and logs

WHEN Dundun emits a `suggested_sections` list containing an item that fails Pydantic validation on the BE (missing required field, wrong type, content too long)
THEN the BE drops the offending entry before forwarding
AND a structured warn-level log is emitted with the correlation id
AND surviving valid entries are forwarded to the FE
AND if ALL entries are invalid, the `suggested_sections` field is forwarded as an empty list (NOT absent)

---

## US-224: Preview edits reflected in Dundun's context on next turn

### Scenario: Outbound message carries sections_snapshot

WHEN the user sends a message through the chat composer
THEN the FE constructs the outbound WS frame with shape
```
{ "type": "message", "content": "<user text>", "context": { "sections_snapshot": { "<section_type>": "<content>", ... } } }
```
AND the `sections_snapshot` map contains ALL current section_types of the work item (not only those edited this turn)
AND each value is the section's latest locally-buffered content (the text the user is about to "commit" / has last autosaved)

---

### Scenario: BE attaches authoritative snapshot on forward

WHEN the BE WS proxy receives an outbound frame
THEN the BE loads the current sections for this work item from `work_item_sections` via `ISectionRepository.get_by_work_item(work_item_id)`
AND overrides `frame.context.sections_snapshot` with the server-authoritative map before forwarding to Dundun
AND this prevents a stale / tampered snapshot from the FE leaking into Dundun context

---

### Scenario: No section data for a newly-created item

WHEN the user sends a message for a work item whose sections are empty or not yet provisioned
THEN the snapshot map is `{}` (empty object, NOT absent)
AND Dundun receives the empty snapshot as a valid turn

---

### Scenario: Primer message carries initial snapshot

WHEN the creation-time primer is sent (see `specs/chat-prime/spec.md`)
THEN the primer turn also carries `context.sections_snapshot` (read server-side from the sections that EP-02 pre-populated from the template)
AND Dundun sees the template-default state as the baseline for the first turn

---

### Scenario: Snapshot excludes drafts and versions — current sections only

WHEN the BE builds `sections_snapshot`
THEN the snapshot contains only the current `content` field of each row in `work_item_sections`
AND it does NOT include section version history, section drafts, or other work item fields (title, description, priority, ...)
AND the map is keyed by `section_type` (the stable domain identifier) NOT by `section_id` (which is row-scoped)

---

### Scenario: Large snapshot — no truncation for MVP

WHEN the snapshot size exceeds a soft threshold (e.g. 50KB)
THEN the BE emits a warn-level log with the size and work_item_id
AND the snapshot is forwarded in full (no truncation in EP-22 scope; diff-based transport is deferred per decision #3)
