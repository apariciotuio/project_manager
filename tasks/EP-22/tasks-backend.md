# EP-22 — Backend Implementation Plan

TDD-driven. Follow RED → GREEN → REFACTOR for every step. Specs: `specs/chat-prime/spec.md`, `specs/suggestion-bridge/spec.md`. Design: `design.md` §2–4, §9–11.

---

## Phase 0 — Kick-off

- [ ] [PREP] Read `proposal.md`, `design.md`, and all 5 spec files
- [ ] [PREP] Confirm EP-03 `ConversationService.get_or_create_thread` and WS proxy `_pump` contracts are unchanged
- [ ] [PREP] Inventory existing subscribers (`application/events/timeline_subscriber.py`, `notification_subscriber.py`) for the registration pattern
- [ ] [PREP] Verify `ISectionRepository.get_by_work_item(work_item_id)` already exists in `domain/repositories/section_repository.py`

---

## Phase 1 — Domain and schema

### 1.1 `conversation_threads.primer_sent_at` migration

- [ ] [RED] Integration test (`tests/integration/test_conversation_thread_primer_column.py`): loads the conversation_threads table and asserts `primer_sent_at TIMESTAMPTZ NULL` exists; fails pre-migration
- [ ] [GREEN] Create Alembic migration `backend/alembic/versions/0118_add_primer_sent_at.py` — adds the column + partial index `WHERE primer_sent_at IS NULL`
- [ ] [GREEN] Update `ConversationThread` domain dataclass in `app/domain/models/conversation_thread.py` to carry `primer_sent_at: datetime | None`
- [ ] [GREEN] Update ORM mapper in `infrastructure/persistence/conversation_thread_repository_impl.py` to read/write the new column
- [ ] [REFACTOR] Add `mark_primer_sent(self, now: datetime) -> ConversationThread` method to the entity (returns new immutable instance)

### 1.2 Pydantic models for Dundun signals (wire schema)

- [ ] [RED] Unit tests (`tests/unit/presentation/schemas/test_dundun_signals.py`): ≥6 cases
  - Valid minimal signals
  - Valid with 2 suggestions
  - Missing `section_type` → invalid
  - `proposed_content` empty → invalid
  - `proposed_content` >20 KB → invalid
  - `rationale` >2 KB → invalid
  - Unknown extra top-level field → tolerated
  - Section type normalised to lowercase
- [ ] [GREEN] Create `backend/app/presentation/schemas/dundun_signals.py` with `SuggestedSection` and `ConversationSignalsWire` models
- [ ] [REFACTOR] Expose a helper `validate_signals(raw: dict) -> dict` that returns the cleaned dict, dropping invalid items and logging warnings with correlation id

---

## Phase 2 — Primer subscriber (Application)

### 2.1 `ChatPrimerSubscriber` core

- [ ] [RED] Unit tests (`tests/unit/application/events/test_chat_primer_subscriber.py`): ≥8 cases using fakes
  - Non-empty `original_input` → fake Dundun receives exactly one send; `primer_sent_at` set
  - Empty `original_input` → no send; thread still created
  - None `original_input` → no send
  - Whitespace-only `original_input` → no send
  - `primer_sent_at` already set → no send
  - Dundun raises → handler returns without raising; `primer_sent_at` NOT set
  - Unknown work_item_id (repo returns None) → handler logs and returns
  - Duplicate event delivered twice → Dundun receives exactly one send
- [ ] [GREEN] Create `backend/app/application/events/chat_primer_subscriber.py`
  - Handler accepts the event, loads the work item via `IWorkItemRepository.get(event.work_item_id)`
  - Guards on `original_input` (None / empty / whitespace-only)
  - Calls `ConversationService.get_or_create_thread(...)`
  - Checks `thread.primer_sent_at`; skips if set
  - Sends user message to Dundun via `DundunClient.invoke_agent(agent="chat", ...)` with `caller_role=employee` and `conversation_id=thread.dundun_conversation_id`
  - Updates `thread.primer_sent_at` via the repository
- [ ] [GREEN] Add factory `register_chat_primer_subscribers(bus, get_primer_service_factory)` in `application/events/chat_primer_subscriber.py`
- [ ] [GREEN] Wire registration in `application/events/register_subscribers.py` (or equivalent) inside `create_app`

### 2.2 Concurrency guard

- [ ] [RED] Integration test (`tests/integration/test_chat_primer_concurrent.py`): launch two handler invocations for the same event; assert `FOR UPDATE` serialises and Dundun receives exactly one send
- [ ] [GREEN] Implement `IConversationThreadRepository.acquire_for_primer(thread_id: UUID) -> ConversationThread | None` — row-locked SELECT; returns the thread or None if already primed
- [ ] [REFACTOR] Subscriber uses the new repo method; the row lock is released by the surrounding transaction on commit/rollback

### 2.3 Creation end-to-end

- [ ] [RED] Integration test (`tests/integration/test_work_item_creation_primes_dundun.py`):
  - POST `/api/v1/work-items` with a non-empty title
  - Assert fake Dundun receives a chat invocation whose `conversation_id` matches the thread row for (creator, work_item)
  - Assert `thread.primer_sent_at IS NOT NULL`
  - Second POST with a different title → second thread + second primer; each isolated
- [ ] [GREEN] No code changes expected — wire-up alone should suffice; fix up until green

---

## Phase 3 — WS proxy: outbound `sections_snapshot`

