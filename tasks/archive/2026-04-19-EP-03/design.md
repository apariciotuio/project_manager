# EP-03 — Technical Design: Clarification, Conversation & Assisted Actions (Dundun thin proxy)

> **Resolved 2026-04-14 (decisions_pending.md #17, #32)**: This epic is rewritten as a thin proxy to **Dundun** (external Tuio agentic system). No LLM SDK in our backend. No prompt registry, no prompt YAMLs, no LiteLLM, no OpenAI/Anthropic adapter, no context-window management, no summarization, no token counting in our code. All AI — chat, gap detection, suggestions, quick actions — is owned by Dundun. Our backend proxies HTTP+WS, enforces auth, and persists results.

## 1. Conversation Model — thread pointer to Dundun

Our DB keeps a thin pointer to each Dundun conversation. We do NOT replicate message history server-side; Dundun is the source of truth and we fetch history on demand.

```sql
CREATE TABLE conversation_threads (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    work_item_id            UUID REFERENCES work_items(id) ON DELETE SET NULL,  -- NULL for general/workspace threads
    dundun_conversation_id  TEXT NOT NULL UNIQUE,                               -- owned by Dundun
    last_message_preview    TEXT,                                              -- denormalized preview for inbox lists
    last_message_at         TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, work_item_id)  -- at most one thread per (user, work item)
);
```

`conversation_messages` is **removed** (or reduced to a cache-only table). Full history comes from `DundunClient.get_history(dundun_conversation_id)`.

## 2. Dundun Integration

### 2.1 DundunClient

```python
# infrastructure/dundun/dundun_client.py

class DundunClient:
    def __init__(self, base_url: str, service_key: str):
        self._http = httpx.AsyncClient(base_url=base_url, headers={"Authorization": f"Bearer {service_key}"}, timeout=30)
        self._ws_base = base_url.replace("http", "ws")

    async def invoke_agent(self, agent: str, user_id: UUID, conversation_id: str | None, work_item_id: UUID | None, callback_url: str, payload: dict) -> dict:
        """Async agent invocation via Celery + callback. Dundun returns 202 + request_id; result arrives at callback_url."""

    async def chat_ws(self, conversation_id: str, user_id: UUID, work_item_id: UUID | None):
        """Opens a WebSocket to Dundun `/ws/chat` — caller is our FastAPI WS handler proxying to the FE."""

    async def get_history(self, conversation_id: str) -> list[dict]: ...
```

All calls carry:
- `caller_role=employee`
- `user_id`
- `conversation_id` (when applicable)
- `work_item_id` (optional context hint)
- Dundun-side service API key from `DUNDUN_SERVICE_KEY` env var

### 2.2 Chat flow (WebSocket proxy)

```
FE WS → Our BE WS `/ws/conversations/:thread_id` → DundunClient.chat_ws → Dundun `/ws/chat`
```

Our BE verifies the JWT, workspace membership, and (when `work_item_id` is set) access to the work item before opening the upstream WS. Progress frames (`{"type": "progress", ...}`) and response frames (`{"type": "response", ...}`) are forwarded to the FE transparently, without persistence.

### 2.3 Async agent invocation (Celery + callback)

Suggestion generation, gap detection, breakdown generation, spec generation, and other agent tasks all use the same pattern:

1. Controller enqueues a Celery task on queue **`dundun`** (single queue — no `llm_high/default/low` split).
2. Celery worker calls `DundunClient.invoke_agent(agent=<name>, ..., callback_url=<BE>/api/v1/dundun/callback)`. Dundun responds 202 with `request_id`.
3. When generation completes, Dundun POSTs the result to our callback endpoint.
4. `/api/v1/dundun/callback` verifies the signature, persists the result (e.g. into `assistant_suggestions`), and emits a domain event for SSE push to the FE.
5. FE receives an SSE event (or polls `/suggestions?batch_id=`).

### 2.4 Gap detection

Calls Dundun agent `wm_gap_agent`. We store the returned gap list on our side for display; the agent itself is owned by Dundun.

### 2.5 Quick actions

Each quick action (`rewrite`, `concretize`, `expand`, `shorten`, `generate_ac`) maps to a Dundun agent invocation. No prompt templates in our repo.

### 2.6 Split-view UX and diff viewer (kept in-house)

The split-view proposal/comparison UX and the diff viewer remain ours. The diff viewer uses EP-07's stack (`remark` AST + `diff-match-patch`) and is independent from Dundun.

### 2.7 Agent YAMLs / prompt versions

Owned by the Dundun team in their repo. Not in ours. Our code never references a prompt ID, template version, or model name.

---

## 3. Suggestion Model

Single flat table `assistant_suggestions`. The previous two-table split (`suggestion_sets` + `suggestion_items`) is replaced. Grouping is via `batch_id` (a UUID assigned per generation job).

```
assistant_suggestions
  id                    UUID PK
  work_item_id          UUID FK work_items(id) NOT NULL
  thread_id             UUID FK conversation_threads(id) NULLABLE
  section_id            UUID FK work_item_sections(id) NULLABLE  -- null = whole-item
  proposed_content      TEXT NOT NULL
  current_content       TEXT NOT NULL                           -- snapshot at generation time
  rationale             TEXT
  status                ENUM(pending, accepted, rejected, expired)
  version_number_target INT NOT NULL                           -- work_item version when generated
  batch_id              UUID NOT NULL                          -- groups one generation run
  created_by            UUID FK users(id) NOT NULL
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
  expires_at            TIMESTAMPTZ NOT NULL                   -- created_at + 24h

  INDEX(work_item_id, batch_id, status)
  INDEX(work_item_id, created_at DESC)
  INDEX(batch_id)
```

**Batch semantics**: `batch_id` is a caller-generated UUID shared by all suggestions in one generation run. Partial apply operates on selected `id` values within a batch. Batch-level status is derived on read (not stored): all pending → `pending`; all accepted or rejected → `fully_applied`; mixed → `partially_applied`; any `expires_at < now()` → `expired`.

### 3.1 Partial patch application strategy

Each section maps to a row in `work_item_sections` (via `section_id` on the suggestion). Partial apply is a single transaction:

```
BEGIN;
  -- 1. Lock the work item row
  SELECT id, version_number FROM work_items WHERE id = ? FOR UPDATE;

  -- 2. Verify version hasn't changed since suggestion was generated
  IF current_version != batch_version_number_target THEN
    RAISE conflict_error;
  END IF;

  -- 3. For each accepted suggestion, call SectionService.save_section() (which calls VersioningService)
  --    For whole-item suggestions (section_id IS NULL), UPDATE work_items description field directly
  UPDATE work_item_sections SET content = <proposed_content> WHERE id = <section_id>;

  -- 4. Call VersioningService.create_version(trigger='ai_suggestion', actor_type='ai_suggestion')
  --    VersioningService handles the work_item_versions INSERT — never done here directly

  -- 5. Mark accepted suggestions
  UPDATE assistant_suggestions SET status = 'accepted', updated_at = now() WHERE id IN (?);

  -- 6. Mark remaining batch suggestions as rejected
  UPDATE assistant_suggestions SET status = 'rejected', updated_at = now()
    WHERE batch_id = ? AND status = 'pending';
COMMIT;
```

All-or-nothing for the transaction. If the DB write fails, nothing is applied. Conflict detected at step 2 is returned as HTTP 409 to the caller — never silently ignored.

---

## 4. Gap Detection Implementation

### 4.1 Rule-based engine

```
domain/gap_detection/
  gap_detector.py        # Orchestrator: runs rule set, returns GapReport
  rules/
    required_fields.py   # Hard gaps: missing required fields by element type
    content_quality.py   # Soft gaps: too short, vague language patterns
    acceptance_criteria.py  # WHEN/THEN pattern check for User Story
    hierarchy_rules.py   # Parent linkage checks
  models.py              # GapFinding, GapReport, GapSeverity
```

Rules are pure functions: `(work_item: WorkItem) -> list[GapFinding]`. No I/O. Fully unit-testable.

`GapDetector.detect(work_item)` runs all rules, deduplicates, sorts by severity, and returns `GapReport` with `score` (0.0–1.0).

Score formula: `1.0 - (hard_gap_count * 0.2 + soft_gap_count * 0.05)` clamped to [0, 1].

### 4.2 LLM-enhanced detection

`ClarificationService.run_llm_gap_analysis(work_item_id)`:
1. Loads work item.
2. Builds prompt with element content + type-specific context.
3. Calls `LLMProvider.complete()` with `gap_detection/v1` template.
4. Parses structured output into additional `GapFinding` records tagged `source=llm`.
5. Persists findings to `gap_findings` table (cache, TTL = element's `updated_at`).
6. Returns combined `GapReport`.

Gap findings are invalidated whenever the work item is updated (trigger or application-level hook).

---

## 5. API Endpoints

### Conversation

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/threads?work_item_id=&type=` | List threads (filter by element or general) |
| POST | `/api/v1/threads` | Create general thread |
| GET | `/api/v1/threads/{thread_id}` | Get thread + messages (paginated) |
| POST | `/api/v1/threads/{thread_id}/messages` | Send message (triggers async LLM response) |
| GET | `/api/v1/threads/{thread_id}/stream` | SSE stream for assistant responses |
| DELETE | `/api/v1/threads/{thread_id}` | Archive general thread (soft delete) |

### Gap Detection & Clarification

> **Note**: `GET /api/v1/work-items/{id}/gaps` is owned by EP-04 and returns completeness-based gaps. Content quality findings produced by EP-03 are returned inline in the clarification response and stored in `assistant_suggestions`, not via a separate `/gaps` endpoint.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/work-items/{id}/gaps/ai-review` | Trigger async LLM-enhanced review |
| GET | `/api/v1/work-items/{id}/gaps/questions` | Get next N prioritised questions |

### Suggestions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/work-items/{id}/suggestion-sets` | Generate new suggestion set (async) |
| GET | `/api/v1/suggestion-sets/{set_id}` | Get suggestion set + items |
| POST | `/api/v1/suggestion-sets/{set_id}/apply` | Apply partial selection `{ "accepted_item_ids": [...] }` |
| PATCH | `/api/v1/suggestion-items/{item_id}` | Update single item status |

### Quick Actions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/work-items/{id}/quick-actions` | `{ "section": "...", "action": "rewrite" }` |
| POST | `/api/v1/work-items/{id}/quick-actions/{action_id}/undo` | Undo within window |

---

## 6. Suggestion Flow Sequence Diagram

```
User              Frontend           API               ClarificationService   LLMAdapter         DB
 |                    |                |                       |                   |               |
 |--"Improve"--->     |                |                       |                   |               |
 |                    |--POST /suggestion-sets-->              |                   |               |
 |                    |                |--create SuggestionSet(status=pending)-->  |               |
 |                    |                |                       |                   |               |
 |                    |                |--generate_suggestions(work_item)-->       |               |
 |                    |                |                       |--complete(prompt)->               |
 |                    |                |                       |                   |--[LLM API]--->|
 |                    |                |                       |<--LLMResponse-----|               |
 |                    |                |                       |--parse_suggestions()              |
 |                    |                |<--SuggestionSet(items)|                   |               |
 |                    |                |--INSERT suggestion_items----------------->|               |
 |                    |                |--UPDATE set status=pending_review-------->|               |
 |                    |<--202 set_id---|                       |                   |               |
 |<--preview panel----|                |                       |                   |               |
 |                    |                |                       |                   |               |
 |--accept [A,C]-->   |                |                       |                   |               |
 |                    |--POST /apply { accepted_item_ids: [A,C] }-->               |               |
 |                    |                |--BEGIN TX-------------------------------->|               |
 |                    |                |   SELECT work_item FOR UPDATE             |               |
 |                    |                |   CHECK version match                     |               |
 |                    |                |   UPDATE work_items sections A, C         |               |
 |                    |                |   INSERT work_item_versions               |               |
 |                    |                |   UPDATE suggestion_items                 |               |
 |                    |                |--COMMIT---------------------------------->|               |
 |                    |<--200 {new_version, applied_sections}                      |               |
 |<--updated element--|                |                       |                   |               |
```

---

## 7. Performance Considerations

### Async LLM calls

All LLM calls are async. No synchronous blocking calls in request handlers. Pattern:

1. Request handler creates a pending record and returns 202 with a job/resource ID.
2. Celery task picks up the work, calls the LLM adapter, persists results.
3. Frontend polls (or receives SSE push) for completion.

For conversation messages (US-031), the LLM response is streamed directly via SSE — the 202 + poll pattern is not used here because the user is waiting interactively.

### Celery task queues

| Queue | Tasks | Priority |
|-------|-------|----------|
| `llm_high` | Conversation message responses (interactive) | High |
| `llm_normal` | Suggestion set generation | Normal |
| `llm_low` | Background gap analysis, context summarisation | Low |

Task timeout: 30s for all LLM tasks. On timeout, the record is marked `failed` with a user-visible error.

### Caching

- Gap reports are cached in Redis with key `gap:{work_item_id}:{version}`, TTL = 5 minutes. Invalidated on `work_item.updated_at` change.
- Prompt templates are loaded once at startup into memory. No per-request disk I/O.
- Suggestion sets are not cached (always freshly generated; idempotent via `source_version`).

### Database indexes (critical)

```sql
-- Thread message pagination
CREATE INDEX idx_messages_thread_created ON conversation_messages(thread_id, created_at);

-- Suggestion set lookup by element
CREATE INDEX idx_suggestion_sets_work_item ON suggestion_sets(work_item_id, status, created_at);

-- Gap findings by element
CREATE INDEX idx_gap_findings_work_item ON gap_findings(work_item_id, source, severity);
```

### Context window budget

Token counting uses `tiktoken` (cl100k_base) for approximate counts before sending to any provider. This prevents context overflow errors at the provider level.

---

## 8. Dependencies and Risks

| Risk | Mitigation |
|------|-----------|
| Low-quality AI suggestions erode trust | LLM findings always labelled; rule-based findings separate; user always in control of apply |
| Context window limits | Server-side summarisation (section 1.2); hard token budget enforced before every LLM call |
| Partial apply conflicts | Optimistic locking on `version_number`; HTTP 409 returned with conflict resolution options |
| LLM provider latency | All calls async; timeouts at 30s; graceful degradation to rule-based-only for gap detection |
| Stale suggestions | 24h expiry on suggestion sets; conflict detection at apply time |
| Thread context privacy | Access control enforced at thread level, mirrors work_item permissions |
