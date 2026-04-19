# EP-22 — Technical Design: Chat-first Capture Flow

> Proposal: `tasks/EP-22/proposal.md`. The 5 decisions there are closed — this document only designs the implementation. No re-negotiation.

> **⚠ CONTRACT v2 (2026-04-18):** The "ConversationSignals extension with `suggested_sections`" described below is **superseded**. Real Dundun-Morpheo returns a `MorpheoResponse` envelope as a JSON-string inside `frame.response`, discriminated by `kind ∈ {question, section_suggestion, po_review, error}`. See `specs/suggestion-bridge/spec.md` (v2) for the authoritative contract. Sections 3 & 4 below (Chat proxy extension + ConversationSignals schema) describe v1 and are kept for history; treat them as deprecated.

---

## 1. Architecture Overview

EP-22 is predominantly wiring. The building blocks already exist:

- `WorkItemDetailLayout` (EP-03 extension) — split view ready
- `ChatPanel` — WS-backed chat
- `SplitViewContext` — pub/sub point between chat and content panels
- `SpecificationSectionsEditor` (EP-04) — editable section grid
- `ConversationService` / `DundunClient` (EP-03) — Dundun proxy
- `EventBus` + `WorkItemCreatedEvent` (EP-01/07) — subscriber plumbing
- `DiffHunk` (EP-07) — diff viewer reusable for the pending-suggestion UX

Three new cross-cutting components are needed:

1. A **backend event subscriber** that primes a Dundun thread with `original_input` when a work item is created.
2. A **chat proxy extension** that attaches a server-authoritative `context.sections_snapshot` to every outbound chat frame and validates + forwards `signals.suggested_sections` on inbound response frames.
3. A **frontend suggestion bridge** inside `SpecificationSectionsEditor` that renders a pending-suggestion diff card (Accept / Reject / Edit) wired through `SplitViewContext`.

A cross-repo change in **Dundun** extends `ConversationSignals` with a `suggested_sections` list and updates the agent prompt(s) to emit it when applicable.

```
             ┌───────────────────────┐        ┌─────────────────────────────────────────┐
             │    FE (Next.js)       │        │                 BE (FastAPI)            │
             │                       │        │                                         │
             │  items/[id]/page.tsx  │        │  POST /work-items                       │
             │    └── WorkItemDetailLayout    │    └── WorkItemService.create()         │
             │         ├── ChatPanel (left)   │         └── emit(WorkItemCreatedEvent)  │
             │         │    ▲       │        │                │                         │
             │         │    │ WS    │        │                ▼                         │
             │         │    ▼       │        │   ChatPrimerSubscriber                   │
             │         │  /ws/conversations/{thread_id}        │                         │
             │         │    ├─ outbound → frame.context.sections_snapshot attached     │
             │         │    └─ inbound  ← signals.suggested_sections forwarded         │
             │         └── SpecificationSectionsEditor (right) │                         │
             │              └── PendingSuggestionCard (diff + Accept/Reject/Edit)      │
             └───────────────────────┘        └─────────────────────────────────────────┘
                                                             │
                                                             ▼
                                                     ┌──────────────┐
                                                     │   Dundun     │
                                                     │  (WS chat +  │
                                                     │  prompts)    │
                                                     └──────────────┘
```

---

## 2. Backend: `WorkItemCreatedEvent` primer subscriber

### 2.1 Location

`backend/app/application/events/chat_primer_subscriber.py` — follows the pattern of `timeline_subscriber.py` and `notification_subscriber.py` (existing).

### 2.2 Responsibilities

On `WorkItemCreatedEvent`:

1. Fast-exit if `original_input` is None, empty, or whitespace-only.
2. Call `ConversationService.get_or_create_thread(workspace_id=event.workspace_id, user_id=event.creator_id, work_item_id=event.work_item_id)` — idempotent, always returns an `active` thread.
3. Guard against duplicate primers via a new column `primer_sent_at` on `conversation_threads`:
   - If `primer_sent_at is not None`, skip.
   - Otherwise send `original_input` as a user message to Dundun (HTTP `invoke_agent(agent="chat", ...)` or, once WS is available, a one-shot WS send). Then update `primer_sent_at = now()`.
