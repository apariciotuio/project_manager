# EP-22 — Dundun Integration Specifications

> How EP-22 talks to Dundun. Contract-level doc — **what travels on the wire**, who owns each field, and the release order across repos. Complements `design.md` §2–§4 and §9. Authority for the cross-repo interface.

> **Target deployment: Dundun-Morpheo** — the Morpheo variant of the Dundun codebase, specialised for work-item definition (tasks, stories, epics, PRDs). Same `dundun` repo, different config (`dundun-config-morpheo/`) + different host + `/morpheo/` API prefix. This epic does NOT target the base `dundun` customer-assistant deployment (Leia).

---

## 1. Repos and Roles

| Repo | Path | Role in EP-22 |
|---|---|---|
| `project_manager/backend` | `backend/app/**` | WS proxy between FE and Dundun. Owns thread store, `original_input` primer, `sections_snapshot` enrichment, `suggested_sections` validation. |
| `project_manager/frontend` | `frontend/**` | Renders `ChatPanel` + `SpecificationSectionsEditor`. Connects to **our** `/ws/conversations/{thread_id}` — never directly to Dundun. |
| `dundun` | `src/dundun/**` | Dundun backend. Owns conversation history per `conversation_id`. Emits `response` frames with `signals`. Cross-repo PR #1 (schema) lands here. |
| `dundun-hub` | `../dundun-hub` | **Reference client, not part of EP-22 runtime.** SPA that connects to the same `/ws/chat` we target. Use it as the canonical example for WS connect, frame shapes, auth query params, and debouncing behavior. |

`dundun-hub` is a sibling tool that talks to the same `/ws/chat` we use. Treat it as the **working reference client**: when the published OpenAPI or our internal docs disagree with reality, `dundun-hub/src/hooks/useWebSocket.ts` is the source of truth for how a browser actually connects and parses frames today.

**Key files in `dundun-hub` to cross-check against our implementation**:

| File | What to lift from it |
|---|---|
| `src/config/endpoints.ts` — profile `morpheo` | Hosts per env, WS path `/api/v1/morpheo/ws/chat`, `defaultRole: "employee"`, `authStyle` defaults to `"dundun"` (direct WS with query-param identity — no REST bootstrap) |
| `src/hooks/useWebSocket.ts` `resolveEndpoint` + `connect` (dundun auth branch) | Query-param wiring: `x-user-phone` + `x-caller-role`. No `conversation_id` param, no headers, no bootstrap |
| `src/hooks/useWebSocket.ts` `parseIncomingPayload` | Exact three inbound shapes: `{type:"progress",...}`, `{response, signals:{...}}`, plain text. Mirror this in our BE proxy |
| `src/hooks/useRunner.ts` `consumeStartup` | Greeting-payload skipping — greeting arrives immediately on `accept()`, regex-drained before real messaging |

---

## 2. Existing Dundun-Morpheo Surface

Frozen baseline — EP-22 extends only where called out in §4. Paths + hosts below match the `morpheo` profile in `dundun-hub/src/config/endpoints.ts`; frame shapes + schemas come from the shared `dundun` codebase.

### 2.0 Hosts per env

| Env | Host (WS + REST) | Protocol |
|---|---|---|
| local | `localhost:8083` | `ws` / `http` |
| dev | `dundun-morpheo-api.internal.dev.tuio.com` | `wss` / `https` |
| pre | `dundun-morpheo-api.internal.pre.tuio.com` | `wss` / `https` |
| pro | `dundun-morpheo-api.internal.tuio.com` | `wss` / `https` |

Injected into our BE as `DUNDUN_BASE_URL` (or equivalent). **Never hardcode in code — read from settings.**

### 2.1 HTTP

