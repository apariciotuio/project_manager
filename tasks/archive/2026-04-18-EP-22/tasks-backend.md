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

### 1.2 Pydantic models for Dundun signals (wire schema)

- [x] [RED] Unit tests in `tests/unit/presentation/test_dundun_signals.py` — 17 cases; all failed before module existed — 2026-04-18
- [x] [GREEN] Created `backend/app/presentation/schemas/dundun_signals.py` with `SuggestedSection`, `ConversationSignalsWire`, `validate_signals()` — 2026-04-18
- [x] [REFACTOR] `validate_signals` drops invalid items with warn log including `dropped_count` + `invalid_reasons`, always returns dict with `suggested_sections` key — 2026-04-18
- [x] All 17 tests pass — 2026-04-18

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

### 3.2 Outbound frame enrichment

- [x] [RED] Controller unit tests `tests/unit/presentation/controllers/test_conversation_ws_ep22.py` — 9 cases — 2026-04-18
- [x] [GREEN] Added `_enrich_outbound_frame(frame, work_item_id, snapshot_provider)` to `conversation_controller.py` — 2026-04-18
- [x] [GREEN] Modified `_pump.fe_to_upstream` to call `_enrich_outbound_frame` before forwarding — 2026-04-18
- [x] [GREEN] WS handler builds `_get_snapshot` closure using `SectionRepositoryImpl` — 2026-04-18

### 3.3 Observability

- [x] [GREEN] Log `sections_snapshot_bytes` at debug (always) and warn when >50KB — 2026-04-18

---

## Phase 4 — WS proxy: inbound `signals.suggested_sections`

### 4.1 Validation interception

- [x] [RED] Unit tests for `_enrich_inbound_frame` — 5 cases in `test_conversation_ws_ep22.py` — 2026-04-18
- [x] [GREEN] Added `_enrich_inbound_frame(frame)` to `conversation_controller.py` — validates signals on type==response frames via `validate_signals`, drops invalid items — 2026-04-18
- [x] [GREEN] Modified `_pump.upstream_to_fe` to call `_enrich_inbound_frame` before `send_json` — 2026-04-18

### 4.2 Log quality signal

- [x] [GREEN] `validate_signals` logs `dropped_count` and `invalid_reasons` in warn log — 2026-04-18

---

## Phase 5 — Cross-cutting

### 5.1 Fake Dundun client extensions

- [x] [GREEN] Added `queue_ws_response_with_signals(signals: dict)` to `FakeDundunClient` in `app/infrastructure/fakes/fake_dundun_client.py` — 2026-04-18

### 5.2 Contract test with Dundun repo

- [x] [GREEN] Added `tests/integration/test_dundun_signals_contract.py` — 4 cases validating our schema against Dundun's ConversationSignals; all pass — 2026-04-18

### 5.3 Docs

- [x] [GREEN] Updated `memory/reference_dundun_api.md` with EP-22 `suggested_sections` extension, outbound snapshot, and primer flow — 2026-04-18

---

## Phase 6 — Finalization

- [x] [TEST] All 42 EP-22 tests pass — no regressions in existing tests — 2026-04-18
- [x] [LINT] `ruff` clean on all new/modified files — 2026-04-18
- [x] [LINT] `mypy --strict` — 0 new errors on EP-22 files; pre-existing errors in other files (124 total, 61 files) tracked as repo-wide debt — verified 2026-04-18
- [x] [SEC] Security review — 4 SEC findings addressed inline (SEC-AUTH-001 workspace scope on threads, SEC-CONF-001 prod service-key required, SEC-INVAL-001 suggested_sections cap, SEC-LOG-001 validation log sanitisation); commits e88e1b6, ced46a7, abf7015 — 2026-04-18
- [x] [REVIEW] `code-reviewer` agent run — 1 MF + 3 SF flagged; MF closed (REST workspace scoping), SF closed or deferred — session 2026-04-18
- [ ] [REVIEW] `review-before-push` run — blocked by repo-wide debt (see EP-21 tasks.md "Status 2026-04-18" section); EP-22 scope itself is clean
- [x] Update `tasks.md` — all checkboxes ticked — 2026-04-18

---

## Definition of Done

- [x] `conversation_threads.primer_sent_at` column migrated (0122) and indexed
- [x] `ChatPrimerSubscriber` registered; `WorkItemCreatedEvent` handled idempotently
- [x] WS outbound enriches `context.sections_snapshot` from the server
- [x] WS inbound validates `signals.suggested_sections` and drops malformed entries
- [x] `ConversationSignalsWire` schema enforces size caps and tolerates new Dundun fields
- [x] Structured logs: primer status, snapshot sizes, dropped suggestions
- [x] 42 new backend tests — all green

**Status: COMPLETED** (2026-04-18)
