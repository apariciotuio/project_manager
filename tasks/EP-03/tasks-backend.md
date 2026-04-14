# EP-03 Backend Tasks — Clarification, Conversation & Assisted Actions

Branch: `feature/ep-03-backend`
Refs: EP-03
Depends on: EP-01 backend (work_items), EP-02 backend (draft/template infra)

---

## API Contract (Frontend Dependency)

### Conversation

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/threads?work_item_id={id}&type={element|general}` | JWT | List threads |
| POST | `/api/v1/threads` | JWT | Create general thread |
| GET | `/api/v1/threads/{thread_id}` | JWT | Get thread + paginated messages |
| POST | `/api/v1/threads/{thread_id}/messages` | JWT | Send message, triggers async LLM response |
| GET | `/api/v1/threads/{thread_id}/stream` | JWT | SSE stream for assistant responses |
| DELETE | `/api/v1/threads/{thread_id}` | JWT | Archive general thread |

### Gap Detection & Clarification

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/work-items/{id}/gaps/ai-review` | JWT | Trigger async LLM review, returns `202 { job_id }` |
| GET | `/api/v1/work-items/{id}/gaps/questions` | JWT | Get next 3 prioritised questions |

### Suggestions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/work-items/{id}/suggestion-sets` | JWT | Generate new suggestion set, returns `202 { set_id }` |
| GET | `/api/v1/suggestion-sets/{set_id}` | JWT | Get suggestion set + items |
| POST | `/api/v1/suggestion-sets/{set_id}/apply` | JWT | Partial apply `{ "accepted_item_ids": ["uuid",...] }` |
| PATCH | `/api/v1/suggestion-items/{item_id}` | JWT | Update single item status |

### Quick Actions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/work-items/{id}/quick-actions` | JWT | `{ "section": "description", "action": "rewrite" }` |
| POST | `/api/v1/work-items/{id}/quick-actions/{action_id}/undo` | JWT | Undo within 10s window |

**SSE stream event format:**
```
event: token
data: {"content": "partial text..."}

event: done
data: {"message_id": "uuid"}

event: error
data: {"code": "LLM_TIMEOUT", "message": "..."}
```

**Suggestion apply response:**
```json
{ "data": { "new_version": 3, "applied_sections": ["description", "acceptance_criteria"] } }
```

---

## Phase 1 — Database Migrations

- [ ] [RED] Write migration schema tests: assert `conversation_threads` columns, UNIQUE `(work_item_id)` WHERE not null, enum values
- [ ] [GREEN] Create Alembic migration `conversation_threads`: all columns per design.md, UNIQUE partial index on `work_item_id`
- [ ] [RED] Write migration schema tests: assert `conversation_messages` columns, index on `(thread_id, created_at)`
- [ ] [GREEN] Create Alembic migration `conversation_messages`: all columns including `archived_at TIMESTAMPTZ`, `token_count`, `metadata JSONB`; index `idx_messages_thread_created`
- [ ] [GREEN] Create Alembic migration `assistant_suggestions`: single flat table with `id`, `work_item_id FK`, `thread_id FK NULLABLE`, `section_id FK NULLABLE`, `proposed_content`, `current_content`, `rationale`, `status ENUM(pending,accepted,rejected,expired)`, `version_number_target INT`, `batch_id UUID NOT NULL`, `created_by FK`, `created_at`, `updated_at`, `expires_at`; indexes: `idx_as_work_item_batch ON (work_item_id, batch_id, status)`, `idx_as_work_item_created ON (work_item_id, created_at DESC)`, `idx_as_batch ON (batch_id)`
- [ ] [GREEN] Create Alembic migration `gap_findings`: `id`, `work_item_id FK`, `source VARCHAR(20)` (rule|llm), `severity VARCHAR(20)`, `dimension VARCHAR(100)`, `message TEXT`, `created_at`, `invalidated_at`; index `idx_gap_findings_work_item ON (work_item_id, source, severity)`
- [ ] [REFACTOR] Verify all FK constraints and unique indexes match design.md

---