Verified against `dundun/src/dundun/api/v1/api.py` + `webhooks/schemas.py` + `webhooks/stan.py`. The base `dundun` codebase mounts chat routes under `/api/v1/dundun/*`; Morpheo's deployment exposes equivalents under `/api/v1/morpheo/*` (prefix swap). **Verify the exact async webhook path with the Dundun team before the primer lands** — the WS path is confirmed as `/api/v1/morpheo/ws/chat`; the async webhook path under Morpheo is not visible in the open-source routes we have and likely requires a deployment-side reverse-proxy rule or pending router.

- `POST /api/v1/morpheo/chat` — sync. Body: `{ user_phone, message, caller_role?, timeout_seconds? }` → `{ data: { type: "response", response, signals } }`. 504 on timeout, 409 if superseded. Not used by EP-22.
- `POST /api/v1/webhooks/dundun/chat` (shared webhook — confirm Morpheo routing) — async (schema: `StanSendMessageRequest`). **`conversation_id` and `request_id` are both REQUIRED non-optional fields** — the caller (us) must generate both before the first turn. Returns `202 + { status, conversation_id, request_id, message }` (NOT `{request_id}` alone). **`history` field is accepted but ignored** — Dundun owns per-`conversation_id` history.
- `POST /api/v1/webhooks/agent/dundun/response` — inbound callback **receiver on Dundun itself** for DunDun-on-DunDun flows. Not relevant to our proxy.
- `POST /api/v1/webhooks/dundun/end-conversation` — terminates by `conversation_id`.
- No read endpoint. Platform persists each turn locally (`conversation_threads`, turn log).

**`source_workflow_id` semantics (often misunderstood)**: it is the **workflow ID of the caller** used by Dundun to route the callback signal back via Temporal on DunDun-to-DunDun chains. It is **not** a free-form tag or agent name. For EP-22 where the caller is our platform (not another Dundun instance), `source_workflow_id` should be `None` — we rely on `callback_url` alone for delivery.

### 2.2 WebSocket — `/api/v1/morpheo/ws/chat`

Source: `dundun/src/dundun/api/v1/dundun/chat_websocket.py` (same handler code; Morpheo mounts it under the `/morpheo` prefix).

**Connect**
```
wss://dundun-morpheo-api.internal.<env>.tuio.com/api/v1/morpheo/ws/chat?x-user-phone=<phone>&x-caller-role=<role>
```