4. Log structured outcome (event_id, thread_id, work_item_id, primer length).

The subscriber is fire-and-forget: the existing `EventBus.emit` already swallows handler exceptions and logs them. Creation never rolls back because of a Dundun outage.

### 2.3 Reading `original_input`

The event does not carry `original_input` today. Two options:

| Option | Pros | Cons |
|---|---|---|
| A. Add `original_input` to `WorkItemCreatedEvent` | No extra DB query | Mutates a cross-cutting event dataclass; all existing subscribers recompile |
| B. Load the work item inside the subscriber via `IWorkItemRepository.get(event.work_item_id)` | Event stays minimal; subscriber owns its data | One extra SELECT per creation |

**Decision**: Option B. The event stays pure lifecycle metadata. Load the row — one indexed PK lookup is a negligible cost, and keeps the event shape stable for EP-01/07 subscribers.

### 2.4 Idempotency

`conversation_threads` gains:

```sql
ALTER TABLE conversation_threads
    ADD COLUMN primer_sent_at TIMESTAMPTZ;
```

The subscriber does:

```
SELECT id, primer_sent_at FROM conversation_threads WHERE id = ? FOR UPDATE;
IF primer_sent_at IS NOT NULL: skip.
ELSE: send to Dundun, UPDATE conversation_threads SET primer_sent_at = now() WHERE id = ?;
```

The `FOR UPDATE` lock serialises concurrent handler invocations (rare but possible on retry). Success of the update commits the "primer has been sent" fact even if the FE later disagrees — this is the honest trade-off (no ghost duplicate primers).

### 2.5 Failure mode

| Failure | Behavior |
|---|---|
| Dundun HTTP 5xx / timeout | Log error with event_id; do NOT update `primer_sent_at`; next emit for the same event (or next access that resurrects the path) can retry. No user-visible error on creation. |
| Thread creation conflict (race vs FE creating the thread) | `get_or_create_thread` is idempotent. Continue. |
| Duplicate event delivery | `primer_sent_at` guard blocks the second send. |

### 2.6 Registration

In `backend/app/application/events/register_subscribers.py` (existing), add:

```
bus.subscribe(WorkItemCreatedEvent, chat_primer_subscriber.handle)
```

Subscriber handle accepts the bus + a factory for `ConversationService` + `DundunClient` + `IWorkItemRepository` + `IConversationThreadRepository`, mirroring the `timeline_subscriber.register_timeline_subscribers` signature.

---

## 3. Backend: outbound chat proxy — `context.sections_snapshot`

### 3.1 WS proxy location

`backend/app/presentation/controllers/conversation_controller.py` — `_pump.fe_to_upstream`. Currently it `websocket.receive_json()` and forwards verbatim via `upstream.send(msg)`.

### 3.2 New behavior

Before forwarding a client frame upstream:

1. If the frame has `type == "message"`, compute the authoritative snapshot:

   ```
   sections = ISectionRepository.get_by_work_item(thread.work_item_id)
   snapshot = { s.section_type.value: s.content for s in sections }
   msg["context"] = { **msg.get("context", {}), "sections_snapshot": snapshot }
   ```

2. Forward the enriched frame.
3. If `thread.work_item_id is None` (general thread), skip — send the frame verbatim.

The FE may include its own `context.sections_snapshot` (for its own observability / optimistic behavior); the BE ignores / overrides it. The server is the source of truth.

### 3.3 Payload shape sent to Dundun

```json
{
  "type": "message",
  "content": "<user text>",
  "context": {
    "sections_snapshot": {
      "problem_statement": "...",
      "acceptance_criteria": "...",
      "stakeholders": "..."
    }
  }
}
```