### 3.1 Server-authoritative snapshot build

- [ ] [RED] Unit tests (`tests/unit/application/services/test_conversation_snapshot.py`):
  - Work item with 3 sections → snapshot is `{ section_type: content }` for all three
  - Work item with 0 sections → snapshot is `{}`
  - General thread (work_item_id=None) → snapshot is `None` (skipped)
- [ ] [GREEN] Add `ConversationService.build_sections_snapshot(work_item_id: UUID | None) -> dict[str, str] | None` using `ISectionRepository.get_by_work_item`

### 3.2 Outbound frame enrichment

- [ ] [RED] Integration test (`tests/integration/test_conversation_ws_snapshot_outbound.py`):
  - Open WS to `/ws/conversations/{thread_id}` (fake auth, fake Dundun)
  - Send `{"type":"message","content":"hello"}`
  - Assert fake Dundun received `{"type":"message","content":"hello","context":{"sections_snapshot":{...}}}`
  - Assert any `context.sections_snapshot` the FE passed was overwritten by server values
  - General thread → frame forwarded verbatim (no `context.sections_snapshot`)
- [ ] [GREEN] Modify `conversation_controller._pump.fe_to_upstream` to call `ConversationService.build_sections_snapshot` and merge into the frame before `upstream.send`
- [ ] [REFACTOR] Extract the enrichment into a small helper `_enrich_outbound_frame(frame, thread, snapshot_provider)` for testability

### 3.3 Observability

- [ ] [GREEN] Log `sections_snapshot_bytes` at debug level (always) and warn level when >50KB, with `work_item_id` + `thread_id` + correlation id
- [ ] [RED] Unit test asserts warn log is emitted for oversized payloads; debug for small

---

## Phase 4 — WS proxy: inbound `signals.suggested_sections`

### 4.1 Validation interception

- [ ] [RED] Integration tests (`tests/integration/test_conversation_ws_signals_inbound.py`):
  - Dundun emits `response` with valid `suggested_sections` (2 items) → FE receives the same 2 items (via WS snapshot)
  - Dundun emits `response` with 1 invalid + 1 valid → FE receives only the valid one; warn log emitted
  - Dundun emits `response` with ALL items invalid → FE receives `suggested_sections: []` (field present, empty)
  - Dundun emits `response` without `signals` → FE receives defaults `{conversation_ended: false, suggested_sections: []}`
  - Dundun emits frame with unknown type (`"type":"progress"`) → forwarded verbatim
- [ ] [GREEN] Modify `conversation_controller._pump.upstream_to_fe` to call `validate_signals` on `type == "response"` frames before `websocket.send_json`
- [ ] [REFACTOR] Extract interception into `_enrich_inbound_frame(frame, validator)` helper

### 4.2 Log quality signal

- [ ] [GREEN] Include `dropped_count` and `invalid_reasons` in the warn log when items are dropped — enables prompt-quality monitoring

---

## Phase 5 — Cross-cutting

### 5.1 Fake Dundun client extensions

- [ ] [GREEN] Extend `backend/app/infrastructure/fakes/fake_dundun_client.py`:
  - `received_invocations: list[dict]` already captures `invoke_agent` calls
  - Add helper `queue_ws_response_with_signals(signals: dict)` so WS integration tests can assert inbound handling
  - Preserve existing fake-shaped contract

### 5.2 Contract test with Dundun repo

- [ ] [GREEN] Add `tests/integration/test_dundun_signals_contract.py` that loads Dundun's `ConversationSignals` class (symlink or vendored copy) and asserts our `ConversationSignalsWire` accepts every field Dundun emits. Guards against schema drift.

### 5.3 Docs + changelog

- [ ] [GREEN] Update `memory/reference_dundun_api.md` (if present) with the `suggested_sections` extension
- [ ] [GREEN] Append a changelog entry to `backend/CHANGELOG.md` describing the new subscriber + WS enrichment

---

## Phase 6 — Finalization

- [ ] [TEST] All new tests pass (`pytest -q tests/unit tests/integration -k "primer or snapshot or signals"`)
- [ ] [TEST] Full backend suite green — no regressions in EP-03 WS tests
- [ ] [LINT] `ruff` + `mypy --strict` clean on new files
- [ ] [SEC] Security-by-design review — verify:
  - `validate_signals` caps `proposed_content` at 20 KB (protects FE)
  - `section_type` stripped + lowercased (defence against homograph / whitespace)
  - Log entries never include raw `proposed_content` at info level (potential PII)
  - WS auth (existing EP-03 JWT check) remains in front of the proxy
- [ ] [REVIEW] `code-reviewer` agent run
- [ ] [REVIEW] `review-before-push` run
- [ ] Update `tasks.md` — all checkboxes ticked; status row set to COMPLETED (YYYY-MM-DD)

---

## Definition of Done

- `conversation_threads.primer_sent_at` column migrated and indexed
- `ChatPrimerSubscriber` registered; `WorkItemCreatedEvent` handled idempotently
- WS outbound enriches `context.sections_snapshot` from the server
- WS inbound validates `signals.suggested_sections` and drops malformed entries
- `ConversationSignalsWire` schema enforces size caps and is tolerant of new Dundun fields
- Structured logs provide observability on primer status, snapshot sizes, and dropped suggestions
- ≥20 new backend tests (domain/application/integration) — all green, no flakes