## Phase 2 — Domain Layer

### Gap Detection Rules

- [ ] Implement `domain/models/gap_finding.py` — `GapFinding` dataclass: `dimension`, `severity: GapSeverity`, `message`, `source: Literal['rule', 'llm']`; `GapReport` dataclass: `work_item_id`, `findings: list[GapFinding]`, `score: float`; `GapSeverity` enum: `blocking | warning | info`
- [ ] [RED] Write unit tests for `required_fields` rule: each WorkItemType has specific required fields; missing required field returns `GapFinding(severity=blocking)`; all fields present returns empty list
- [ ] [RED] Write unit tests for `content_quality` rule: description < 50 chars returns soft gap; vague phrases ("TBD", "TODO", "N/A" alone) trigger gap
- [ ] [RED] Write unit tests for `acceptance_criteria` rule: missing WHEN/THEN pattern in acceptance criteria field returns gap for applicable types; Task/Spike are not applicable
- [ ] [RED] Write unit tests for `hierarchy_rules` rule: Initiative without linked child items returns gap; Task without parent returns gap for applicable types
- [ ] [RED] Write unit tests for `GapDetector.detect()`: combines all rules, deduplicates identical `(dimension, severity)` pairs, sorts by severity (blocking first), score formula: `1.0 - (hard * 0.2 + soft * 0.05)` clamped to [0, 1]
- [ ] [GREEN] Implement rule functions in `domain/gap_detection/rules/`: `required_fields.py`, `content_quality.py`, `acceptance_criteria.py`, `hierarchy_rules.py`
- [ ] [GREEN] Implement `domain/gap_detection/gap_detector.py` — `GapDetector.detect(work_item) -> GapReport`
- [ ] [REFACTOR] All rule functions are pure: `(WorkItem) -> list[GapFinding]`, no I/O, 100% branch coverage

### Suggestion Domain Models

- [ ] [RED] Write unit tests: `AssistantSuggestion` entity — `pending → accepted` allowed; `pending → rejected` allowed; expired suggestion (`expires_at < now()`) raises `SuggestionExpiredError` on apply; accepted suggestion cannot be re-applied
- [ ] [RED] Write unit tests: `SuggestionBatch` value object (derived from list of suggestions) — `status` derived correctly: all pending=`pending`, mixed=`partially_applied`, all accepted/rejected=`fully_applied`; any expired=`expired`
- [ ] [GREEN] Implement `domain/models/assistant_suggestion.py` — `AssistantSuggestion` entity and `SuggestionBatch` value object

### Conversation Domain Models

- [ ] [RED] Write unit tests: `ConversationThread` — `thread_type=element` with `work_item_id=null` raises; `thread_type=general` with `work_item_id` set is allowed (non-element link); duplicate element thread constraint enforced at service layer
- [ ] [RED] Write unit tests: `ConversationMessage` — `author_type=human` requires `author_user_id`; `author_type=assistant` allows null `author_user_id`
- [ ] [GREEN] Implement `domain/models/conversation_thread.py` and `domain/models/conversation_message.py`

---

## Phase 3 — LLM Infrastructure

- [ ] [GREEN] Implement `domain/ports/llm_provider.py` — `LLMProvider` Protocol: `async complete(messages, prompt_template_id, prompt_version, max_tokens, stream) -> AsyncIterator[str] | LLMResponse`
- [ ] [GREEN] Implement `tests/fakes/fake_llm_adapter.py` — `FakeLLMAdapter` that returns configurable structured responses; used in all service and controller tests
- [ ] [RED] Write unit tests for `ResponseParser`: valid JSON parsed against schema, invalid JSON raises `LLMParseError`, schema mismatch raises `LLMParseError`, retry once on first failure
- [ ] [GREEN] Implement `infrastructure/llm/response_parser.py` — `ResponseParser` with `jsonschema` validation
- [ ] [RED] Write unit tests for `PromptRegistry`: loads YAML from `prompts/` directory, returns correct template by `(template_id, version)`, raises `PromptNotFoundError` on missing template
- [ ] [GREEN] Implement `infrastructure/llm/prompt_registry.py` — loads at startup, memory cache, no hot reload
- [ ] [GREEN] Write prompt YAML files in `infrastructure/llm/prompts/`:
  - `gap_detection/v1.yaml` — `system_prompt`, `user_prompt_template` (Jinja2), `output_schema`, `max_tokens: 2048`, `temperature: 0.1`
  - `guided_question/v1.yaml`
  - `suggestion_generation/v1.yaml` — structured output schema requiring `sections` array
  - `quick_action_rewrite/v1.yaml`, `quick_action_concretize/v1.yaml`, `quick_action_expand/v1.yaml`, `quick_action_shorten/v1.yaml`, `quick_action_generate_ac/v1.yaml`
  - `thread_summarisation/v1.yaml`
