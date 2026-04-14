# EP-03 Backend Tasks — Clarification, Conversation & Assisted Actions (Dundun thin proxy)

Branch: `feature/ep-03-backend`
Refs: EP-03
Depends on: EP-01 backend (work_items), EP-02 backend (draft/template infra)

> **Scope (2026-04-14, decisions_pending.md #17, #32)**: Thin proxy to **Dundun**. **Remove** from the checklists below: `LLMProvider` protocol, `AnthropicAdapter`, `ResponseParser`, `PromptRegistry`, prompt YAML files, `FakeLLMAdapter`, `tiktoken`, token-budget enforcement, `conversation_messages` table and repo, `build_context`, `summarise_and_archive`, `summarise_thread_context` task, SSE streaming endpoint with `LLM_TIMEOUT` payload. **Keep**: gap-detection rules (in-house), suggestion domain + apply, quick-action domain + undo, diff viewer FE stack. **Add**: `DundunClient` (HTTP+WS), `FakeDundunClient`, `/api/v1/dundun/callback` HMAC-verified endpoint, single Celery queue `dundun`, WS proxy `WS /ws/conversations/:thread_id` to Dundun `/ws/chat`. `conversation_threads` is a pointer-only table (no messages). See `design.md`.

---

## API Contract (Frontend Dependency)

### Conversation

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/threads?work_item_id={id}` | JWT | List current user's threads |
| POST | `/api/v1/threads` | JWT | Get-or-create thread for `(user_id, work_item_id?)` |
| GET | `/api/v1/threads/{thread_id}` | JWT | Get thread pointer + last_message preview |
| GET | `/api/v1/threads/{thread_id}/history` | JWT | Fetch history from Dundun via `DundunClient.get_history` |
| WS  | `/ws/conversations/{thread_id}` | JWT | Proxies to Dundun `/ws/chat` (chat transport; no REST `POST /messages`) |
| DELETE | `/api/v1/threads/{thread_id}` | JWT | Archive local pointer (does not delete Dundun history) |

### Gap Detection & Clarification

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/work-items/{id}/gaps/ai-review` | JWT | EP-04 endpoint — enqueue Dundun `wm_gap_agent` via Celery + callback, returns `202 { request_id }` (EP-03 doesn't own this path; listed for cross-ref only) |
| GET | `/api/v1/work-items/{id}/gaps/questions` | JWT | Get next 3 prioritised questions (rules-based, local) |

### Dundun Callback

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/dundun/callback` | HMAC signature | Dundun delivers async agent results (suggestion/gap/quick-action/breakdown/spec-gen) |

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

**Chat transport**: WebSocket only. Our BE WS endpoint proxies to Dundun `/ws/chat`. Frame format is owned by Dundun:
```
{"type": "progress", "content": "..."}
{"type": "response", "content": "...", "message_id": "<dundun-id>"}
{"type": "error", "code": "<dundun-error-code>", "message": "..."}
```
Frames are forwarded verbatim; our BE does NOT interpret content, only enforces auth and closes the upstream on client disconnect.

**Suggestion apply response:**
```json
{ "data": { "new_version": 3, "applied_sections": ["description", "acceptance_criteria"] } }
```

---

## Phase 1 — Database Migrations

- [ ] [RED] Write migration schema tests: assert `conversation_threads` columns (id, user_id, work_item_id NULLABLE, dundun_conversation_id TEXT UNIQUE, last_message_preview, last_message_at, created_at), UNIQUE `(user_id, work_item_id)`
- [ ] [GREEN] Create Alembic migration `conversation_threads` (pointer-only)
- [ ] [GREEN] Create Alembic migration `assistant_suggestions`: single flat table with `id`, `work_item_id FK`, `thread_id FK NULLABLE`, `section_id FK NULLABLE`, `proposed_content`, `current_content`, `rationale`, `status ENUM(pending,accepted,rejected,expired)`, `version_number_target INT`, `batch_id UUID NOT NULL`, `dundun_request_id TEXT`, `created_by FK`, `created_at`, `updated_at`, `expires_at`; indexes: `idx_as_work_item_batch ON (work_item_id, batch_id, status)`, `idx_as_work_item_created ON (work_item_id, created_at DESC)`, `idx_as_batch ON (batch_id)`, `idx_as_dundun_request ON (dundun_request_id)`
- [ ] [GREEN] Create Alembic migration `gap_findings`: `id`, `work_item_id FK`, `source VARCHAR(20)` (rule|dundun), `severity VARCHAR(20)`, `dimension VARCHAR(100)`, `message TEXT`, `dundun_request_id TEXT NULL`, `created_at`, `invalidated_at`; index `idx_gap_findings_work_item ON (work_item_id, source, severity)`
- [ ] Do NOT create `conversation_messages`, `prompt_templates`, `llm_calls`, or any token-budget tables (decision #32)
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

- [ ] [RED] Write unit tests: `ConversationThread` — `(user_id, work_item_id)` uniqueness enforced at service layer; `work_item_id` NULL = general thread; `dundun_conversation_id` set on creation
- [ ] [GREEN] Implement `domain/models/conversation_thread.py` (pointer-only; no `ConversationMessage` model — history owned by Dundun)

---

## Phase 3 — Dundun Integration

- [ ] [RED] Write unit tests for `DundunClient.invoke_agent(agent, user_id, conversation_id, work_item_id, callback_url, payload)`: happy path 202 returns `{request_id}`; 4xx/5xx raise typed errors; request headers carry `caller_role=employee`, `user_id`, bearer service key; `callback_url` included in payload
- [ ] [RED] Write unit tests for `DundunClient.chat_ws(conversation_id, user_id, work_item_id)`: opens WS to Dundun `/ws/chat` with correct headers; async iterator yields frames; propagates close
- [ ] [RED] Write unit tests for `DundunClient.get_history(conversation_id)`: returns ordered list; 404 raises `DundunNotFoundError`
- [ ] [GREEN] Implement `infrastructure/dundun/dundun_client.py` (httpx AsyncClient for HTTP, `websockets` library for WS; timeouts from env)
- [ ] [GREEN] Implement `tests/fakes/fake_dundun_client.py` — records calls; configurable responses; used in all service/controller tests as the only fake at the Dundun boundary
- [ ] [RED] Write unit tests for HMAC signature verification on `/api/v1/dundun/callback` (invalid signature → 401; valid + unknown `request_id` → 404; valid + known → 200 and result persisted)
- [ ] [GREEN] Implement `infrastructure/dundun/callback_verifier.py` (HMAC-SHA256 over raw body + shared secret from `DUNDUN_CALLBACK_SECRET`)
- [ ] [GREEN] Implement `presentation/controllers/dundun_callback_controller.py` — routes by `agent` + `request_id`, persists result (`assistant_suggestions`, `gap_findings`, `task_proposals`, etc.), emits in-process domain event for SSE push to FE
- [ ] [REFACTOR] No `anthropic`/`openai`/`litellm`/`tiktoken` in `pyproject.toml`; no prompt YAMLs; no `LLMProvider` protocol; no `ResponseParser`

---

## Phase 4 — Repository Layer

- [ ] [RED] Write integration tests for `ConversationThreadRepository`: CRUD, UNIQUE `(user_id, work_item_id)` enforced, `get_by_user_and_work_item`, `get_by_dundun_conversation_id`
- [ ] [RED] Write integration tests for `AssistantSuggestionRepository`: CRUD, `get_by_dundun_request_id`, `list_pending_for_work_item`, `update_status`
- [ ] [RED] Write integration tests for `GapFindingRepository`: insert, invalidate by `work_item_id`, get active (non-invalidated) findings
- [ ] [GREEN] Implement all 3 repository implementations with SQLAlchemy async. No `ConversationMessageRepository` (no table).
- [ ] [REFACTOR] All queries use indexed columns

---

## Phase 5 — Application Services

### ClarificationService

- [ ] [RED] Write unit tests using fake repo + fake LLM:
  - `get_gap_report(work_item_id)`: rule-based only, cached result served from Redis (fake cache hit → fake repo not called)
  - `trigger_ai_review(work_item_id)`: dispatches Celery task invoking `wm_gap_agent` via Dundun; returns `request_id`; does not block
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

WHEN `trigger_ai_review(work_item_id)` is called
THEN a Celery task is dispatched to queue `dundun` (single queue) invoking `wm_gap_agent` via `DundunClient.invoke_agent(...)`
AND the service returns a `request_id` string immediately (does not await Dundun)
AND no Dundun call is made synchronously

WHEN `get_next_questions(work_item_id)` is called and there are 5 blocking findings
THEN exactly 3 questions are returned (max 3)
AND all 3 are from `blocking` severity findings (not warnings or info)
AND each question is phrased as human-readable text (not the raw `dimension` field name)

### ConversationService

- [ ] [RED] Write unit tests:
  - `get_or_create_thread(user_id, work_item_id=None)`: idempotent on `(user_id, work_item_id)`; creates local row + calls `DundunClient.create_conversation(user_id, work_item_id)`, storing `dundun_conversation_id`
  - `get_history(thread_id)`: delegates to `DundunClient.get_history`; refreshes `last_message_preview` and `last_message_at`
  - `archive_thread(thread_id)`: archives local pointer (sets `deleted_at`) without deleting Dundun history
- [ ] [GREEN] Implement `application/services/conversation_service.py` (pointer lifecycle only — no message persistence, no context building, no token counting, no summarization)

### Acceptance Criteria — ConversationService

See also: specs/conversation/spec.md (US-031)

WHEN `get_or_create_thread(user_id, work_item_id)` is called twice for the same `(user_id, work_item_id)`
THEN the second call returns the SAME thread (same `id`, same `dundun_conversation_id`)
AND only one row exists in `conversation_threads`

WHEN `get_history(thread_id)` is called
THEN `DundunClient.get_history(dundun_conversation_id)` is invoked
AND the returned list is passed back to the caller
AND `last_message_preview` + `last_message_at` are refreshed on the local row

WHEN `archive_thread(thread_id)` is called
THEN the local row has `deleted_at = now()`
AND NO call is made to Dundun (history preserved externally)

### SuggestionService

- [ ] [RED] Write unit tests:
  - `generate(work_item_id, user_id)`: creates pending `assistant_suggestions` batch, enqueues Celery task that invokes `DundunClient.invoke_agent(agent="wm_suggestion_agent", callback_url=...)` on queue `dundun`; returns `batch_id`; does not block
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
AND a Celery task is dispatched to queue `dundun` (the single agent queue)
AND the returned `batch_id` is the UUID grouping the pending suggestions
AND no Dundun call is made synchronously

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
  - `execute(work_item_id, section, action)`: each of 5 action types (`rewrite`/`concretize`/`expand`/`shorten`/`generate_ac`) maps to a Dundun agent invocation via Celery + callback
  - `execute`: empty section content raises validation error (before enqueuing)
  - `execute`: Dundun timeout/error marks action as failed in callback; action status visible to FE
  - `undo(work_item_id, action_id)`: within 10s window reverts section content, marks version as reverted
  - `undo`: outside 10s window raises `UndoWindowExpiredError`
- [ ] [GREEN] Implement `application/services/quick_action_service.py` with undo TTL via Redis key `undo:{action_id}` TTL 10s

---

## Phase 6 — Celery Tasks (single `dundun` queue)

- [ ] [RED] Write integration tests using `FakeDundunClient`:
  - `invoke_suggestion_agent(batch_id)`: calls `DundunClient.invoke_agent(agent="wm_suggestion_agent", ...)`; sets `dundun_request_id` on batch rows; persists nothing else until callback
  - `invoke_gap_agent(work_item_id)`: calls `DundunClient.invoke_agent(agent="wm_gap_agent", ...)`; returns `request_id`
  - `invoke_quick_action_agent(action_id, action_type)`: dispatches correct agent per action type
- [ ] [RED] Test idempotency on retry (Fixed per backend_review.md CA-1): WHEN the task retries after a partial failure THEN it checks the `dundun_request_id` and existing batch status; if already invoked, skip re-invocation; NO duplicate Dundun request
- [ ] [RED] Test callback flow: `/api/v1/dundun/callback` with `agent=wm_suggestion_agent` persists `suggestion_items` for the referenced `batch_id` and transitions the batch to `pending` (awaiting user review); emits SSE event to the author
- [ ] [RED] Test callback flow: `/api/v1/dundun/callback` with `agent=wm_gap_agent` writes `gap_findings` tagged `source=dundun` and invalidates Redis gap cache
- [ ] [GREEN] Implement Celery tasks in `infrastructure/tasks/dundun_tasks.py` on queue `dundun` (single queue — no `llm_high/normal/low` split)
- [ ] [REFACTOR] All tasks idempotent on retry via `dundun_request_id` check; `max_retries=3`, exponential backoff

---

## Phase 7 — API Controllers

- [ ] [RED] Write integration tests for `GET /api/v1/threads`: filters by `work_item_id`, scoped to current user; 401 unauthenticated
- [ ] [RED] Write integration tests for `POST /api/v1/threads`: `{ work_item_id?: uuid }` — idempotent get-or-create for the `(user_id, work_item_id)` pair; 200 on existing, 201 on created
- [ ] [RED] Write integration tests for `GET /api/v1/threads/{id}/history`: delegates to Dundun and returns history array; 404 if thread missing; 403 if not thread owner
- [ ] [RED] Write integration tests for `WS /ws/conversations/{thread_id}`: JWT check on handshake, workspace + work_item access check, upstream WS to Dundun opened, frames forwarded both ways; upstream close propagates to FE
- [ ] [RED] Write integration tests for `POST /api/v1/dundun/callback`: invalid HMAC → 401; unknown `request_id` → 404; valid suggestion callback → 200 with items persisted; valid gap callback → 200 with findings persisted
- [ ] [RED] Write integration tests for `POST /api/v1/work-items/{id}/suggestion-sets`: 202 + batch_id
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

**POST /api/v1/threads with `{ work_item_id?: "uuid" }`**
WHEN called for a `(user, work_item)` pair that already has a thread
THEN response is HTTP 200 with the EXISTING thread (idempotent, not 201)

WHEN called with no `work_item_id` and no general thread exists for the user
THEN response is HTTP 201 with a new general thread

**WS /ws/conversations/{thread_id}**
WHEN the client sends an unauthenticated handshake
THEN the upgrade is rejected with 401

WHEN the client handshakes with a valid JWT but lacks access to the thread or its work_item
THEN the upgrade is rejected with 403

WHEN the handshake succeeds
THEN our BE opens an upstream WS to Dundun `/ws/chat` with headers `caller_role=employee`, `user_id`, `conversation_id`
AND frames are forwarded verbatim in both directions
AND when either side closes, the other is closed within 500ms

**POST /api/v1/dundun/callback**
WHEN the `X-Dundun-Signature` header doesn't match HMAC(SHA256, body, DUNDUN_CALLBACK_SECRET)
THEN response is HTTP 401

WHEN the `request_id` in the payload is unknown
THEN response is HTTP 404

WHEN valid and `agent=wm_suggestion_agent`
THEN `suggestion_items` are persisted under the referenced `batch_id`
AND the batch status transitions to `pending` (awaiting user review)
AND a domain event is emitted for SSE delivery to the author

**POST /api/v1/work-items/{id}/gaps/ai-review**  (EP-04-owned endpoint)
WHEN called for a valid work item
THEN response is HTTP 202 `{ "data": { "request_id": "uuid" } }`

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

- [ ] Security review: all thread, suggestion, and WS endpoints check that the requesting user has access to the related `work_item_id` (IDOR); threads are always scoped to the calling `user_id`
- [ ] Dundun callback HMAC signature verified on every request; secret held in `DUNDUN_CALLBACK_SECRET` env var, never logged
- [ ] `request_id` binding: a callback MUST reference an outstanding `dundun_request_id` stored on the target entity (`assistant_suggestions.dundun_request_id`, `gap_findings.dundun_request_id`, etc.) to prevent cross-user tampering
- [ ] No prompt-template auditing in our DB (prompts owned by Dundun/LangSmith — decision #32)

---

## Definition of Done

- [ ] All tests pass (unit + integration)
- [ ] `mypy --strict` clean
- [ ] `ruff` clean
- [ ] WS proxy correctly forwards frames in both directions (manual verification against a Dundun stub)
- [ ] All Dundun tasks use `FakeDundunClient` in tests — no real API calls in test suite
- [ ] Suggestion apply transaction is atomic (verified: DB error mid-apply leaves no partial state)
- [ ] IDOR check verified: user A cannot read user B's threads
- [ ] No `anthropic` / `openai` / `litellm` / `tiktoken` / prompt YAMLs in the repo