Keyed by `section_type` string (stable) — NOT by `section_id` (row UUID, meaningless across items).

### 3.4 Size observability

Log `sections_snapshot_bytes` on each forward (debug level for small, warn when >50KB). The threshold informs the future migration to diff-based transport (decision #3 deferred).

### 3.5 Dundun repo change required

Update the Dundun chat agent prompt to acknowledge and use `context.sections_snapshot` as the live preview context. See §9 "Cross-repo dependency on Dundun".

---

## 4. Backend: inbound `signals.suggested_sections` validation and forward

### 4.1 Schema — Pydantic model on BE side (mirrors Dundun's)

`backend/app/presentation/schemas/dundun_signals.py` — new module:

```python
class SuggestedSection(BaseModel):
    section_type: str = Field(min_length=1, max_length=64)
    proposed_content: str = Field(min_length=1, max_length=20_000)
    rationale: str = Field(default="", max_length=2_000)

    @field_validator("section_type")
    @classmethod
    def _normalise_type(cls, v: str) -> str:
        return v.strip().lower()


class ConversationSignalsWire(BaseModel):
    """What we forward to the FE. Superset of Dundun's ConversationSignals."""
    conversation_ended: bool = False
    suggested_sections: list[SuggestedSection] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")  # tolerate future fields added by Dundun
```

Validation rules:

- `section_type`: non-empty, ≤64 chars, normalised to lower-case. No per-type-template cross-check on BE (FE drops unknown types — see §5).
- `proposed_content`: required, non-empty, ≤20 KB. Protects against runaway LLM output.
- `rationale`: optional, ≤2 KB.
- Individual entries that fail validation are dropped; survivors are forwarded. A completely invalid list produces `suggested_sections: []` (field always present).

### 4.2 Interception point

In `conversation_controller._pump.upstream_to_fe`:

```python
while True:
    frame = await upstream.receive()
    if frame is None: break
    if frame.get("type") == "response":
        frame["signals"] = _validate_signals(frame.get("signals", {}))
    await websocket.send_json(frame)
```

`_validate_signals` is a pure function that:
1. Parses `signals` through `ConversationSignalsWire.model_validate(raw, strict=False)`.
2. On item-level validation error, drops the item and logs a warning.
3. On top-level model error, returns `{ "conversation_ended": False, "suggested_sections": [] }`.
4. Always returns a dict.

### 4.3 Why BE validates

- Defence in depth: Dundun prompt errors could emit garbage. We don't want bad data reaching the FE.
- Security: prevents the LLM from indirectly injecting arbitrary JSON into our frontend (we constrain sizes + types).
- Observability: the BE is where we log prompt-quality signals (count of dropped items by reason).

---

## 5. Frontend: ChatPanel interception + SplitViewContext emission

### 5.1 `SplitViewContext` extension

Extend the existing context value:

```ts
export interface SplitViewContextValue {
  highlightedSectionId: string | null;
  setHighlightedSectionId: (id: string | null) => void;

  // new
  pendingSuggestions: Record<string, PendingSuggestion>; // keyed by section_type
  emitSuggestion: (sug: PendingSuggestion) => void;
  clearSuggestion: (section_type: string) => void;
}

export interface PendingSuggestion {
  section_type: string;
  proposed_content: string;
  rationale: string;
  received_at: number;  // ms since epoch, for de-dup
}
```

`WorkItemDetailLayout` manages `pendingSuggestions` state (Map keyed by `section_type`). `emitSuggestion` upserts; `clearSuggestion` deletes. Latest suggestion for a given `section_type` wins (re-emission replaces).

### 5.2 `ChatPanel` interception

Inside the WS `onmessage` handler, after handling `type === "response"`:

```ts
if (frame.type === 'response' && frame.signals?.suggested_sections?.length) {
  for (const sug of frame.signals.suggested_sections) {
    splitView.emitSuggestion({
      section_type: sug.section_type,
      proposed_content: sug.proposed_content,
      rationale: sug.rationale,
      received_at: Date.now(),
    });
  }
  // Also set highlight to the first suggestion's section (by section_type → section_id lookup)
  splitView.setHighlightedSectionId(/* first */);
}
```

FE also drops items whose `section_type` is not in the current work item's template (unknown section_types produce no effect).

### 5.3 `SpecificationSectionsEditor` consumption

`SectionRow` gains a subscription to `useSplitView().pendingSuggestions[section.section_type]`:

- If present and the component is not in `Edit` dismissal state: render `<PendingSuggestionCard>` above the textarea with:
  - A diff view (EP-07 `DiffHunk`) comparing `section.content` (committed) vs `suggestion.proposed_content`.
  - The `rationale` text.
  - Three buttons: `Aceptar`, `Rechazar`, `Editar`.

- On Accept: call `onSave(section.id, suggestion.proposed_content)` (existing hook), then `splitView.clearSuggestion(section.section_type)`.
- On Reject: just `clearSuggestion(section.section_type)`. No network call.
- On Edit: `setValue(suggestion.proposed_content)` in local state, focus the textarea, `clearSuggestion(section.section_type)`. The existing debounce handles save.

### 5.4 Conflict with concurrent user edits

When `pendingSuggestion` arrives and the textarea has focus OR `value !== section.content` (user is mid-edit):

- Do NOT replace the editor.
- Render a non-blocking banner above the card: "Dundun propuso un cambio mientras escribías — ver propuesta".
- Clicking the banner renders the diff view comparing `value` (local buffer) vs `proposed_content`.
- Accept / Edit / Reject proceed as above.
- Last-write-wins: the EP-04 autosave path remains unchanged; if the autosave commits first, Accept will commit the proposal on top, creating a new version.

### 5.5 No persistence of suggestions

Pending suggestions live only in FE context memory. Reload = lost. This is intentional per EP-22 scope: suggestions are ephemeral UX state, not a domain entity.

---

## 6. Outbound `ChatPanel.sendMessage` payload

On `handleSend`:

```ts
const sectionsSnapshot: Record<string, string> = Object.fromEntries(
  sections.map(s => [s.section_type, valueBuffersRef.current[s.id] ?? s.content])
);

wsRef.current.send(JSON.stringify({
  type: 'message',
  content: text,
  context: { sections_snapshot: sectionsSnapshot },
}));
```

Notes:
- The FE's snapshot is informational; the BE overrides with the authoritative `work_item_sections` state before forwarding upstream. Including it FE-side is only for parity with the future Dundun-fake implementation and for observability.
- `sections` comes from the existing `use-sections` cache (React Query). Reading it inside `ChatPanel` requires either (a) passing it via `SplitViewContext` or (b) a separate `useSections(workItemId)` call. Option (a) avoids a duplicate query.

---

## 7. Clarificación tab removal — migration

### 7.1 Files to delete

- `frontend/components/clarification/clarification-tab.tsx` — the component itself.
- `frontend/components/clarification/__tests__/clarification-tab.test.tsx` (if exists).
- All references in `items/[id]/page.tsx`.

### 7.2 Files to update

- `frontend/app/workspace/[slug]/items/[id]/page.tsx` — replace entire `<Tabs>` structure with `<WorkItemDetailLayout>` wrapping:
  - The remaining tabs (Especificación, Tareas, Revisiones, Comentarios, Historial, Versiones, Sub-items, Auditoría, Adjuntos) move into the right-panel content area.
  - The "Clarificación" `<TabsTrigger>` and its `<TabsContent>` block are deleted.
- Any route test fixtures or E2E specs asserting the presence of the Clarificación tab get updated or deleted.

### 7.3 Routes

No URL changes. The detail page URL is unchanged (`/workspace/{slug}/items/{id}`). There was no `?tab=clarificacion` query-param deep-link (grep confirms), so no redirect handling is needed.

### 7.4 Backend surface

None. The Clarificación tab was purely a FE composition over EP-03 APIs that already serve `ChatPanel`. No endpoint is deprecated.

---

## 8. Collapse state persistence

**Decision**: localStorage, keyed by `(workItemId)`, scoped to the browser+device. Reasoning:

- No cross-device sync requirement in scope (proposal lists this as "not risky, minor storage").
- A per-user DB column would require a backend write on every collapse toggle, new endpoint surface, and cross-device sync semantics we don't need.
- The existing split-view width is already persisted in localStorage (`split-view:chat-width`) — a consistent pattern.

Key: `split-view:chat-collapsed:{workItemId}` with value `"1"` (collapsed) or absent (expanded).

Read on mount of `WorkItemDetailLayout`; write on collapse/expand. Failure to read/write localStorage (private mode, SSR) defaults to expanded.

### Alternatives Considered

- **DB column** on `workspace_memberships` or `work_items` — rejected. Wrong layer for device-scoped UX state. Adds write amplification.
- **User profile JSON** — also rejected for the same reason.
- **Cookie** — rejected. Cookies are sent on every request; wasteful for ≥10^3 items.

---

## 9. Cross-repo dependency on Dundun

### 9.1 `ConversationSignals` extension

`/home/david/Workspace_Tuio/agents_workspace/dundun/src/dundun/temporal/shared/entities/callback.py`:

```python
class SuggestedSection(BaseModel):
    section_type: str
    proposed_content: str
    rationale: str = ""


class ConversationSignals(BaseModel):
    conversation_ended: bool = False
    suggested_sections: list[SuggestedSection] = []
```

The default empty list means any Dundun agent that hasn't been updated still emits valid (empty) signals — zero backward-compat risk.

### 9.2 Prompt update

Agent prompt(s) in `dundun/src/dundun/prompts/` must be updated so that when the agent's response includes per-section recommendations, it fills `suggested_sections` with one entry per targeted section, with the proposed new content and a short rationale. Exact prompt wording is owned by the Dundun team; minimum requirement: JSON structure is present and valid per the Pydantic model above.

### 9.3 WS emission

`chat_websocket.py` already emits `result.signals.model_dump()` in the `response` frame. No change needed — the extension is picked up automatically.

### 9.4 Release ordering

- Dundun PR #1: add `suggested_sections` to `ConversationSignals`. Ships first, is backward-compatible (empty list default).
- Our BE: can ship the proxy forwarding code before Dundun's prompt update ships — we just forward empty lists until Dundun starts emitting.
- Dundun PR #2: update prompt to actually emit suggestions. Ships after FE is ready to receive.

This sequencing means FE does not wait on Dundun for MVP merge.

---

## 10. Data Model Changes

### 10.1 `conversation_threads`

```sql
ALTER TABLE conversation_threads
    ADD COLUMN primer_sent_at TIMESTAMPTZ NULL;

CREATE INDEX idx_conversation_threads_primer_not_sent
    ON conversation_threads (id)
    WHERE primer_sent_at IS NULL;
```

The partial index is cheap and only matters for the retry path. No data migration — existing threads leave `primer_sent_at = NULL` (they won't be retroactively primed; only new creations trigger the subscriber).

### 10.2 No new tables

Suggestions are ephemeral FE state. `assistant_suggestions` (EP-03) is NOT used for the new flow — it models a different interaction (explicit user-initiated suggestion-set generation). Mixing the two would create semantic drift. Both can coexist.

---

## 11. API Changes

No new HTTP endpoints. No changes to existing endpoint request/response shapes.

WS frame changes:
- Outbound client → BE: gains optional `context.sections_snapshot` (BE overrides on forward).
- Inbound Dundun → FE: `response.signals.suggested_sections` (new field, default `[]`).

---

## 12. Frontend Component Design

```
app/workspace/[slug]/items/[id]/page.tsx
  └── WorkItemDetailLayout
        ├── ChatPanel (left, collapsible, per-item persistence)
        │     ├── intercepts signals.suggested_sections → splitView.emitSuggestion(...)
        │     └── sendMessage attaches { context.sections_snapshot }
        └── Right-panel content router
              ├── Especificación (default)
              │     └── SpecificationSectionsEditor
              │           ├── SectionRow (existing)
              │           └── PendingSuggestionCard (new) — DiffHunk + Accept/Reject/Edit
              ├── Tareas
              ├── Revisiones
              ├── Comentarios
              ├── Historial
              ├── Versiones (canEdit)
              ├── Sub-items
              ├── Auditoría (canEdit)
              └── Adjuntos
```

`PendingSuggestionCard`: new component at `frontend/components/work-item/pending-suggestion-card.tsx`.

Props:
```ts
interface PendingSuggestionCardProps {
  currentContent: string;
  proposedContent: string;
  rationale: string;
  onAccept: () => void | Promise<void>;
  onReject: () => void;
  onEdit: () => void;
  conflictMode?: boolean;  // user was mid-edit
}
```

Imports `DiffHunk` from EP-07.

---

## 13. Test Strategy

### 13.1 Backend

| Layer | Tests |
|---|---|
| Domain | `SuggestedSection` / `ConversationSignalsWire` Pydantic model: valid + invalid + oversize + missing fields (≥6 cases). Triangulation. |
| Application | `ChatPrimerSubscriber.handle`: (a) non-empty input sends primer once, (b) empty input skips, (c) whitespace-only skips, (d) `primer_sent_at` guard prevents duplicate, (e) Dundun failure doesn't crash, (f) `work_item` not found silently skips with log. Fakes for `DundunClient` and repos. |
| Application | `ConversationService`: unchanged behavior plus new unit test asserting `get_or_create_thread` is used by the subscriber (via the fake bus). |
| Integration | `test_conversation_ws_snapshot.py`: BE-side WS proxy override of `context.sections_snapshot` with fake Dundun + fake section repo. |
| Integration | `test_conversation_ws_signals.py`: inbound `suggested_sections` validated, malformed entries dropped, valid ones forwarded. |
| Integration | `test_work_item_creation_primes_dundun.py`: end-to-end through `POST /work-items` → event bus → subscriber → fake Dundun receives primer. |

### 13.2 Frontend

| Layer | Tests |
|---|---|
| Component | `SplitViewContext` emit/clear/re-emit logic (unit). |
| Component | `ChatPanel` WS interception: `response` frame with `suggested_sections` calls `emitSuggestion`; with empty list does not; malformed frame is ignored. |
| Component | `ChatPanel.sendMessage` outbound payload shape: contains `context.sections_snapshot` from the sections cache. |
| Component | `PendingSuggestionCard` renders diff, shows rationale, Accept/Reject/Edit handlers. |
| Component | `SpecificationSectionsEditor` integration: pending suggestion mounts card above affected section; conflict mode renders banner; accept/reject/edit paths. |
| Component | `WorkItemDetailLayout` collapse control persists per-item. |
| Page | `items/[id]/page.tsx`: renders `WorkItemDetailLayout`; Clarificación tab absent in all states. |

Follow `useFakes over mocks` (project rule): inject `DundunClientFake`, `SectionRepositoryFake`, `ConversationThreadRepositoryFake`.

---

## 14. Alternatives Considered

### 14.1 New WS frame `type: "suggestion"`

Rejected. Decision #1 is closed — extend `ConversationSignals`. A new frame type adds protocol complexity for no gain; `signals` already models "out-of-band state about this response" semantically correctly.

### 14.2 Persist suggestions in `assistant_suggestions`

Rejected. That table models explicit user-triggered batch generation (`POST /work-items/{id}/suggestion-sets`). EP-22 suggestions are a reactive, single-turn, ephemeral UX affordance. Reusing the table would conflate two lifecycles and force users to explicitly "reject" every passing suggestion or see them expire. Ephemeral FE state is the right scope.

### 14.3 Diff-based `sections_snapshot` transport

Deferred (decision #3). Full snapshot is the MVP; observability (logged byte size) will tell us when to optimise.

### 14.4 Per-user DB collapse state

Rejected. UX device-local state; no cross-device requirement; would add a write endpoint for a toggle.

### 14.5 Sending `original_input` as an explicit "system/primer" bubble type

Rejected. Decision #2 is closed — visible user bubble, indistinguishable. Adding a distinct bubble kind would surface Dundun-side implementation details to the user and make the UX inconsistent with a normal conversation.

### 14.6 Keeping the Clarificación tab as a deep-link

Rejected. Decision #4 is closed. No deep-links exist today (audited via grep). Keeping a stub route would add dead code for no user value.

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Dundun prompt emits malformed `suggested_sections` | BE Pydantic validation with per-item drop; warn-level log for observability. |
| `sections_snapshot` too large on big items | Log size; alert threshold 50KB; optimisation (diff) deferred to a follow-up once data is available. |
| Race: user editing section while suggestion arrives | Banner + diff-against-local-buffer pattern; last-write-wins; EP-04 autosave unchanged. |
| Cross-repo sequencing | Backward-compatible Dundun PR order (schema → prompt); BE + FE ship with empty-list safe default. |
| Subscriber failure blocks creation | Fire-and-forget via existing EventBus; primer retry possible via `primer_sent_at IS NULL` guard. |
| Primer re-delivery duplicates message in Dundun | `primer_sent_at` column + `FOR UPDATE` row lock in subscriber. |
| Clarificación tab removal breaks tests | Inventory all test fixtures in Phase 0 of the FE plan; update/delete in the same PR. |
| Collapse state lost in private browsing | Acceptable per scope; default to expanded. |

---

## 16. Layer Mapping Summary

| Concern | Layer | File(s) |
|---|---|---|
| `WorkItemCreatedEvent` emission (unchanged) | Application (existing) | `application/services/work_item_service.py` |
| Primer subscriber | Application | `application/events/chat_primer_subscriber.py` (new), `application/events/register_subscribers.py` (append) |
| `primer_sent_at` column | Infrastructure / migrations | `backend/alembic/versions/0118_*.py` (new) |
| `ConversationSignalsWire` schema | Presentation (schema) | `presentation/schemas/dundun_signals.py` (new) |
| WS proxy snapshot + signals interception | Presentation (controller) | `presentation/controllers/conversation_controller.py` (extend `_pump`) |
| Section snapshot read for outbound | Application | new helper `ConversationService.build_sections_snapshot(work_item_id)` OR inline in controller using `ISectionRepository` |
| Detail page wiring | FE (page) | `frontend/app/workspace/[slug]/items/[id]/page.tsx` |
| SplitViewContext extension | FE (state) | `frontend/components/detail/split-view-context.tsx` |
| ChatPanel interception | FE (component) | `frontend/components/clarification/chat-panel.tsx` |
| PendingSuggestionCard | FE (component) | `frontend/components/work-item/pending-suggestion-card.tsx` (new) |
| Section editor consumption | FE (component) | `frontend/components/work-item/specification-sections-editor.tsx` |
| Collapse state | FE (component) | `frontend/components/detail/work-item-detail-layout.tsx` |
| Clarificación tab removal | FE (page + component) | `frontend/app/workspace/[slug]/items/[id]/page.tsx`, delete `frontend/components/clarification/clarification-tab.tsx` |
| Dundun `ConversationSignals` | Dundun repo | `dundun/src/dundun/temporal/shared/entities/callback.py` |
| Dundun agent prompt | Dundun repo | `dundun/src/dundun/prompts/*` |
