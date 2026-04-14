# EP-03 — Implementation Checklist

## Status: IN PROGRESS

---

## Phase 1 — Data Model & Migrations

- [ ] [TDD-RED] Write migration tests: assert conversation_threads table schema (columns, indexes, constraints)
- [ ] [TDD-RED] Write migration tests: assert conversation_messages table schema
- [ ] [TDD-RED] Write migration tests: assert suggestion_sets and suggestion_items tables
- [ ] [TDD-RED] Write migration tests: assert gap_findings table
- [ ] [TDD-GREEN] Create Alembic migration: conversation_threads
- [ ] [TDD-GREEN] Create Alembic migration: conversation_messages + indexes
- [ ] [TDD-GREEN] Create Alembic migration: suggestion_sets + suggestion_items + indexes
- [ ] [TDD-GREEN] Create Alembic migration: gap_findings + index
- [ ] [TDD-REFACTOR] Verify all FK constraints and unique indexes match design.md section 1 and 3

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

- [ ] [TDD-RED] Unit tests: `ConversationThread` — one element thread constraint, general thread creation
- [ ] [TDD-RED] Unit tests: `ConversationMessage` — author_type invariants, message_type constraints
- [ ] [TDD-GREEN] Implement domain models: `ConversationThread`, `ConversationMessage`

---

## Phase 3 — LLM Infrastructure

- [ ] [TDD-RED] Unit tests: `LLMProvider` protocol — fake adapter returns structured responses
- [ ] [TDD-RED] Unit tests: `ResponseParser` — valid JSON parsed correctly, invalid JSON raises `LLMParseError`, retry logic
- [ ] [TDD-RED] Unit tests: `PromptRegistry` — loads YAML, returns versioned template, raises on missing
- [ ] [TDD-GREEN] Implement `LLMProvider` protocol in `domain/ports/llm_provider.py`
- [ ] [TDD-GREEN] Implement `FakeLLMAdapter` for tests in `tests/fakes/`
- [ ] [TDD-GREEN] Implement `AnthropicAdapter` in `infrastructure/llm/`
- [ ] [TDD-GREEN] Implement `ResponseParser` with jsonschema validation
- [ ] [TDD-GREEN] Implement `PromptRegistry` — load from YAML at startup
- [ ] [TDD-GREEN] Write prompt YAML files: gap_detection/v1, guided_question/v1, suggestion_generation/v1, quick_action_*/v1, thread_summarisation/v1
- [ ] [TDD-REFACTOR] Token counting with tiktoken integrated into adapter; hard budget enforced before call

---

## Phase 4 — Repository Layer

- [ ] [TDD-RED] Integration tests: `ConversationThreadRepository` — CRUD, unique element thread constraint
- [ ] [TDD-RED] Integration tests: `ConversationMessageRepository` — paginated load, archive query excludes archived messages
- [ ] [TDD-RED] Integration tests: `SuggestionSetRepository` — CRUD, expiry query, status update
- [ ] [TDD-RED] Integration tests: `GapFindingRepository` — cache invalidation on work_item update
- [ ] [TDD-GREEN] Implement repositories with SQLAlchemy async
- [ ] [TDD-REFACTOR] All queries use indexed columns; N+1 checked on message load with FK joins

---

## Phase 5 — Application Services

### ClarificationService (US-030)

- [ ] [TDD-RED] Unit tests: `ClarificationService.get_gap_report()` — rule-based only, cached result served from Redis
- [ ] [TDD-RED] Unit tests: `ClarificationService.trigger_llm_review()` — dispatches Celery task, returns job_id
- [ ] [TDD-RED] Unit tests: `ClarificationService.get_next_questions()` — returns top 3 hard gaps as questions
- [ ] [TDD-GREEN] Implement `ClarificationService`
- [ ] [TDD-REFACTOR] Redis cache key `gap:{work_item_id}:{version}`, TTL 5 min, invalidated on update

### ConversationService (US-031)

