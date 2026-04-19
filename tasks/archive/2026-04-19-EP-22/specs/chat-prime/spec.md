# Chat Prime Specs — EP-22

## US-221: Chat is primed with original_input as the first user message

### Overview

When a work item is created, the backend emits `WorkItemCreatedEvent`. A new subscriber listens for this event and, if `original_input` is a non-empty string, performs two steps:

1. Calls `ConversationService.get_or_create_thread(workspace_id, user_id=creator_id, work_item_id)` — idempotent.
2. Sends `original_input` as a user-authored message to Dundun on that thread's `dundun_conversation_id`.

On the frontend, the chat renders that message as a standard user bubble (indistinguishable from a message the user typed themselves). Dundun stores it in its own conversation history and (optionally) produces an immediate assistant response.

---

### Scenario: Thread created and primed with original_input on creation

WHEN `WorkItemCreatedEvent` fires with a non-empty `original_input`
THEN the subscriber calls `ConversationService.get_or_create_thread` for (workspace_id, creator_id, work_item_id)
AND exactly one thread row exists for (creator_id, work_item_id)
AND the subscriber forwards `original_input` (verbatim, untrimmed) to Dundun as a user message on that thread's `dundun_conversation_id`
AND the send carries `caller_role=employee`, `user_id=creator_id`, and (when Dundun supports it) `work_item_id` as context hint

---

### Scenario: original_input empty — no prime

WHEN `WorkItemCreatedEvent` fires with `original_input` being `None` or an empty string
THEN the subscriber creates (or reuses) the thread
AND NO primer message is sent to Dundun
AND the chat renders empty (the existing "start a conversation" placeholder is shown)

---

### Scenario: original_input whitespace-only — treated as empty

WHEN `WorkItemCreatedEvent` fires with `original_input` being only whitespace
THEN the subscriber does NOT send a primer message
AND the thread is still created idempotently

---

### Scenario: Frontend renders the primed message as a user bubble

WHEN the user lands on the SplitView after creation
AND the thread history (via GET `/threads/{id}/history` or local cache) returns the primer turn
THEN the first message rendered in the `ChatPanel` is a user bubble with `content === original_input`
AND it is indistinguishable visually from a message the user would have typed
AND no "(primer)" / "(system)" label is shown (decision #2: transparency + honesty to the user)

---

### Scenario: Subscriber failure does not break creation

WHEN the subscriber fails (Dundun unavailable, network error, thread creation throws)
THEN `WorkItemService.create` still returns HTTP 201 to the caller
AND the failure is logged with `event_id` for later retry/observability
AND the work item remains intact in Draft state
AND the next time the user opens the work item, the thread auto-creates lazily via `get_or_create_thread`; the primer is NOT re-sent (see Idempotency scenario)

---

### Scenario: Idempotency — event redelivered does not duplicate primer

WHEN the same `WorkItemCreatedEvent` is received twice (e.g., retry after transient failure)
THEN the thread is created exactly once (existing `unique(user_id, work_item_id)` constraint)
AND the primer is sent at most once to Dundun
AND duplication is prevented by a `primer_sent_at` flag on the `conversation_threads` row — the subscriber checks it before sending and updates it atomically after send succeeds

---

### Scenario: Dundun responds — assistant bubble follows primer

WHEN Dundun processes the primer message and returns a response
AND the user is present on the detail page WebSocket
THEN the assistant response arrives over the existing `/ws/conversations/{thread_id}` WS channel
AND the chat renders it as an assistant bubble directly after the user primer bubble

---

### Scenario: Thread is owned by the creator

WHEN the primer subscriber creates the thread
THEN the thread's `user_id` is the `creator_id` from the event
AND NOT the owner_id (if those differ)
AND subsequent users opening the same work item see their own thread created lazily by `get_or_create_thread` on first access
