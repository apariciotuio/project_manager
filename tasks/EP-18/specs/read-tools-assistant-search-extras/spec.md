# EP-18 · Capability 4 — Read Tools: Assistant, Semantic Search, Extras

## Scope

Read-only exposure of Dundun clarification threads, Puppet semantic search, tags, labels, attachments metadata, inbox, workspace dashboard, and Jira snapshot status.

## In Scope

- `assistant.threads.get`, `assistant.threads.workspace`
- `semantic.search` (Puppet proxy)
- `tags.list`, `tags.workitems`, `labels.list`
- `attachments.list` (metadata + on-demand signed URL)
- `inbox.list`
- `workspace.dashboard`
- `jira.snapshot`

## Out of Scope

- Writing to threads (no `assistant.chat.send`)
- Binary attachment streaming via MCP
- Admin writes (dashboards are read-only views)
- Cross-workspace Puppet searches

## Scenarios

### `assistant.threads.get(work_item_id)`

- WHEN caller can read the work item THEN the tool returns `{ messages: [{ id, role: user|assistant|system, content, proposed_sections?: [{ section_id, body_excerpt }], segments?: [{ id, accepted: bool, applied_at? }], created_at }], last_activity_at }`
- WHEN the thread has > 200 messages THEN only the latest 200 are returned with `has_more: true` and `oldest_cursor` for future pagination
- WHEN a message contains a proposed section that references a section the caller cannot see THEN that proposal is omitted but the message itself is listed (never silently dropped)
- AND the tool description explicitly labels assistant content as **untrusted input** (prompt-injection note for external agents consuming it)

### `assistant.threads.workspace()`

- WHEN called THEN returns workspace-general Dundun threads readable by the caller with `{ id, title, last_activity_at, message_count }` — body is NOT included; body requires a future `assistant.threads.getWorkspace(id)` tool (not in MVP)

### `semantic.search(q, filters?, include_external?, limit, cursor)`

- WHEN called THEN the server forwards to Puppet with the caller's workspace scope, attaches caller capabilities to the upstream request, and returns `{ results: [{ kind: workitem|section|comment|external_doc, id, title, snippet_html, score, source, url? }], facets: { state, type, owner, team, tags, archived } }`
- WHEN `include_external: true` THEN Tuio-docs results are included, labeled `source: "tuio-docs"`, separated in ranking
- WHEN Puppet is unreachable (timeout 3 s / 5xx) THEN the tool returns `-32010 upstream_unavailable` with `{ upstream: "puppet", retriable: true }` — no silent fallback, no keyword-only downgrade
- WHEN the caller provides a filter referencing a workspace-foreign id (e.g., tag from another workspace) THEN `-32003`
- WHEN Puppet returns a result that points to an entity the caller cannot read (authz drift) THEN the result is **dropped server-side** before reaching the client — never leak existence
- AND `snippet_html` is sanitized: only `<em>`, `<strong>`, `<br>` tags allowed; everything else HTML-escaped

### `tags.list(include_archived?)`

- WHEN called THEN returns tags with `{ id, name, color, icon?, archived, usage_count }` ordered by `usage_count DESC` then `name ASC`
- WHEN `include_archived: false` (default) THEN archived tags are omitted

### `tags.workitems(tag_ids, mode, cursor)`

- WHEN `mode: "and"` THEN items are those carrying **all** `tag_ids`
- WHEN `mode: "or"` THEN items are those carrying **any** of `tag_ids`
- WHEN `tag_ids` contains > 20 ids THEN `-32602 invalid_params` `TOO_MANY_TAGS`
- AND the response uses the same work-item shape as `workitem.search.items`

### `labels.list()`

- WHEN called THEN returns workspace labels `{ id, name, color, archived }` — labels are distinct from tags (functional spec terminology)

### `attachments.list(work_item_id)`

- WHEN caller can read the work item THEN returns metadata only: `{ id, name, mime, size_bytes, uploader: { id, display_name }, created_at, thumbnail_url?, is_pdf_first_page_available: bool }`
- WHEN the tool is called THEN it **never** returns binary or direct-download URLs
- WHEN caller additionally requests `attachments.signedUrl(attachment_id)` THEN the server issues a URL with TTL ≤ 5 minutes, scoped to that single attachment id, requiring the same bearer on retrieval

### `inbox.list(cursor)`

- WHEN called THEN returns items ordered by priority per §3.8: pending_reviews > returned_items > blocking_dependencies > pending_decisions
- AND each item contains `{ kind, work_item_id, work_item_title, priority_rank, context: { section_id?, version_id?, review_id? }, available_quick_actions: ["reply", "approve", ...] (read-only enumeration, not executable) }`
- AND items older than 30 days are automatically excluded to keep the payload bounded; future `include_archived` option tracked for follow-up

### `workspace.dashboard()`

- WHEN called by any workspace member THEN the tool returns the 4 blocks where the caller has visibility. Admin blocks are **omitted** (not errored) if the caller lacks admin capabilities
- AND each block is a structured object:
  - `workspace_health`: `{ states: { [state]: count }, blockers: count, avg_time_to_ready_days, aged_reviews: count }`
  - `organizational`: `{ members_without_team: count, overloaded_owners: [{ user_id, active_items }] }` — admin only
  - `process`: `{ missed_validations: count, override_ratio, blocked_backlog: count }` — admin only
  - `integrations`: `{ jira: { status: ok|degraded|down, last_error?, failed_exports: count }, puppet: { status, last_error? } }` — admin only

### `jira.snapshot(work_item_id)`

- WHEN the item has been exported at least once THEN the tool returns `{ exported: true, issue_key, exported_version_id, exported_at, current_version_id, diverged: bool, divergence_summary?: { sections_changed: [...] } }`
- WHEN the item has never been exported THEN returns `{ exported: false }` — not an error
- WHEN caller cannot read the work item THEN `-32003`

## Security (Threat → Mitigation)

| Threat | Mitigation |
|---|---|
| Puppet authz drift (upstream returns items caller shouldn't see) | Server-side post-filter re-checks read permission on every result before responding |
| XSS via `snippet_html` relayed to agent UIs | Sanitizer whitelist (`<em>`, `<strong>`, `<br>`); everything else HTML-escaped |
| Prompt injection via assistant thread content fed into agent consumers | Tool description labels content as untrusted; server does not interpret it; document expected agent-side handling |
| Binary exfiltration via attachment metadata abuse | Tool returns no URLs by default; signed URL is per-call, short-lived, bearer-bound |
| Tag enumeration revealing workspace structure across tenants | Tag queries always scoped to session workspace_id |
| Dashboard admin fields leaking to non-admin | Fields omitted not errored; omission is documented; integration test asserts non-admin caller sees only `workspace_health` |
| Jira snapshot leaking diverged content the caller lacks read on | Re-check read permission on the work item before returning snapshot fields |
| Signed URL replay beyond original caller | Signed URLs encode token_id and require the same bearer to redeem; single-use recommended (post-MVP) |

## Non-Functional Requirements

- `semantic.search` p95 < 800 ms (dominated by Puppet)
- `assistant.threads.get` p95 < 300 ms
- `tags.list` p95 < 100 ms (cacheable per workspace)
- `workspace.dashboard` p95 < 600 ms — server caches blocks for 30 s per workspace
- `attachments.list` does not hit object storage (metadata only from DB)