- [ ] [GREEN] Implement `infrastructure/llm/anthropic_adapter.py` — `AnthropicAdapter` implements `LLMProvider`; wraps `anthropic` SDK; streaming path uses `client.messages.stream()`
- [ ] [REFACTOR] Token counting with `tiktoken` (cl100k_base) integrated into adapter; hard budget (80k) enforced before every call; raises `TokenBudgetExceededError` if over limit

---

## Phase 4 — Repository Layer

- [ ] [RED] Write integration tests for `ConversationThreadRepository`: CRUD, unique element thread constraint enforced, `get_by_work_item_id` returns correct thread
- [ ] [RED] Write integration tests for `ConversationMessageRepository`: paginated load (oldest first), archived messages excluded from context query, `get_active_with_token_budget` returns messages up to token limit
- [ ] [RED] Write integration tests for `SuggestionSetRepository`: CRUD, `get_active_by_work_item` excludes expired sets, `update_status` transitions correctly
- [ ] [RED] Write integration tests for `GapFindingRepository`: insert, invalidate by `work_item_id`, get active (non-invalidated) findings
- [ ] [GREEN] Implement all 4 repository implementations with SQLAlchemy async
- [ ] [REFACTOR] Verify no N+1 on message load; use single query with JOIN for messages + thread data

---

## Phase 5 — Application Services

### ClarificationService

- [ ] [RED] Write unit tests using fake repo + fake LLM:
  - `get_gap_report(work_item_id)`: rule-based only, cached result served from Redis (fake cache hit → fake repo not called)
  - `trigger_llm_review(work_item_id)`: dispatches Celery task, returns `job_id`, does not block
  - `get_next_questions(work_item_id)`: returns top 3 `blocking` findings as formatted questions
- [ ] [GREEN] Implement `application/services/clarification_service.py`
- [ ] Redis cache key: `gap:{work_item_id}:{version}`, TTL 5 minutes; invalidated on `work_item.updated_at` change

### Acceptance Criteria — ClarificationService

See also: specs/clarification/spec.md (US-030)

WHEN `get_gap_report(work_item_id)` is called and a cached result exists in Redis
THEN the DB (gap_findings table) is NOT queried
AND the cached `GapReport` is returned as-is

WHEN `get_gap_report(work_item_id)` is called with no cache (miss)
THEN rule-based gap detection runs synchronously
AND result is stored in Redis with 5-min TTL before returning

WHEN `trigger_llm_review(work_item_id)` is called
THEN a Celery task is dispatched to `llm_low` queue
AND the service returns a `job_id` string immediately (does not await LLM)
AND no LLM call is made synchronously

WHEN `get_next_questions(work_item_id)` is called and there are 5 blocking findings
THEN exactly 3 questions are returned (max 3)
AND all 3 are from `blocking` severity findings (not warnings or info)
AND each question is phrased as human-readable text (not the raw `dimension` field name)

### ConversationService

- [ ] [RED] Write unit tests:
  - `get_or_create_element_thread(work_item_id)`: idempotent — returns existing thread if present, creates once
  - `send_message(thread_id, content, author_id)`: persists human message, dispatches `generate_llm_response` Celery task to `llm_high` queue, returns message ID
  - `build_context(thread_id)`: returns messages within 80k token budget, prepends summary message if older messages archived
  - `summarise_and_archive(thread_id)`: archives oldest messages until under 50k tokens, inserts `summary` type message