- `x-caller-role` ∈ `{employee, customer, anonymous}`. EP-22 always uses `employee` (Morpheo's `defaultRole`).
- `x-user-phone` optional for `employee` / `anonymous`. Absent → server generates `"{role}-{uuid4}"` as the user id (fresh per connect — not stable across reconnects).
- **Dundun's WS has NO concept of `conversation_id`.** The WS is keyed on a Temporal `workflow_id = "dundun-orchestrator-{role}-{phone-or-uuid}"` (see `message_service.get_or_create_workflow_for_user`). One workflow per `(role, phone)` — history survives across reconnects only for the `customer/employee + phone` combination; `anonymous` gets a fresh UUID every connect and loses history.
- Our `DundunHTTPClient.chat_ws` adds `?conversation_id=` as a query param — **Dundun ignores it**. The method is marked speculative in `domain/ports/dundun.py` and is not used by EP-22 on the live-chat path (see §3).
- (Contrast with the `stanchat` profile in `dundun-hub`, which *does* accept `conversation_id` because Stan has a REST bootstrap step.)

**Frames — inbound (client → Dundun)**
Plain text. No JSON envelope required. One text frame == one user turn.

**Frames — outbound (Dundun → client)**

| Shape | When |
|---|---|
| Text — `INITIAL_GREETING` | Immediately after `accept()` |
| `{"type":"progress","phase":"...","detail":"..."}` | Progress poll during long turns (every ~500ms) |
| `{"type":"response","response":"<text>","signals":{...}}` | Final turn result |
| Text — `"Error processing your request. Please try again."` | Error on the latest message |

**Debouncing**: new inbound frame cancels the in-flight task and polling loop. Only the latest message gets a `response` frame.

**Caveat**: Dundun's WS is not in the published OpenAPI, but the handler is live at `/api/v1/morpheo/ws/chat`. EP-22 uses two transports: `invoke_agent` (async HTTP + callback) for the **primer** only, and `chat_ws` (live WS) for the bidirectional chat stream via our proxy (§3). Both are in scope for EP-22.

### 2.3 Signals (today)

`dundun/src/dundun/temporal/shared/entities/callback.py`:

```python
class ConversationSignals(BaseModel):
    conversation_ended: bool = False
```

This is the entire signals surface today. §4.1 extends it.

---

## 3. EP-22 Proxy Architecture (no Dundun changes)

```
FE  ── /ws/conversations/{thread_id} ──▶  BE (project_manager)
                                           │
                                           ├─ enriches outbound with context.sections_snapshot
                                           ├─ validates inbound signals.suggested_sections
                                           ▼
                                          Dundun  (/ws/chat  OR  POST /webhooks/dundun/chat)
```

- **FE never talks to Dundun directly.** The BE is the only caller of `DundunClient.*`.
- **Our WS path** is `/ws/conversations/{thread_id}` (`presentation/controllers/conversation_controller.py`). The `thread_id` is our row id in `conversation_threads`; the row owns the mapping to Dundun's `conversation_id` via `dundun_conversation_id`.
- **Auth**: on the BE→Dundun hop we send `Authorization: Bearer <DUNDUN_SERVICE_KEY>`, `X-Caller-Role: employee`, `X-User-Id: <uuid>`. On the FE→BE hop we rely on the same JWT session used by the rest of the platform (EP-18 wired it).

---

## 4. Cross-repo Contracts (NEW in EP-22)

Two additions. One owned by Dundun (§4.1), one owned by our BE proxy (§4.2). Both are backward-compatible defaults — safe to ship independently.

### 4.1 Dundun — `ConversationSignals.suggested_sections`

**Repo**: `dundun`. **File**: `src/dundun/temporal/shared/entities/callback.py`. **PR**: Dundun PR #1.

```python
class SuggestedSection(BaseModel):
    section_type: str
    proposed_content: str
    rationale: str = ""


class ConversationSignals(BaseModel):
    conversation_ended: bool = False
    suggested_sections: list[SuggestedSection] = []   # NEW
```

- **Default `[]`** → agents that don't emit suggestions still produce valid signals. Zero backward-compat risk.
- Emitted transparently in the existing `response` frame via `result.signals.model_dump()` at `chat_websocket.py:140`. **No new frame type.**
- Also flows through `webhooks/schemas.StanCallbackResponse.signals` on the async/callback path — same field, same default.
- `section_type` is a free-form string on Dundun's side. Our BE validates + normalises (§4.3).

Making Dundun's agent actually emit `suggested_sections` is a Dundun-team concern (prompt/agent-config change, out of scope here). Our contract is the signals field — whether it's filled or not, EP-22 degrades gracefully to "no pending suggestions shown".

### 4.2 BE — outbound `context.sections_snapshot`

**Repo**: `project_manager/backend`. **File**: `presentation/controllers/conversation_controller.py` (extends `_pump.fe_to_upstream`).

For every FE → Dundun frame with `type == "message"`, the BE:

1. Loads `work_item_sections` for `thread.work_item_id`.
2. Builds `{ section_type.value: section.content }`.
3. Overrides (or injects) `frame.context.sections_snapshot` with that authoritative map.
4. Forwards to Dundun.

**On-the-wire shape BE→Dundun (text WS frame, JSON-encoded)**:

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

Current Dundun WS ignores unknown fields (accepts plain text or JSON). Dundun PR #2's prompt update is what makes the snapshot *useful* — without it, the agent sees an unused field and behaves as before. Safe to ship BE before Dundun PR #2.

### 4.3 BE — inbound `signals.suggested_sections` validation

**Repo**: `project_manager/backend`. **File**: `presentation/schemas/dundun_signals.py` (new) + `_pump.upstream_to_fe`.

```python
class SuggestedSection(BaseModel):
    section_type: str = Field(min_length=1, max_length=64)
    proposed_content: str = Field(min_length=1, max_length=20_000)
    rationale: str = Field(default="", max_length=2_000)

    @field_validator("section_type")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return v.strip().lower()


class ConversationSignalsWire(BaseModel):
    conversation_ended: bool = False
    suggested_sections: list[SuggestedSection] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")
```

Rules:
- Invalid individual entries are **dropped** (warn log, correlation id).
- All-invalid list → forwarded as `suggested_sections: []` (present, empty).
- Top-level parse failure → forwarded as `{"conversation_ended": false, "suggested_sections": []}`.
- Size cap `proposed_content ≤ 20KB` protects FE against runaway LLM output.
- `extra="allow"` tolerates future signal fields added by Dundun without redeploy.

### 4.4 BE → FE WS frame (unchanged shape, new field)

The BE → FE frame FE receives on `/ws/conversations/{thread_id}` stays shape-compatible with EP-03:

```json
{
  "type": "response",
  "response": "<assistant text>",
  "signals": {
    "conversation_ended": false,
    "suggested_sections": [
      { "section_type": "acceptance_criteria",
        "proposed_content": "...",
        "rationale": "..." }
    ]
  }
}
```

FE clients that don't know about `suggested_sections` simply ignore the field. Backward-compatible.

---

## 5. Primer (`original_input`)

Not a cross-repo contract change — uses the existing async HTTP invoke. Documented here because it's the first Dundun turn on every new work item.

- Trigger: `WorkItemCreatedEvent` on backend.
- Transport: `DundunClient.invoke_agent(agent="chat", ...)` → `POST /api/v1/webhooks/dundun/chat`.
- Body:
  - `conversation_id` — **REQUIRED**. On first primer the thread has no Dundun id yet; the subscriber must **generate a UUID client-side** and persist it on `conversation_threads.dundun_conversation_id` *before* the HTTP call. Do NOT rely on Dundun allocating one — the schema (`StanSendMessageRequest`) rejects missing `conversation_id` with 422.
  - `request_id` — **REQUIRED**. Generate per-turn (our client already does this via `generate_request_id()` pattern).
  - `message` = `original_input`.
  - `caller_role = "employee"`.
  - `customer_id` — Dundun's schema labels this "phone number" and `_build_customer_context` tries to parse it as a phone. Sending our user UUID is accepted but produces `CustomerContext = None` on Dundun. Acceptable for EP-22 (the primer doesn't need tuio-customer context) but flag in the subscriber logs.
  - `callback_url` = our BE callback at `POST /api/v1/dundun/callback` (see `dundun_callback_controller.py`).
  - `source_workflow_id` — **leave `None`**. This field is for DunDun-to-DunDun Temporal signal routing only (see §2.1). Our current client code at `dundun_http_client.py:117` sets it to the `agent` string — that is a **pre-existing bug** outside EP-22 scope; track separately.
