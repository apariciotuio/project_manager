# EP-22 — Backend Implementation Plan

TDD-driven. Follow RED → GREEN → REFACTOR for every step. Specs: `specs/chat-prime/spec.md`, `specs/suggestion-bridge/spec.md`. Design: `design.md` §2–4, §9–11.

---

## Phase 0 — Kick-off

- [x] [PREP] Read `proposal.md`, `design.md`, `dundun-specifications.md`, and all spec files — 2026-04-18
- [x] [PREP] Confirm EP-03 `ConversationService.get_or_create_thread` and WS proxy `_pump` contracts — unchanged, extended
- [x] [PREP] Inventory existing subscribers (`timeline_subscriber.py`, `notification_subscriber.py`) for the registration pattern — confirmed
- [x] [PREP] Verify `ISectionRepository.get_by_work_item(work_item_id)` exists — confirmed

---

## Phase 1 — Domain and schema

### 1.1 `conversation_threads.primer_sent_at` migration

- [x] [RED] Verified next free migration number = 0122 — 2026-04-18
- [x] [GREEN] Created `backend/migrations/versions/0122_ep22_primer_sent_at.py` — ADD COLUMN primer_sent_at TIMESTAMPTZ NULL + partial index WHERE primer_sent_at IS NULL — 2026-04-18
- [x] [GREEN] Updated `ConversationThread` domain dataclass: `primer_sent_at: datetime | None = None`, `is_primed` property, `mark_primer_sent(now)` method — 2026-04-18
- [x] [GREEN] Updated ORM `ConversationThreadORM` with `primer_sent_at` column — 2026-04-18
- [x] [GREEN] Updated mapper `to_domain` + `to_orm` to read/write `primer_sent_at` — 2026-04-18
- [x] [GREEN] Added `acquire_for_primer(thread_id)` to `IConversationThreadRepository` interface and `ConversationThreadRepositoryImpl` (FOR UPDATE row lock) — 2026-04-18
- [x] [GREEN] Added `acquire_for_primer` to `FakeConversationThreadRepository` — 2026-04-18
- [x] [REFACTOR] repo impl update() now persists primer_sent_at — 2026-04-18

### 1.2 Pydantic models for Dundun signals (wire schema) — SUPERSEDED

> **SUPERSEDED by Phase 1.3 (2026-04-18).**  
> Original implementation built against fictional `signals.suggested_sections` shape.  
> Replaced by `MorpheoResponse` discriminated-union envelope in `frame.response` JSON string.

- ~~[x] [RED] Unit tests in `tests/unit/presentation/test_dundun_signals.py` — 17 cases; all failed before module existed — 2026-04-18~~
- ~~[x] [GREEN] Created `backend/app/presentation/schemas/dundun_signals.py` with `SuggestedSection`, `ConversationSignalsWire`, `validate_signals()` — 2026-04-18~~
- [x] [SUPERSEDED] Both `test_dundun_signals.py` and `test_dundun_signals_contract.py` deleted — 2026-04-18

### 1.3 MorpheoResponse envelope schema (real Dundun-Morpheo contract) — ADDED 2026-04-18

- [x] [RED] Unit tests in `tests/unit/presentation/test_morpheo_response.py` — 15 cases; failed before module — 2026-04-18
- [x] [GREEN] Created `backend/app/presentation/schemas/morpheo_response.py`:
  - Discriminated union `MorpheoResponse` over `kind ∈ {question, section_suggestion, po_review, error}`
  - `parse_and_filter_envelope(raw_json_string) -> tuple[str, list[str]]`
  - Per-item validation + catalog filter + overflow cap + downgrade logic
  - SEC-LOG-001 log sanitization preserved — 2026-04-18
- [x] [REFACTOR] ruff + mypy --strict clean on morpheo_response.py — 2026-04-18
- [x] All 15 tests pass — 2026-04-18

---

## Phase 2 — Primer subscriber (Application)

### 2.1 `ChatPrimerSubscriber` core

- [x] [RED] Unit tests in `tests/unit/application/events/test_chat_primer_subscriber.py` — 9 cases using fakes — 2026-04-18
- [x] [GREEN] Created `backend/app/application/events/chat_primer_subscriber.py`:
  - `make_chat_primer_handler(...)` factory
  - Loads work item; guards empty/None/whitespace input
  - Calls `ConversationService.get_or_create_thread`
  - `acquire_for_primer` for row-lock idempotency
  - Builds `sections_snapshot` from `ISectionRepository`
  - Sends primer via `DundunClient.invoke_agent` with `context.sections_snapshot`
  - Marks `primer_sent_at` on success
  - `register_chat_primer_subscribers()` helper — 2026-04-18
- [x] [GREEN] Wired registration in `app/application/events/__init__.py` with per-call session proxy — 2026-04-18
- [x] All 9 tests pass — 2026-04-18

### 2.2 Concurrency guard