- [ ] [GREEN] Implement `application/services/conversation_service.py`

### Acceptance Criteria — ConversationService

See also: specs/conversation/spec.md (US-031)

WHEN `get_or_create_element_thread(work_item_id)` is called twice for the same work item
THEN the second call returns the SAME thread object (same `id`)
AND only one row exists in `conversation_threads` for that `work_item_id`

WHEN `send_message(thread_id, content="Hello", author_id=user_id)` is called
THEN a `ConversationMessage` row is inserted with `author_type = "human"`
AND a Celery task `generate_llm_response` is dispatched to the `llm_high` queue
AND the returned value is the persisted message's `id`
AND no LLM call is made synchronously

WHEN `build_context(thread_id)` is called and total token count exceeds 80,000
THEN only the most recent messages within the 80k budget are returned
AND if archived messages exist, a `summary` type message is prepended to the context

WHEN `summarise_and_archive(thread_id)` is called with 100k total tokens
THEN oldest messages are archived (`archived_at` set) until remaining count is < 50k tokens
AND a new `summary` message is inserted at the oldest-non-archived position
AND the archived messages remain in the DB (not deleted)

### SuggestionService

- [ ] [RED] Write unit tests:
  - `generate(work_item_id, user_id)`: dispatches Celery task, returns pending `batch_id`, does not block; all new suggestions share the same `batch_id`
  - `apply_partial(batch_id, accepted_suggestion_ids)`: happy path applies accepted suggestions (patches `work_item_sections` rows), calls `VersioningService.create_version(trigger='ai_suggestion')`, all in single transaction
  - `apply_partial`: version conflict (work item changed since generation) raises `VersionConflictError`
  - `apply_partial`: any suggestion in batch has `expires_at < now()` → raises `SuggestionExpiredError`
  - `apply_partial`: remaining batch suggestions marked `rejected`; applied ones marked `accepted`
  - `apply_partial` concurrent (Fixed per backend_review.md TC-1): WHEN two concurrent `apply_partial()` calls run for the same work_item THEN one succeeds and the other raises `VersionConflictError`; implementation MUST use `SELECT FOR UPDATE` on the work_item row to serialize concurrent applies
- [ ] [GREEN] Implement `application/services/suggestion_service.py` with transactional apply (design.md section 3.1)

### Acceptance Criteria — SuggestionService

See also: specs/suggestions/spec.md (US-032)

WHEN `generate(work_item_id, user_id)` is called
THEN `assistant_suggestions` rows are created with `status = "pending"` and a shared `batch_id`
AND a Celery task is dispatched to `llm_normal` queue
AND the returned `batch_id` is the UUID grouping the pending suggestions
AND no LLM call is made synchronously

WHEN `apply_partial(batch_id, accepted_suggestion_ids=["id1", "id2"])` is called and the work item version matches `version_number_target`
THEN accepted suggestions are patched onto the corresponding `work_item_sections` rows
AND `VersioningService.create_version(trigger='ai_suggestion', actor_type='ai_suggestion')` is called in the same transaction
AND remaining pending suggestions in the batch are set to `rejected`
AND the section updates and version snapshot are committed in a single DB transaction

WHEN `apply_partial(batch_id, accepted_suggestion_ids)` is called and the work item has changed since generation
THEN it raises `VersionConflictError` with the `current_version` and `version_number_target` in the error
AND no sections are modified

WHEN `apply_partial(batch_id, accepted_suggestion_ids)` is called and any suggestion in the batch has `expires_at < now()`
THEN it raises `SuggestionExpiredError`
AND no sections are modified

WHEN `apply_partial(batch_id, accepted_suggestion_ids=[])` (none accepted)
THEN all batch suggestions are set to `rejected`
AND no sections are modified