- Idempotency: `conversation_threads.primer_sent_at` column (new) — see design §2.4.
- Primer turns also carry `context.sections_snapshot` (EP-02 template defaults) per spec `suggestion-bridge/spec.md` scenario "Primer message carries initial snapshot". On the async HTTP path this travels as an extra field in the JSON body — Dundun's Pydantic model has `extra="allow"` by default, so the field passes through to the agent prompt via customer context injection once the prompt is updated.

---

## 6. Release Order (non-negotiable)

| # | Repo | Change | Can ship before next? |
|---|---|---|---|
| 1 | `dundun` | PR #1: add `suggested_sections: list[SuggestedSection] = []` to `ConversationSignals` | **Yes** — pure additive, default `[]` |
| 2 | `project_manager/backend` | Proxy: outbound snapshot enrichment + inbound signals validation + primer subscriber + migration | Yes — forwards empty `suggested_sections` lists until Dundun starts emitting |
| 3 | `project_manager/frontend` | SplitView wiring + PendingSuggestionCard + Clarificación removal | Yes — no suggestions visible until Dundun starts emitting; UI simply shows no pending cards |
| 4 | Dundun team | Agent starts emitting `suggested_sections` (prompt/agent-config — their concern) | Independently revertable |

This ordering means **neither FE nor BE is blocked on Dundun's agent-side work**.

