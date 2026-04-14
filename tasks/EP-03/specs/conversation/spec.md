# US-031 — Persistent Conversation Threads

## Summary

Every element has a persistent conversation thread. Users can also open general (workspace-level) threads not tied to any element. All threads are resumable at any time with full history. Messages can be authored by humans or the AI assistant.

---

## Definitions

| Term | Definition |
|------|-----------|
| Thread | A named, ordered sequence of messages scoped to either an element or the workspace |
| Element thread | A thread linked to a specific `work_item_id`; there is exactly one per element |
| General thread | A thread with no `work_item_id`; owned by a user; serves as a scratch space or multi-topic chat |
| Message | A single turn in a thread; has `author_type` (human | assistant), `content`, `timestamp`, `metadata` |
| Thread context | The last N messages passed to the LLM as context window; determined by token budget, not raw count |
| Resumption | Opening a previously visited thread and continuing from where it was left |

---

## Thread Model Constraints

- One element thread per work item (auto-created on first access, never deleted with the element).
- General threads are user-created; no upper limit per user in MVP.
- Thread history is immutable — messages are never edited or deleted (soft-delete max for admin).
- Assistant messages are stored with their full prompt reference (prompt_template_id + version) for auditability.
- Thread context window is managed server-side: when token count exceeds budget, oldest messages are summarised and archived, with the summary stored as a special `summary` message type.

---

## Scenarios

### US-031-01 — Element thread created automatically

WHEN a work item is created  
THEN an element thread is created in the background  
AND the thread is empty (no messages)  
AND the thread is accessible from the element detail view  

### US-031-02 — User opens element thread

WHEN a user navigates to the conversation panel on an element detail view  
THEN the element thread is loaded with full message history  
AND messages are displayed in chronological order  
AND the most recent message is visible without scrolling  
AND if the thread is empty, a prompt is shown ("Start a conversation about this element")  

### US-031-03 — User sends a message in an element thread

WHEN a user types and submits a message in an element thread  
THEN the message is persisted immediately with status `sent`  
AND the AI assistant processes the message asynchronously  
AND a loading indicator is shown while the assistant is responding  
AND the assistant response is streamed token-by-token to the UI when available  
AND both messages (user + assistant) are persisted once the response completes  

### US-031-04 — User resumes an element thread after leaving

WHEN a user returns to an element they previously had a conversation with  
THEN the full thread history is loaded  
AND the user can continue from the last message without re-establishing context  
AND if the thread context window was truncated, a summary banner is shown ("Earlier context summarised")  

### US-031-05 — User creates a general thread

WHEN a user opens the global assistant panel (not from an element)  
THEN a new general thread is created if none is active  
AND the thread is titled with the timestamp or user-provided name  
AND the user can rename the thread at any time  

### US-031-06 — User lists and switches general threads

WHEN a user opens the general assistant panel  
THEN a sidebar lists all their general threads sorted by last activity  
AND the user can select any thread to resume it  
AND the user can create a new thread at any time  

### US-031-07 — Linking a general thread message to an element

WHEN a user is in a general thread and mentions an element (by ID or name)  
THEN the system creates a soft link between the message and the element  
AND the element detail view shows a "referenced in conversation" indicator  
AND clicking the indicator navigates to the relevant thread message  

### US-031-08 — Thread context window management

WHEN a thread's token count exceeds the configured budget (e.g., 80k tokens)  
THEN the system summarises the oldest messages into a `summary` message type  
AND the original messages are archived (retained in storage, excluded from context)  
AND the summary is prepended to the context sent to the LLM on next turn  
AND the user still sees full history in the UI (summary is shown as a collapsible block)  

### US-031-09 — Thread visibility and access control

WHEN an element thread exists  
THEN only users with read access to the element can read the thread  
AND only users with write access to the element can post messages  

WHEN a general thread exists  
THEN only the owning user can read and write to it  
AND workspace admins can read (audit only) but cannot post  

### US-031-10 — Message delivery failure

WHEN the AI assistant fails to respond (timeout or provider error)  
THEN the user's message is still persisted  
AND an error message is appended as a system message in the thread  
AND the user can retry the last message with a single action  

---

## Out of Scope (US-031)

- Multi-user real-time collaborative threads (no live sync in MVP; user refreshes or polls)
- Attachments or file uploads in threads
- Thread export or download
- Element threads visible to external users (Jira export does not include conversation)