WHEN two concurrent `apply_partial()` calls execute for the same work_item simultaneously (Fixed per backend_review.md TC-1)
THEN one call succeeds and the other raises `VersionConflictError`
AND only one version is created in `work_item_versions`
AND no partial section updates are applied from the losing call

### QuickActionService

- [ ] [RED] Write unit tests:
  - `execute(work_item_id, section, action)`: each of 5 action types dispatches correct prompt template
  - `execute`: empty section content raises validation error
  - `execute`: LLM timeout marks action as failed, returns error
  - `undo(work_item_id, action_id)`: within 10s window reverts section content, marks version as reverted
  - `undo`: outside 10s window raises `UndoWindowExpiredError`
- [ ] [GREEN] Implement `application/services/quick_action_service.py` with undo TTL via Redis key `undo:{action_id}` TTL 10s

---

## Phase 6 — Celery Tasks

- [ ] [RED] Write integration tests using `FakeLLMAdapter`:
  - `generate_llm_response`: user message received, assistant message persisted with correct `prompt_template_id` + `prompt_version`, `context_token_count` updated on thread
  - `generate_suggestion_set`: suggestion items created with correct sections and status=pending, set status updated to pending_review
  - `run_background_gap_analysis`: LLM findings tagged `source=llm`, persisted to `gap_findings`, invalidates Redis cache
  - `summarise_thread_context`: messages above threshold archived, summary message inserted, token count reduced
- [ ] [RED] Test `generate_suggestion_set` idempotency on retry (Fixed per backend_review.md CA-1): WHEN task retries after partial item creation (e.g. 2 of 5 items inserted before network error) THEN the retry checks `suggestion_set.status == 'pending'` AND whether items already exist; if items exist, skip LLM call and proceed to status update; NO duplicate items or duplicate sets created
- [ ] [RED] Test `summarise_thread_context` distributed lock (Fixed per backend_review.md CA-4): WHEN two concurrent summarise tasks run for the same thread_id THEN only one summary is created; the second task exits early (Redis `SETNX summarise:{thread_id}` with TTL 120s)
- [ ] [GREEN] Implement Celery tasks in `infrastructure/tasks/llm_tasks.py`:
  - Queue assignments: `generate_llm_response` → `llm_high`; `generate_suggestion_set` → `llm_normal`; `run_background_gap_analysis` → `llm_low`; `summarise_thread_context` → `llm_low`
  - `generate_suggestion_set`: on task start, check if `suggestion_set.status != 'pending'` or items already exist → skip LLM, proceed to status update
  - `summarise_thread_context`: acquire Redis distributed lock `SETNX summarise:{thread_id}` TTL=120s before proceeding; release on completion or failure
- [ ] [REFACTOR] All tasks idempotent (safe to retry); `max_retries=3`, exponential backoff; task timeout 30s

---

## Phase 7 — API Controllers

- [ ] [RED] Write integration tests for `GET /api/v1/threads`: filter by `work_item_id`, filter by `type`, 401 unauthenticated
- [ ] [RED] Write integration tests for `POST /api/v1/threads`: general thread created with 201, element thread returns existing thread (idempotent)
- [ ] [RED] Write integration tests for `POST /api/v1/threads/{id}/messages`: human message stored, 202 returned with message_id, LLM Celery task dispatched (verify task enqueued via Celery test backend)
- [ ] [RED] Write integration tests for `GET /api/v1/threads/{id}/stream`: SSE `Content-Type: text/event-stream`, streaming tokens delivered in `event: token\ndata: ...` format, `event: done` sent with `message_id` when complete
- [ ] [RED] Write integration tests for `POST /api/v1/work-items/{id}/gaps/ai-review`: 202 + job_id, 401 unauthenticated, 404 work item not found
- [ ] [RED] Write integration tests for `POST /api/v1/work-items/{id}/suggestion-sets`: 202 + set_id
- [ ] [RED] Write integration tests for `POST /api/v1/suggestion-sets/{id}/apply`: 200 with `new_version` and `applied_sections`, 409 on version conflict, 422 on expired set
- [ ] [RED] Write integration tests for `POST /api/v1/work-items/{id}/quick-actions`: 200 with patched section content
- [ ] [RED] Write integration tests for `POST /api/v1/work-items/{id}/quick-actions/{id}/undo`: 200 within 10s window, 422 outside window
- [ ] [GREEN] Implement all controllers in `presentation/controllers/`
- [ ] [REFACTOR] All endpoints enforce authorization; thread access mirrors work_item read permission; IDOR check: user cannot access threads for work items they cannot see