---

## 7. Security Boundaries

Asked: **"how can this be exploited?"**

| Vector | Control |
|---|---|
| LLM emits arbitrary JSON into `signals` | BE Pydantic validation + size caps (§4.3). FE never trusts signals directly. |
| LLM emits huge `proposed_content` → OOM on FE | 20KB cap per entry; list length bounded by Dundun's response size (already capped upstream). |
| FE forges `context.sections_snapshot` to poison Dundun context | BE **overrides** the snapshot with authoritative `work_item_sections` data before forwarding. FE-supplied value is ignored. |
| FE targets another workspace via `thread_id` | Existing authz on `/ws/conversations/{thread_id}` — thread row check workspace membership. Unchanged by EP-22. |
| Primer sent twice after retry | `conversation_threads.primer_sent_at` + `FOR UPDATE` row lock. |
| Dundun unavailable during creation → creation fails | Primer subscriber is fire-and-forget. `WorkItemService.create` returns 201 regardless. |
| Section content leaks across tenants via snapshot | Snapshot is built from `ISectionRepository.get_by_work_item(thread.work_item_id)` — same workspace scope as the thread. No extra leakage surface. |

---

## 8. Observability

- **`sections_snapshot_bytes`** — debug log on every outbound forward. Warn when >50KB (threshold for considering the deferred diff-transport optimisation, decision #3).
- **`suggested_sections_dropped`** — warn log with correlation id + reason when a suggestion item fails Pydantic validation.
- **Primer outcome** — structured log: `event_id`, `thread_id`, `work_item_id`, `primer_length`, `dundun_status`.
- **Thread-level correlation** — reuse `conversation_id` (Dundun) + `thread_id` (platform) in log context throughout the turn.

---

## 9. Out of Scope for EP-22

- Extended WS framing (multiplexed channels, server-push beyond `signals`). The current BE→Dundun WS transport is live for the bidirectional chat stream (§2.2, §3); deeper framing is a separate epic once Dundun publishes the WS contract.
- Diff-based `sections_snapshot` transport (deferred per decision #3).
- Reading Dundun history (no API exists; platform store is authoritative).
- Changes to `dundun-hub` — it remains a standalone operator console.
- Changes to `stanchat` / `morpheo` profiles — EP-22 only targets the `dundun` profile and its `/ws/chat` path.

---

## 10. File Map (cross-repo)

| File | Repo | Change |
|---|---|---|
| `src/dundun/temporal/shared/entities/callback.py` | `dundun` | Add `SuggestedSection` + extend `ConversationSignals` |
| `backend/app/presentation/controllers/conversation_controller.py` | `project_manager` | Extend `_pump` for snapshot enrichment + signals validation |
| `backend/app/presentation/schemas/dundun_signals.py` | `project_manager` | **New** — `ConversationSignalsWire`, `SuggestedSection` |
| `backend/app/application/events/chat_primer_subscriber.py` | `project_manager` | **New** — `WorkItemCreatedEvent` handler |
| `backend/app/application/events/register_subscribers.py` | `project_manager` | Append primer subscriber registration |
| `backend/alembic/versions/0118_*.py` | `project_manager` | **New** — `ALTER TABLE conversation_threads ADD primer_sent_at` |
| `frontend/components/clarification/chat-panel.tsx` | `project_manager` | Intercept `suggested_sections`; attach outbound snapshot |
| `frontend/components/detail/split-view-context.tsx` | `project_manager` | Extend with `pendingSuggestions` map |
| `frontend/components/work-item/pending-suggestion-card.tsx` | `project_manager` | **New** — diff + Accept/Reject/Edit |

Dundun file paths verified against the repo at `/home/david/Workspace_Tuio/agents_workspace/dundun`. Backend paths match design.md §16.