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

- [x] [RED] Write migration schema tests: 15 new tests for conversation_threads, assistant_suggestions, gap_findings — columns, constraints, unique indexes, check constraints, FK behaviour (2026-04-16)
- [x] [GREEN] Create Alembic migration `conversation_threads` — `0014_create_conversation_threads.py`, revision `0014_conversation_threads`; UNIQUE(dundun_conversation_id), UNIQUE(user_id, work_item_id), work_item_id SET NULL on delete (2026-04-16)
- [x] [GREEN] Create Alembic migration `assistant_suggestions` — `0015_create_assistant_suggestions.py`, revision `0015_assistant_suggestions`; CHECK status IN (pending/accepted/rejected/expired), section_id bare UUID (no FK, EP-04 note), 4 indexes including partial on dundun_request_id (2026-04-16)
- [x] [GREEN] Create Alembic migration `gap_findings` — `0016_create_gap_findings.py`, revision `0016_gap_findings`; CHECK source IN (rule/dundun), CHECK severity IN (blocking/warning/info), idx_gap_findings_active partial index WHERE invalidated_at IS NULL (2026-04-16)
- [x] Do NOT create `conversation_messages`, `prompt_templates`, `llm_calls`, or any token-budget tables (decision #32) — confirmed, not created
- [x] [REFACTOR] All FK constraints, check constraints, unique indexes, and partial indexes verified by 24 passing schema tests (2026-04-16)

**Status: COMPLETED** (2026-04-16)

---

## Phase 2 — Domain Layer

### Gap Detection Rules

- [x] Implement `domain/models/gap_finding.py` — `GapFinding` dataclass: `dimension`, `severity: GapSeverity`, `message`, `source: Literal['rule', 'dundun']`; `GapReport` dataclass: `work_item_id`, `findings: list[GapFinding]`, `score: float`; `GapSeverity` enum: `blocking | warning | info` (2026-04-16)
- [x] [RED] Write unit tests for `required_fields` rule: each WorkItemType has specific required fields; missing required field returns `GapFinding(severity=blocking)`; all fields present returns empty list (2026-04-16)
- [x] [RED] Write unit tests for `content_quality` rule: description < 50 chars returns soft gap; vague phrases ("TBD", "TODO", "N/A" alone) trigger gap (2026-04-16)
- [x] [RED] Write unit tests for `acceptance_criteria` rule: missing WHEN/THEN pattern in acceptance criteria field returns gap for applicable types; Task/Spike are not applicable (2026-04-16)
- [x] [RED] Write unit tests for `hierarchy_rules` rule: Initiative without linked child items returns gap; Task without parent returns gap for applicable types (2026-04-16)
- [x] [RED] Write unit tests for `GapDetector.detect()`: combines all rules, deduplicates identical `(dimension, severity)` pairs, sorts by severity (blocking first), score formula: `1.0 - (hard * 0.2 + soft * 0.05)` clamped to [0, 1] (2026-04-16)
- [x] [GREEN] Implement rule functions in `domain/gap_detection/rules/`: `required_fields.py`, `content_quality.py`, `acceptance_criteria.py`, `hierarchy_rules.py` (2026-04-16)
- [x] [GREEN] Implement `domain/gap_detection/gap_detector.py` — `GapDetector.detect(work_item) -> GapReport` (2026-04-16)
- [x] [REFACTOR] GapDetector + 4 rule functions, 94 unit tests; all pure `(WorkItem) -> list[GapFinding]`; ruff clean, mypy --strict zero errors (2026-04-16)

### Suggestion Domain Models

- [x] [RED] Write unit tests: `AssistantSuggestion` entity — `pending → accepted` allowed; `pending → rejected` allowed; expired suggestion (`expires_at < now()`) raises `SuggestionExpiredError` on apply; accepted suggestion cannot be re-applied (2026-04-16 — 22 tests in test_assistant_suggestion.py + test_suggestion_batch.py)
- [x] [RED] Write unit tests: `SuggestionBatch` value object (derived from list of suggestions) — `status` derived correctly: all pending=`pending`, mixed=`partially_applied`, all accepted/rejected=`fully_applied`; any expired=`expired` (2026-04-16 — 12 tests in test_suggestion_batch.py)
- [x] [GREEN] Implement `domain/models/assistant_suggestion.py` — `AssistantSuggestion` entity and `SuggestionBatch` value object; `SuggestionExpiredError` + `InvalidSuggestionStateError` added to exceptions.py; 40/40 passing (2026-04-16)

### Conversation Domain Models

- [x] [RED] Write unit tests: `ConversationThread` — `(user_id, work_item_id)` uniqueness enforced at service layer; `work_item_id` NULL = general thread; `dundun_conversation_id` set on creation (2026-04-16 — 9 tests in test_conversation_thread.py)
- [x] [GREEN] Implement `domain/models/conversation_thread.py` (pointer-only; no `ConversationMessage` model — history owned by Dundun) (2026-04-16)

**Status: COMPLETED** (2026-04-16) — Phase 2 total: 134 unit tests (94 gap detection + 40 suggestion/conversation), 706 suite total, 94% coverage

---

## Phase 3 — Dundun Integration

- [x] [RED] Write unit tests for `DundunClient.invoke_agent(agent, user_id, conversation_id, work_item_id, callback_url, payload)`: happy path 202 returns `{request_id}`; 4xx/5xx raise typed errors; request headers carry `caller_role=employee`, `user_id`, bearer service key; `callback_url` included in payload (2026-04-16 — 21 tests in test_dundun_http_client.py)
- [x] [RED] Write unit tests for `DundunClient.chat_ws(conversation_id, user_id, work_item_id)`: opens WS to Dundun `/ws/chat` with correct headers; async iterator yields frames; propagates close (2026-04-16 — 3 tests)
- [x] [RED] Write unit tests for `DundunClient.get_history(conversation_id)`: returns empty list (Dundun has no read API per reference_dundun_api.md; deviation documented in port) (2026-04-16 — 2 tests)
- [x] [GREEN] Implement `infrastructure/adapters/dundun_http_client.py` (httpx AsyncClient for HTTP, `websockets` library for WS; timeouts from env; `get_history` returns [] with TODO — no Dundun read API) (2026-04-16)
- [x] [GREEN] Implement `tests/fakes/fake_dundun_client.py` — records calls in `invocations`; configurable `chat_frames`; `history_by_conversation`; `next_error` injection; used in all service/controller tests as the only fake at the Dundun boundary (2026-04-16 — 15 tests in test_fake_dundun_client.py)
- [x] [RED] Write unit tests for HMAC signature verification: valid → True; wrong body → False; wrong secret → False; empty/malformed → False; never raises (2026-04-16 — 10 tests in test_dundun_callback_verifier.py)
- [x] [GREEN] Implement `infrastructure/adapters/dundun_callback_verifier.py` (HMAC-SHA256 over raw body + shared secret; constant-time `hmac.compare_digest`; case-insensitive hex) (2026-04-16)
- [x] [GREEN] Implement `presentation/controllers/dundun_callback_controller.py` — routes by `agent` + `request_id`, persists result (`assistant_suggestions`, `gap_findings`); idempotency via `dundun_request_id` dedup; `wm_quick_action_agent` returns 501 (EP-04); `status=error` logs and returns 200; HMAC checked before Pydantic parse; 8 integration tests all green (2026-04-16)
- [x] [REFACTOR] No `anthropic`/`openai`/`litellm`/`tiktoken` in `pyproject.toml`; no prompt YAMLs; no `LLMProvider` protocol; no `ResponseParser` — confirmed clean (2026-04-16)

> **Note**: Callback controller deferred to Phase 3b pending Phase 4 repos. Total Phase 3 (partial): 45 new tests; ruff clean; mypy --strict zero errors.
> **Phase 3b COMPLETED (2026-04-16)**: 8 integration tests in `test_dundun_callback_controller.py`; ruff clean (new files); mypy --strict zero errors on new files; 845 total passing.

**Deviation from design.md §2.1**: `get_history` returns `[]` — Dundun v0.1.1 has no read API (reference_dundun_api.md). Platform must persist turns locally. Documented in `app/domain/ports/dundun.py`.
**Deviation from design.md §2.1**: Invoke endpoint is `POST /api/v1/webhooks/dundun/chat` (not `/api/v1/agents/<agent>/invoke`). Body maps `agent → source_workflow_id`, `user_id → customer_id` per Dundun's actual contract.
**Deviation from design.md §2.3 (adapter path)**: Implementation placed in `infrastructure/adapters/` (consistent with existing adapter pattern) rather than `infrastructure/dundun/` as design suggested.

---

## Phase 4 — Repository Layer

- [x] [RED] Write integration tests for `ConversationThreadRepository`: CRUD, UNIQUE `(user_id, work_item_id)` enforced, `get_by_user_and_work_item`, `get_by_dundun_conversation_id` (2026-04-16 — 14 tests in test_conversation_thread_repository.py)
- [x] [RED] Write integration tests for `AssistantSuggestionRepository`: CRUD, `get_by_dundun_request_id`, `list_pending_for_work_item`, `update_status` (2026-04-16 — 14 tests in test_assistant_suggestion_repository.py)
- [x] [RED] Write integration tests for `GapFindingRepository`: insert, invalidate by `work_item_id`, get active (non-invalidated) findings (2026-04-16 — 12 tests in test_gap_finding_repository.py)
- [x] [GREEN] Implement all 3 repository implementations with SQLAlchemy async. No `ConversationMessageRepository` (no table). ORM models added to `orm.py`, mappers in `mappers/`, ABCs in `domain/repositories/`, impls in `infrastructure/persistence/`. `conftest.py` TRUNCATE updated to include new tables. (2026-04-16 — 40 new tests all green; 791 total passing)
- [x] [REFACTOR] All queries use indexed columns: `idx_conversation_threads_user`, `idx_conversation_threads_work_item` (partial), `idx_as_work_item_batch` + `idx_as_dundun_request` (partial), `idx_gap_findings_active` (partial) — confirmed against migrations 0014/0015/0016 (2026-04-16)

**Deviation from design.md §3**: `GapFinding` remains a pure transient value object (used by rule engine). Added `StoredGapFinding` as the persisted entity — keeps rule layer clean while satisfying the repo interface.

**Status: COMPLETED** (2026-04-16)

---

## Phase 5 — Application Services

### ClarificationService

- [x] [RED] Write unit tests using fake repo + fake LLM:
  - `get_gap_report(work_item_id)`: rule-based only, cached result served from Redis (fake cache hit → fake repo not called)
  - `trigger_ai_review(work_item_id)`: dispatches Celery task invoking `wm_gap_agent` via Dundun; returns `request_id`; does not block
  - `get_next_questions(work_item_id)`: returns top 3 `blocking` findings as formatted questions
- [x] [GREEN] Implement `application/services/clarification_service.py`
- [x] Redis cache key: `gap:{work_item_id}:{version}`, TTL 5 minutes; invalidated on `work_item.updated_at` change
  — **COMPLETED** (2026-04-16): 14 tests, all green. Cache key embeds updated_at (auto-invalidation). Celery dispatch deferred to Phase 6 — service calls Dundun directly; Phase 6 wraps in task.

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

- [x] [RED] Write unit tests:
  - `get_or_create_thread(user_id, work_item_id=None)`: idempotent on `(user_id, work_item_id)`; creates local row + calls `DundunClient.create_conversation(user_id, work_item_id)`, storing `dundun_conversation_id`
  - `get_history(thread_id)`: delegates to `DundunClient.get_history`; refreshes `last_message_preview` and `last_message_at`
  - `archive_thread(thread_id)`: archives local pointer (sets `deleted_at`) without deleting Dundun history
- [x] [GREEN] Implement `application/services/conversation_service.py` (pointer lifecycle only — no message persistence, no context building, no token counting, no summarization)
  — **COMPLETED** (2026-04-16): 16 tests, all green. Dundun v0.1.1 has no create-conversation endpoint — local UUID used; platform adopts Dundun id on first chat response. Archived threads resurrected via update (no duplicate rows).

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

- [x] [RED] Write unit tests for `generate` + `list_pending_for_work_item` + `update_single_status`:
  - `generate(work_item_id, user_id)`: dispatches Dundun wm_suggestion_agent, returns batch_id, no DB rows created (16 tests)
  - `list_pending_for_work_item`: returns pending non-expired rows, excludes accepted/expired
  - `update_single_status`: accept/reject with expired and invalid-state guard
- [x] [GREEN] Implement `application/services/suggestion_service.py` — generate, list_pending, update_single_status
  — **COMPLETED** (2026-04-16): 16 tests, all green.
- [ ] [DEFERRED] `apply_partial(batch_id, accepted_suggestion_ids)`:
  - Requires `work_item_sections` table (EP-04) and `VersioningService.create_version` (EP-07)
  - TC-1 SELECT FOR UPDATE concurrency guard also deferred
  - Module docstring contains TODO: EP-04+EP-07 marker

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

- [ ] [SKIPPED — Phase 6+] `QuickActionService` — not in Phase 5 scope. Lines 247+ belong to Phase 6. No implementation in this phase.
  - `execute` / `undo` deferred; requires `work_item_sections` (EP-04) and undo TTL infra

**Status: PARTIALLY COMPLETED** (2026-04-16)
— ClarificationService: DONE (14 tests)
— ConversationService: DONE (16 tests)
— SuggestionService.generate + list_pending + update_single_status: DONE (16 tests)
— SuggestionService.apply_partial: DEFERRED (needs EP-04 work_item_sections + EP-07 VersioningService)
— QuickActionService: DEFERRED (Phase 6+, needs EP-04)

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