### Acceptance Criteria — Controllers (Phase 7)

See also: specs/clarification/spec.md, specs/conversation/spec.md, specs/suggestions/spec.md

**GET /api/v1/threads?work_item_id={id}**
WHEN called by a user with read access to the work item
THEN response is HTTP 200 with an array of thread objects

WHEN called by a user who cannot read the work item
THEN response is HTTP 403 (IDOR prevention)

WHEN called unauthenticated
THEN response is HTTP 401

**POST /api/v1/threads with `{ thread_type: "element", work_item_id: "uuid" }`**
WHEN called for a work item that already has an element thread
THEN response is HTTP 200 with the EXISTING thread (idempotent, not 201)

WHEN called with `{ thread_type: "general" }` (no work_item_id)
THEN response is HTTP 201 with the new general thread

**POST /api/v1/threads/{thread_id}/messages**
WHEN called with `{ content: "Hello" }`
THEN response is HTTP 202 `{ "data": { "message_id": "uuid" } }`
AND the human message is stored in `conversation_messages`
AND a Celery `generate_llm_response` task is enqueued (verifiable via test backend)

WHEN called by a user without write access to the thread's work item
THEN response is HTTP 403

**GET /api/v1/threads/{thread_id}/stream**
WHEN the LLM is streaming
THEN response `Content-Type` is `text/event-stream`
AND events arrive as `event: token\ndata: {"content": "..."}\n\n`
AND stream ends with `event: done\ndata: {"message_id": "uuid"}\n\n`
AND on LLM error: `event: error\ndata: {"code": "LLM_TIMEOUT", "message": "..."}\n\n`

**POST /api/v1/work-items/{id}/gaps/ai-review**
WHEN called for a valid work item
THEN response is HTTP 202 `{ "data": { "job_id": "uuid" } }`

WHEN called for a non-existent work item
THEN response is HTTP 404

**POST /api/v1/work-items/{id}/suggestions/batches/{batch_id}/apply**
WHEN called with `{ "accepted_suggestion_ids": ["id1"] }` and no version conflict
THEN response is HTTP 200 `{ "data": { "new_version": N, "applied_sections": ["description"] } }`

WHEN version conflict exists
THEN response is HTTP 409 `{ "error": { "code": "VERSION_CONFLICT" } }`

WHEN batch suggestions have expired
THEN response is HTTP 422 `{ "error": { "code": "SUGGESTION_EXPIRED" } }`

**POST /api/v1/work-items/{id}/quick-actions/{action_id}/undo**
WHEN called within 10-second window
THEN response is HTTP 200 and section content is reverted

WHEN called after 10-second window has expired
THEN response is HTTP 422 `{ "error": { "code": "UNDO_WINDOW_EXPIRED" } }`

---

## Phase 8 — Security

- [ ] Security review: all thread and suggestion endpoints check that requesting user has permission for the related `work_item_id`
- [ ] LLM prompt injection: sanitize work item content before template variable interpolation (strip `{{`, `}}`, Jinja2 delimiters from user input)
- [ ] `prompt_template_id` and `prompt_version` stored on every assistant message for auditability

---

## Definition of Done

- [ ] All tests pass (unit + integration)
- [ ] `mypy --strict` clean
- [ ] `ruff` clean
- [ ] SSE endpoint streams tokens correctly (manual verification)
- [ ] All LLM tasks use `FakeLLMAdapter` in tests — no real API calls in test suite
- [ ] Suggestion apply transaction is atomic (verified: DB error mid-apply leaves no partial state)
- [ ] IDOR check verified: user A cannot read user B's threads