- [ ] [TDD-RED] Unit tests: `ConversationService.get_or_create_element_thread()` — idempotent, returns existing if present
- [ ] [TDD-RED] Unit tests: `ConversationService.send_message()` — persists user message, dispatches LLM task
- [ ] [TDD-RED] Unit tests: `ConversationService.build_context()` — returns messages within token budget, includes summary if truncated
- [ ] [TDD-RED] Unit tests: `ConversationService.summarise_and_archive()` — archives old messages, inserts summary message
- [ ] [TDD-GREEN] Implement `ConversationService`
- [ ] [TDD-REFACTOR] Context assembly is deterministic; token budget enforced before every LLM call

### SuggestionService (US-032)

- [ ] [TDD-RED] Unit tests: `SuggestionService.generate()` — dispatches task, returns pending set_id
- [ ] [TDD-RED] Unit tests: `SuggestionService.apply_partial()` — happy path, version conflict raises 409, expired set raises 422
- [ ] [TDD-RED] Unit tests: `SuggestionService.apply_partial()` — partial apply creates version snapshot with correct metadata
- [ ] [TDD-GREEN] Implement `SuggestionService` with transactional partial apply (section 3.1 in design.md)
- [ ] [TDD-REFACTOR] Optimistic lock on version_number verified; conflict detection tested explicitly

### QuickActionService (US-033)

- [ ] [TDD-RED] Unit tests: `QuickActionService.execute()` — each action type, empty section validation, failure path
- [ ] [TDD-RED] Unit tests: `QuickActionService.undo()` — within window succeeds, outside window raises error
- [ ] [TDD-GREEN] Implement `QuickActionService` with undo TTL via Redis key `undo:{action_id}` TTL 10s
- [ ] [TDD-REFACTOR] Undo atomically marks version as reverted; no orphan version created

---

## Phase 6 — Celery Tasks

- [ ] [TDD-RED] Integration tests: `generate_llm_response` task — fake LLM adapter, message persisted, thread token count updated
- [ ] [TDD-RED] Integration tests: `generate_suggestion_set` task — fake LLM, suggestion_items created, set status updated
- [ ] [TDD-RED] Integration tests: `run_background_gap_analysis` task — triggered for stale items, findings persisted
- [ ] [TDD-RED] Integration tests: `summarise_thread_context` task — old messages archived, summary message inserted
- [ ] [TDD-GREEN] Implement Celery tasks in `tasks/llm_tasks.py`
- [ ] [TDD-REFACTOR] All tasks idempotent (safe to retry); max_retries=3, exponential backoff

---

## Phase 7 — API Controllers

- [ ] [TDD-RED] Integration tests: `GET /api/v1/threads` — filter by work_item_id, filter by type, auth required
- [ ] [TDD-RED] Integration tests: `POST /api/v1/threads` — general thread created, element thread returns existing
- [ ] [TDD-RED] Integration tests: `POST /api/v1/threads/{id}/messages` — message stored, 202 returned, LLM task dispatched
- [ ] [TDD-RED] Integration tests: `GET /api/v1/threads/{id}/stream` — SSE headers, streaming tokens delivered
- [ ] [TDD-RED] Integration tests: `GET /api/v1/work-items/{id}/gaps` — returns gap report, 404 on missing item
- [ ] [TDD-RED] Integration tests: `POST /api/v1/work-items/{id}/gaps/ai-review` — 202 + job_id, auth required
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
- [ ] E2E test: user opens element thread → sends message → receives streamed response → leaves and resumes
- [ ] E2E test: suggestion set generated → partial apply (2 of 3 sections) → new version created → diff visible
- [ ] E2E test: quick action rewrite → undo within 10s → section reverted
- [ ] E2E test: version conflict on apply → 409 returned → user presented with resolution options
- [ ] Security review: all thread endpoints checked for IDOR (user can only access threads they have permission for)
- [ ] Security review: LLM prompt injection — element content sanitised before insertion into prompts
- [ ] Performance: LLM calls do not block request threads; verified via load test with 10 concurrent suggestion requests
- [ ] `code-reviewer` agent sign-off
- [ ] `review-before-push` workflow sign-off

---

## Notes

- FakeLLMAdapter is the only mock at the LLM boundary; all other test doubles are fakes or real in-process implementations.
- Celery tasks use the `llm_high`, `llm_normal`, `llm_low` queues as defined in design.md section 7.
- Prompt YAML files are version-controlled; never edit a deployed version in place — always bump the version suffix.
- All LLM assistant messages stored with `prompt_template_id` + `prompt_version` for full auditability.