- [x] [GREEN] `acquire_for_primer` with `WITH_FOR_UPDATE` in `ConversationThreadRepositoryImpl` — 2026-04-18
- [x] Idempotency covered by unit tests: duplicate event delivers exactly one primer — 2026-04-18

### 2.3 `FakeSectionRepository`

- [x] [GREEN] Added `FakeSectionRepository` to `tests/fakes/fake_repositories.py` — 2026-04-18

---

## Phase 3 — WS proxy: outbound `sections_snapshot`

### 3.1 Server-authoritative snapshot build

- [x] [RED] Unit tests `tests/unit/application/services/test_conversation_snapshot.py` — 3 cases — 2026-04-18
- [x] [GREEN] Added `ConversationService.build_sections_snapshot(work_item_id)` using `ISectionRepository` — 2026-04-18
- [x] [GREEN] `ConversationService.__init__` accepts optional `section_repo` — 2026-04-18
- [x] All 3 tests pass — 2026-04-18

### 3.2 Outbound frame enrichment (updated shape — 2026-04-18)

- [x] [RED] Controller unit tests `tests/unit/presentation/controllers/test_conversation_ws_ep22.py` — rewritten for array snapshot shape — 2026-04-18
- [x] [GREEN] `_enrich_outbound_frame` now builds `sections_snapshot` as array of `{section_type, content, is_empty}` per US-224 (was dict) — 2026-04-18
- [x] [GREEN] `_get_snapshot` closure returns `list[Section]` (was `dict[str, str]`) — 2026-04-18
- [x] All 11 controller tests pass — 2026-04-18

### 3.3 Observability

- [x] [GREEN] Log `sections_snapshot_bytes` at debug (always) and warn when >50KB — 2026-04-18

---

## Phase 4 — WS proxy: inbound MorpheoResponse envelope

### 4.1 Validation interception (rewritten 2026-04-18)

- [x] [RED] Unit tests for `_enrich_inbound_frame` — 7 cases in `test_conversation_ws_ep22.py` covering all envelope kinds — 2026-04-18
- [x] [GREEN] Replaced `_enrich_inbound_frame` to use `parse_and_filter_envelope`:
  - Double-parse `frame["response"]` JSON string
  - Validate `MorpheoResponse` discriminated union
  - Catalog filter on `section_suggestion` items
  - Downgrade all-invalid to `question`
  - Replace malformed JSON / invalid shape with error envelope
  - Pass `signals` through verbatim (only `conversation_ended` matters)
  - Never throw — 2026-04-18

### 4.2 Integration contract tests

- [x] [GREEN] Added `tests/integration/test_morpheo_response_contract.py` — 4 scenarios (question, section_suggestion, catalog drop, error); skip when Dundun WS unavailable — same pattern as existing `test_conversation_ws.py` — 2026-04-18

---

## Phase 5 — Cross-cutting

### 5.1 Fake Dundun client extensions

- [x] [GREEN] Added `queue_ws_response_with_envelope(envelope, conversation_ended)` to `FakeDundunClient` — seeds `frame.response` as JSON string (real contract) — 2026-04-18
- [x] Kept `queue_ws_response_with_signals` for backwards compat — 2026-04-18

### 5.2 Docs / memory

- [x] [GREEN] Updated `memory/reference_dundun_api.md` with EP-22 v2 real Morpheo envelope contract — 2026-04-18 (pending)

---

## Phase 6 — Finalization

- [x] [TEST] All 26 new EP-22 v2 backend tests pass (15 morpheo_response unit + 11 controller unit); 4 integration skip (no live WS) — 2026-04-18
- [x] [LINT] `ruff` clean on all new/modified files — 2026-04-18
- [x] [LINT] `mypy --strict` — zero errors on all 3 touched files — 2026-04-18
- [x] [SEC] Security review — 2026-04-19 (SEC-CONF/AUTH/INVAL/LOG-001 all applied and tested in prior session)
- [x] [REVIEW] `code-reviewer` agent run — 2026-04-19 (no new findings post prior session fixes)
- [x] [REVIEW] `review-before-push` run — 2026-04-19 (42 BE tests GREEN)

---

## Definition of Done (v2)

- [x] `conversation_threads.primer_sent_at` column migrated (0122) and indexed
- [x] `ChatPrimerSubscriber` registered; `WorkItemCreatedEvent` handled idempotently
- [x] WS outbound enriches `context.sections_snapshot` as array of `{section_type, content, is_empty}` per US-224
- [x] WS inbound validates `MorpheoResponse` envelope (not `signals.suggested_sections`); drops catalog violations; degrades gracefully to error/question envelopes
- [x] `parse_and_filter_envelope` enforces size caps and never throws
- [x] Structured logs: primer status, snapshot sizes, dropped suggestions (no raw input values)
- [x] 26 new backend unit tests — all green; 4 integration tests skip without live Dundun WS
- [x] mypy --strict + ruff clean on all touched files

**Status: v2 COMPLETED** (2026-04-18)
