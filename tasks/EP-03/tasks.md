# EP-03 — Implementation Checklist

## Status: IN PROGRESS

> **Scope (2026-04-14, decisions_pending.md #17, #32)**: Thin proxy to **Dundun**. No LLM SDK in our backend, no prompt registry/YAMLs, no context-window management, no token counting, no summarization, no `conversation_messages` history table. `conversation_threads` is a pointer to `dundun_conversation_id`; full history fetched on demand from Dundun. Suggestion generation / gap detection / quick actions / spec gen / breakdown all go through `DundunClient.invoke_agent(...)` (async Celery + callback) or `chat_ws` (WebSocket proxy). Split-view + diff viewer remain in-house. See `design.md`.

---

## Phase 1 — Data Model & Migrations

- [ ] [TDD-RED] Write migration tests: assert `conversation_threads` schema (id, user_id, work_item_id nullable, dundun_conversation_id UNIQUE, last_message_preview, last_message_at, created_at; UNIQUE (user_id, work_item_id))
- [ ] [TDD-RED] Write migration tests: assert `suggestion_sets` and `suggestion_items` tables
- [ ] [TDD-RED] Write migration tests: assert `gap_findings` table
- [ ] [TDD-GREEN] Create Alembic migration: `conversation_threads` (pointer-only, no `conversation_messages`)
- [ ] [TDD-GREEN] Create Alembic migration: `suggestion_sets` + `suggestion_items` + indexes
- [ ] [TDD-GREEN] Create Alembic migration: `gap_findings` + index
- [ ] [TDD-REFACTOR] Verify FK constraints and unique indexes match design.md sections 1 and 3. Do NOT create `conversation_messages`, `prompt_templates`, or LLM-related tables.

---

## Phase 2 — Domain Layer

### Gap Detection (US-030)

- [ ] [TDD-RED] Unit tests: `required_fields` rule — hard gaps for each element type (User Story, Feature, Task, Epic)
- [ ] [TDD-RED] Unit tests: `content_quality` rule — short content, vague language detection
- [ ] [TDD-RED] Unit tests: `acceptance_criteria` rule — WHEN/THEN pattern check
- [ ] [TDD-RED] Unit tests: `hierarchy_rules` rule — missing parent linkage
- [ ] [TDD-RED] Unit tests: `GapDetector.detect()` — combined report, score formula, deduplication
- [ ] [TDD-GREEN] Implement rule functions in `domain/gap_detection/rules/`
- [ ] [TDD-GREEN] Implement `GapDetector.detect()` orchestrator
- [ ] [TDD-REFACTOR] All rules are pure functions; no I/O; 100% branch coverage

### Suggestion domain (US-032, US-033)

- [ ] [TDD-RED] Unit tests: `SuggestionSet` state machine transitions (pending → partially_applied, rejected, expired)
- [ ] [TDD-RED] Unit tests: `SuggestionItem` status transitions
- [ ] [TDD-GREEN] Implement domain models: `SuggestionSet`, `SuggestionItem`
- [ ] [TDD-REFACTOR] Domain models enforce invariants (e.g., can't apply expired set)

### Conversation domain (US-031)

- [ ] [TDD-RED] Unit tests: `ConversationThread` — one thread per (user_id, work_item_id); general (work_item_id NULL) threads allowed
- [ ] [TDD-GREEN] Implement domain model: `ConversationThread` (pointer to `dundun_conversation_id`; no `ConversationMessage` model — history is owned by Dundun)

---

## Phase 3 — Dundun Integration

- [ ] [TDD-RED] Unit tests: `DundunClient.invoke_agent()` — 202 response returns `request_id`; 4xx/5xx raise typed errors; headers include `caller_role=employee`, `user_id`, service-key bearer token
- [ ] [TDD-RED] Unit tests: `DundunClient.chat_ws()` — opens WS to Dundun `/ws/chat`; forwards frames; propagates disconnect
- [ ] [TDD-RED] Unit tests: `DundunClient.get_history(conversation_id)` — returns message list; 404 raises `DundunNotFoundError`
- [ ] [TDD-GREEN] Implement `DundunClient` in `infrastructure/dundun/dundun_client.py` (HTTP via httpx async + WS via websockets)
- [ ] [TDD-GREEN] Implement `FakeDundunClient` in `tests/fakes/` — records calls, returns configurable responses (only fake at the Dundun boundary)
- [ ] [TDD-GREEN] Implement `/api/v1/dundun/callback` endpoint: verifies HMAC signature, routes by `agent` + `request_id`, persists result (`assistant_suggestions`, `gap_findings`, etc.), emits SSE event
- [ ] [TDD-REFACTOR] No prompt YAMLs, no LLM SDK, no token counting, no `tiktoken` in our repo

---

## Phase 4 — Repository Layer

- [ ] [TDD-RED] Integration tests: `ConversationThreadRepository` — CRUD, unique (user_id, work_item_id) constraint, `find_by_dundun_conversation_id`
- [ ] [TDD-RED] Integration tests: `SuggestionSetRepository` — CRUD, expiry query, status update
- [ ] [TDD-RED] Integration tests: `GapFindingRepository` — cache invalidation on work_item update
- [ ] [TDD-GREEN] Implement repositories with SQLAlchemy async
- [ ] [TDD-REFACTOR] All queries use indexed columns

---

## Phase 5 — Application Services

### ClarificationService (US-030)

- [ ] [TDD-RED] Unit tests: `ClarificationService.get_gap_report()` — rule-based only, cached result served from Redis
- [ ] [TDD-RED] Unit tests: `ClarificationService.trigger_ai_review()` — dispatches Celery task invoking `wm_gap_agent` via Dundun; returns `request_id`
- [ ] [TDD-RED] Unit tests: `ClarificationService.get_next_questions()` — returns top 3 hard gaps as questions
- [ ] [TDD-GREEN] Implement `ClarificationService`
- [ ] [TDD-REFACTOR] Redis cache key `gap:{work_item_id}:{version}`, TTL 5 min, invalidated on update

### ConversationService (US-031)

- [ ] [TDD-RED] Unit tests: `ConversationService.get_or_create_thread(user_id, work_item_id=None)` — idempotent; creates Dundun conversation if missing; returns existing on repeat
- [ ] [TDD-RED] Unit tests: `ConversationService.get_history(thread_id)` — delegates to `DundunClient.get_history(dundun_conversation_id)`; refreshes `last_message_preview`
- [ ] [TDD-GREEN] Implement `ConversationService` — owns thread pointer lifecycle only (no message persistence, no context assembly, no summarization)

### SuggestionService (US-032)

- [ ] [TDD-RED] Unit tests: `SuggestionService.generate()` — creates pending `suggestion_set`, enqueues Celery task calling `DundunClient.invoke_agent(agent="wm_suggestion_agent", ...)`; returns pending `set_id`
- [ ] [TDD-RED] Unit tests: `SuggestionService.apply_partial()` — happy path; version conflict raises 409; expired set raises 422
- [ ] [TDD-RED] Unit tests: `apply_partial()` creates version snapshot with correct metadata
- [ ] [TDD-GREEN] Implement `SuggestionService` with transactional partial apply (section 3.1 in design.md)
- [ ] [TDD-REFACTOR] Optimistic lock on version_number verified; conflict detection tested explicitly

### QuickActionService (US-033)

- [ ] [TDD-RED] Unit tests: `QuickActionService.execute()` — each action type maps to a Dundun agent (`rewrite`/`concretize`/`expand`/`shorten`/`generate_ac`) via Celery + callback; empty section validation; failure path
- [ ] [TDD-RED] Unit tests: `QuickActionService.undo()` — within window succeeds, outside window raises error
- [ ] [TDD-GREEN] Implement `QuickActionService` with undo TTL via Redis key `undo:{action_id}` TTL 10s
- [ ] [TDD-REFACTOR] Undo atomically marks version as reverted; no orphan version created

---

## Phase 6 — Celery Tasks (single `dundun` queue)

- [ ] [TDD-RED] Integration tests: `invoke_suggestion_agent` task — `FakeDundunClient` returns `request_id`; suggestion_set status moves pending → awaiting_callback
- [ ] [TDD-RED] Integration tests: `invoke_gap_agent` task — `FakeDundunClient` stubbed; callback handler writes `gap_findings`
- [ ] [TDD-RED] Integration tests: `/api/v1/dundun/callback` — suggestion callback writes `suggestion_items` and transitions set to `pending` (user review); gap callback writes `gap_findings`
- [ ] [TDD-GREEN] Implement Celery tasks in `tasks/dundun_tasks.py` on queue `dundun`
- [ ] [TDD-REFACTOR] All tasks idempotent on retry (check `request_id` + existing set status before re-invoking); no `llm_high/default/low` queue split

---

## Phase 7 — API Controllers

- [ ] [TDD-RED] Integration tests: `GET /api/v1/threads` — filter by work_item_id, filter by type, auth required
- [ ] [TDD-RED] Integration tests: `POST /api/v1/threads` — general thread created, element thread returns existing
- [ ] [TDD-RED] Integration tests: `WS /ws/conversations/{thread_id}` — JWT verified, membership checked, work_item access checked when set, upstream WS to Dundun opened, frames proxied both directions
- [ ] [TDD-RED] Integration tests: `GET /api/v1/threads/{id}/history` — delegates to `DundunClient.get_history`; returns ordered list
- [ ] [TDD-RED] Integration tests: `GET /api/v1/work-items/{id}/gaps` — returns gap report, 404 on missing item (path owned by EP-04; EP-03 routes content findings through `assistant_suggestions` only)
- [ ] [TDD-RED] Integration tests: `POST /api/v1/dundun/callback` — valid HMAC accepted; invalid rejected 401; unknown `request_id` rejected 404
- [ ] [TDD-RED] Integration tests: `POST /api/v1/work-items/{id}/suggestion-sets` — 202 + set_id
- [ ] [TDD-RED] Integration tests: `POST /api/v1/suggestion-sets/{id}/apply` — 200 on success, 409 on conflict, 422 on expired
- [ ] [TDD-RED] Integration tests: `POST /api/v1/work-items/{id}/quick-actions` — 200 with patched section
- [ ] [TDD-RED] Integration tests: `POST /api/v1/work-items/{id}/quick-actions/{id}/undo` — 200 within window, 422 outside
- [ ] [TDD-GREEN] Implement all controllers in `presentation/controllers/`
- [ ] [TDD-REFACTOR] All endpoints enforce authorization; access control mirrors work_item permissions

---

## Phase 8 — Frontend

- [ ] [TDD-RED] Component tests: GapPanel — renders hard/soft findings, completeness %, dismiss behaviour
- [ ] [TDD-RED] Component tests: ClarificationQuestion — renders question, submit answer, skip
- [ ] [TDD-RED] Component tests: ConversationThread — message list, streaming token append, loading state, error + retry
- [ ] [TDD-RED] Component tests: SuggestionPreviewPanel — per-section diff cards, accept/reject, apply button state
- [ ] [TDD-RED] Component tests: QuickActionMenu — available actions per section type, loading state, undo toast
- [ ] [TDD-GREEN] Implement frontend components (Next.js App Router, TypeScript strict)
- [ ] [TDD-REFACTOR] No `any` types; all API responses typed with Zod schemas; SSE connection teardown on unmount

---

## Phase 9 — Integration & Quality Gates

- [ ] E2E test: gap detected on element open → question answered → gap resolved → element transitions out of Draft
- [ ] E2E test: user opens element thread → Dundun WS proxy streams tokens → reconnect resumes
- [ ] E2E test: suggestion set generated via Dundun → callback fires → partial apply (2 of 3 sections) → new version created → diff visible
- [ ] E2E test: quick action rewrite → undo within 10s → section reverted
- [ ] E2E test: version conflict on apply → 409 returned → user presented with resolution options
- [ ] Security review: all thread endpoints checked for IDOR (user can only access own threads)
- [ ] Security review: Dundun callback HMAC signature verified; `request_id` bound to the original thread/user
- [ ] Performance: Dundun invocations do not block request threads; Celery + callback pattern verified under 10 concurrent suggestion requests
- [ ] `code-reviewer` agent sign-off
- [ ] `review-before-push` workflow sign-off

---

## Notes

- `FakeDundunClient` is the only mock at the Dundun boundary; all other test doubles are fakes or real in-process implementations.
- Single Celery queue `dundun` (no `llm_high/default/low` split).
- No prompt YAML files in our repo — prompts are owned by Dundun/LangSmith.
- Assistant messages are stored by Dundun; our DB only keeps the `dundun_conversation_id` pointer and `last_message_preview` cache.
