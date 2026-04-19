# Suggestion Bridge Specs — EP-22 (v2 — real Dundun-Morpheo contract)

> **v2 supersedes the original spec** (2026-04-18). The original was built against a fictional `signals.suggested_sections` shape. Reality: Dundun-Morpheo returns a `MorpheoResponse` envelope **as a JSON string inside `frame.response`**, discriminated by `kind`. All suggestion/question/review flows are driven by that envelope.

Covers **US-223** (Dundun suggestions flow into the target section of the preview) and **US-224** (preview edits are reflected in Dundun's context on next turn). Additionally covers the companion kinds `question`, `po_review`, `error` that share the same envelope.

---

## Transport summary

- Wire frame (unchanged shape): `{ "type": "response", "response": "<JSON-string>", "signals": {"conversation_ended": bool} }`.
- **`frame.response` is a JSON-encoded string.** Consumers must `JSON.parse(frame.response)` (double-parse) to obtain a `MorpheoResponse` envelope.
- `MorpheoResponse` is a discriminated union on `kind`:
  - `question` — clarification turn. Renders as interactive prompts. No section mutations.
  - `section_suggestion` — proposal with content for N ≤ 25 sections. Drives Accept/Reject/Edit flow.
  - `po_review` — final synthesis (score + per-dimension findings + action_items). Rendered as a review panel; does not mutate sections.
  - `error` — synthesis failure. Rendered as an error banner.
- `signals` only carries `conversation_ended: bool`. **No `suggested_sections` in `signals`** (that was the fictional contract).
- Outbound frames (unchanged): `{ "type": "message", "content": string, "context": {"sections_snapshot": [...]} }`. BE overrides `sections_snapshot` with server-authoritative data before forwarding to Dundun.

---

## MorpheoResponse envelope — shapes

### kind = "question"

```json
{
  "kind": "question",
  "message": "<intro text>",
  "clarifications": [
    {"field": "target_user", "question": "B2C o B2B?"}
  ]
}
```

- `message`: required, ≤2000 chars.
- `clarifications`: optional, max 50 items. Each item: `{field: string≤128, question: string≤500}`.

### kind = "section_suggestion"

```json
{
  "kind": "section_suggestion",
  "message": "<intro text>",
  "suggested_sections": [
    {
      "section_type": "objectives",
      "proposed_content": "<markdown>",
      "rationale": "<optional>"
    }
  ],
  "clarifications": [{"field": "rollback_plan", "question": "..."}]
}
```

- `message`: required, ≤2000 chars.
- `suggested_sections`: required, **min 1**, max 25. Each item:
  - `section_type`: required, lowercase `^[a-z_]+$`, ≤64 chars, MUST be one of our catalog (see §Catalog below).
  - `proposed_content`: required, ≤20480 chars (≈20 KB), markdown.
  - `rationale`: optional, ≤2048 chars.
- `clarifications`: optional, same shape as `question.clarifications`. May coexist with suggestions.

### kind = "po_review"

```json
{
  "kind": "po_review",
  "message": "<summary>",
  "po_review": {
    "score": 62,
    "verdict": "needs_work",
    "agents_consulted": ["product", "architect", "qa", "backend", "security"],
    "per_dimension": [
      {
        "dimension": "product",
        "score": 55,
        "verdict": "needs_work",
        "findings": [{"severity": "high", "title": "...", "description": "..."}],
        "missing_info": [{"field": "success_metric", "question": "..."}]
      }
    ],
    "action_items": [
      {"priority": "critical", "title": "...", "description": "...", "owner": "PO"}
    ]
  },
  "comments": ["envelope-level comment 1", "..."],
  "clarifications": [{"field": "rollout_plan", "question": "..."}]
}
```

- `score`: 0–100. `verdict ∈ {approved, needs_work, rejected}`.
- `per_dimension` ≤ 16, `findings` ≤ 25, `action_items` ≤ 50, `comments` ≤ 100, `clarifications` ≤ 50, `missing_info` ≤ 50, `agents_consulted` ≤ 16.
- `severity ∈ {low, medium, high, critical}`. `priority ∈ {low, medium, high, critical}`.
- `comments` and `clarifications` are **envelope-level siblings** of `po_review`, never nested inside it.

### kind = "error"

```json
{ "kind": "error", "message": "The system could not produce a valid structured response. Please try again." }
```

- `message`: required, ≤2000 chars.

---

## Catalog of `section_type` (EP-22 valid set)

```
objectives
scope
non_goals
acceptance_criteria
risks
assumptions
dependencies
success_metrics
rollout_plan
open_questions
```

Items in `suggested_sections` with a `section_type` outside this catalog are dropped on the BE with a warn log. Surviving items forwarded. If all invalid, the envelope is still forwarded with an empty `suggested_sections` list.

---

## Backend responsibilities

### Inbound: `_enrich_inbound_frame` (conversation_controller.py)

For any frame with `type == "response"`:

1. Read `frame["response"]` (string). If missing or not a string → forward verbatim with warn log.
2. Attempt `json.loads(frame["response"])`. On failure → replace `response` with a wire-safe `{"kind": "error", "message": "malformed_response"}` JSON-string and warn-log.
3. Validate the parsed object against `MorpheoResponse` (discriminated-union Pydantic model). On validation failure → replace with `{"kind": "error", "message": "invalid_response_shape"}` JSON-string and warn-log with field path + error type (no raw input).
4. On valid `section_suggestion`: drop items with `section_type` outside the catalog or failing item-level validation. Re-serialize the envelope (now with filtered `suggested_sections`) back into `frame["response"]` as a JSON-string. If all items dropped, the filtered list may be empty — but because the schema requires `minItems: 1`, in that edge case downgrade the kind to `question` (with the same `message` + any `clarifications`) before re-serialization.
5. Forward `frame` with re-serialized `response` string to the FE. **Do not flatten** — the FE expects the same `{type, response: string, signals}` wire shape.
6. `signals` is passed through verbatim (only `conversation_ended` matters; no mutation).

### Outbound: `_enrich_outbound_frame` — unchanged

Already attaches `context.sections_snapshot` server-authoritative. No change. Dundun confirmed Morpheo consumes `sections_snapshot` to prioritize empty sections.

### Observability

- Warn-log on: malformed JSON, schema validation failure, `section_type` catalog drops, overflow (`>25`). Log fields: `kind`, `thread_id`, `drop_count`, `reason_summary` (field path + error type, **never raw content**).
- Debug-log: parsed envelope size, kind distribution per thread.

---

## Frontend responsibilities

### ChatPanel onMessage (chat-panel.tsx)

```ts
const frame = JSON.parse(event.data);
if (frame.type === 'progress') { /* ... */ }
else if (frame.type === 'response') {
  let envelope: MorpheoResponse;
  try {
    envelope = MorpheoResponseSchema.parse(JSON.parse(frame.response));
  } catch {
    renderError('malformed_response');
    return;
  }
  switch (envelope.kind) {
    case 'question': renderQuestion(envelope); break;
    case 'section_suggestion': renderSectionSuggestion(envelope, sectionsByType, splitView); break;
    case 'po_review': renderPoReview(envelope); break;
    case 'error': renderError(envelope.message); break;
  }
}
```

- Use Zod (already in the FE stack) for envelope validation.
- The `signals.conversation_ended` flag continues to drive the "conversation ended" UI state as today.

### Renderers (new / updated components)

| Component | Kind | Location | Notes |
|---|---|---|---|
| `ClarificationPrompt` | `question` | `components/clarification/clarification-prompt.tsx` | Renders `message` + list of `{field, question}` as a structured bubble in the chat transcript. No side-effects. |
| `PendingSectionSuggestions` | `section_suggestion` | Existing `PendingSuggestionCard` **reused** inside `SpecificationSectionsEditor`; triggered via `SplitViewContext.emitSuggestion(section_type, proposed_content, rationale)`. | Iterates over `suggested_sections`; emits one suggestion per item. `clarifications` (if present) rendered as a secondary bubble after the intro `message`. |
| `PoReviewPanel` | `po_review` | `components/clarification/po-review-panel.tsx` (new) | Renders score header, per-dimension breakdown, action_items, envelope-level comments, envelope-level clarifications. Read-only. No section mutations. |
| `ChatErrorBanner` | `error` | `components/clarification/chat-error-banner.tsx` (new) | Inline error bubble in the transcript. Not a global toast. |

### Types (lib/types/conversation.ts)

```ts
export type MorpheoQuestion = {
  kind: 'question';
  message: string;
  clarifications?: Array<{ field: string; question: string }>;
};

export type MorpheoSectionSuggestion = {
  kind: 'section_suggestion';
  message: string;
  suggested_sections: Array<{
    section_type: string;
    proposed_content: string;
    rationale?: string;
  }>;
  clarifications?: Array<{ field: string; question: string }>;
};

export type MorpheoPoReview = {
  kind: 'po_review';
  message: string;
  po_review: {
    score: number;
    verdict: 'approved' | 'needs_work' | 'rejected';
    agents_consulted: string[];
    per_dimension: Array<{
      dimension: string;
      score: number;
      verdict: 'approved' | 'needs_work' | 'rejected';
      findings: Array<{ severity: 'low' | 'medium' | 'high' | 'critical'; title: string; description: string }>;
      missing_info: Array<{ field: string; question: string }>;
    }>;
    action_items: Array<{ priority: 'low' | 'medium' | 'high' | 'critical'; title: string; description: string; owner: string }>;
  };
  comments?: string[];
  clarifications?: Array<{ field: string; question: string }>;
};

export type MorpheoError = { kind: 'error'; message: string };

export type MorpheoResponse =
  | MorpheoQuestion
  | MorpheoSectionSuggestion
  | MorpheoPoReview
  | MorpheoError;
```

---

## US-223 (revised) — Section suggestions auto-populate into target sections

### Scenario: `section_suggestion` arrives → target sections enter pending mode

WHEN an assistant `response` frame arrives AND `JSON.parse(frame.response).kind == 'section_suggestion'`
AND the FE validates the envelope with Zod
THEN for each item in `suggested_sections`:
  - `ChatPanel` calls `SplitViewContext.emitSuggestion(section_type, proposed_content, rationale)`
AND the right panel scrolls smoothly to the first valid target section
AND that section card is highlighted for 3 seconds (EP-03 pulse convention)
AND each targeted section enters "pending suggestion" mode (proposed content held as pending draft, NOT committed)
AND if `envelope.message` is non-empty, it is rendered as an intro bubble in the chat transcript

### Scenario: Diff view rendered for a pending suggestion

(Unchanged from v1) Section in pending-suggestion mode → diff view above the section editor, Accept / Reject / Edit actions, rationale beneath.

### Scenario: User accepts a pending suggestion

(Unchanged from v1) `PATCH /work-items/{id}/sections/{section_id}` with `{content: proposed_content}` → new section version recorded → pending UI dismissed.

### Scenario: User rejects / edits

(Unchanged from v1)

### Scenario: Multiple suggestions in one envelope

WHEN `suggested_sections` has multiple valid items
THEN each targeted section enters pending mode independently
AND the right panel scrolls to the first (top-down order)
AND pulses only the first one.

### Scenario: Unknown `section_type` — BE drops

WHEN an item has `section_type` outside the catalog
THEN BE drops the item with a warn log
AND surviving items are forwarded
AND if all items are dropped, the kind is downgraded to `question` preserving `message` and `clarifications`.

### Scenario: Malformed envelope — BE downgrades to error

WHEN `frame.response` is not valid JSON OR the parsed object fails `MorpheoResponse` schema
THEN BE replaces `frame.response` with a JSON-string `{"kind": "error", "message": "malformed_response" | "invalid_response_shape"}`
AND warn-logs with field path + error type (no raw input).

---

## US-224 (unchanged) — Outbound sections_snapshot

Unchanged from v1 except for snapshot shape: **array of `{section_type, content, is_empty}`** (the shape Dundun confirmed Morpheo consumes), NOT a map `{section_type: content}`.

```json
{
  "type": "message",
  "content": "<user text>",
  "context": {
    "sections_snapshot": [
      {"section_type": "objectives", "content": "texto actual", "is_empty": false},
      {"section_type": "scope", "content": "", "is_empty": true}
    ]
  }
}
```

BE `_enrich_outbound_frame`: override `context.sections_snapshot` with server-authoritative array before forwarding. Build the array from `ISectionRepository.get_by_work_item(work_item_id)`. `is_empty` = `not content.strip()`.

---

## Companion kinds — `question`, `po_review`, `error`

### `question`

WHEN envelope.kind == 'question' THEN render `<ClarificationPrompt message={...} clarifications={...} />` as an assistant bubble.
No section mutations. User answers via the normal chat composer; Dundun gets the answer on the next turn.

### `po_review`

WHEN envelope.kind == 'po_review' THEN render `<PoReviewPanel envelope={...} />` as an assistant bubble expanded inline in the chat transcript.
The panel is read-only: score header, per-dimension findings grid, action_items list, envelope-level comments, envelope-level clarifications.
No section mutations. Action items are guidance, not automated edits (out of EP-22 scope).

### `error`

WHEN envelope.kind == 'error' THEN render `<ChatErrorBanner message={...} />` inline in the transcript.
Distinct styling from a normal bubble (warning color + icon). No side-effects.

---

## Out of scope (EP-22 v2)

- Accepting `po_review.action_items` as direct section edits (would require a mapping policy action_item → section_type).
- Responding to envelope-level `clarifications` via structured inputs (answered as free text today).
- Streaming partial envelopes (Dundun emits complete envelopes only).
