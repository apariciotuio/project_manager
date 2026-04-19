# EP-18 · Capability 3 — Read Tools: Work Items & Content

## Scope

Core read surface over work items and their content: detail, search, hierarchy, comments, versions, diff, reviews, validations, timeline. Every tool is a thin wrapper over existing application services.

## In Scope

- Tools: `user.me`, `workitem.get`, `workitem.search`, `workitem.children`, `workitem.hierarchy`, `workitem.listByEpic`
- Tools: `comments.list`, `versions.list`, `versions.diff`, `reviews.list`, `validations.list`, `timeline.list`
- Schema definitions (Pydantic) shared or derived from REST DTOs to prevent drift
- Per-tool integration tests including cross-workspace forbidden check

## Out of Scope

- Write tools (separate epic)
- Assistant/search tools (capability 4)
- Resources / subscriptions (capability 5)

## Scenarios

### `user.me`

- WHEN called THEN returns `{ id, email, display_name, workspace: { id, name }, capabilities: [...], context_labels: [...] }` for the authenticated actor — never for another user

### `workitem.get(id, options?)`

- WHEN called with a readable id THEN returns `{ id, type, title, state, owner, project, parent_path, children_count, spec: { sections, completeness: { score, level, gaps, next_step } }, tags, attachment_count, lock, jira, created_at, updated_at, version }`
- WHEN called with an id outside the caller's workspace OR without read permission THEN returns `-32003 forbidden` (existence never leaked)
- WHEN called with `include_spec_body: false` THEN `spec.sections[].body` is omitted; all other fields remain
- WHEN called with a soft-deleted id the caller would otherwise read THEN returns `-32002 not_found`
- AND payload size MUST be bounded: if `spec.sections[].body` would push response > 256 KB, the tool returns a truncated payload with `truncated: true` and instructs to paginate via `sections.get` (future) — for MVP, truncation just omits heavy sections and lists their ids in `omitted_section_ids`

### `workitem.search(q?, filters, limit, cursor)`

- WHEN called with `{ filters: { states?, types?, owners?, teams?, tags?: { ids, mode: and|or }, archived?, parent_id?, project_id?, project_ids? } }` AND an optional free-text `q` THEN returns `{ items, next_cursor?, total_estimate? }`
- WHEN `limit` is omitted THEN default 20; when > 100 THEN clamp to 100 without error
- WHEN `cursor` is provided AND invalid/tampered THEN returns `-32602 invalid_params` with code `INVALID_CURSOR`
- WHEN `filters.project_ids` contains an id outside the caller's workspace THEN returns `-32003` — do not silently filter
- AND search is pure metadata + keyword; it does NOT call Puppet (that is `semantic.search` in capability 4)

### `workitem.children(parent_id, limit, cursor)`

- WHEN called THEN returns **direct children only** with `has_more_children` per returned item (to hint expandability)
- WHEN `parent_id` refers to a leaf THEN returns `items: []` (not an error)

### `workitem.hierarchy(id)`

- WHEN called THEN returns `{ ancestors: [...], node: {...}, direct_children: [...], roll_up: { completeness, descendant_ready_ratio, total_descendants } }`
- WHEN caller can read the node but not some ancestor (unusual; misconfigured capabilities) THEN the hidden ancestor appears as `{ id, type, title: null, redacted: true }` so the path length is preserved

### `workitem.listByEpic(epic_id, group_by?)`

- WHEN `group_by` omitted THEN flat `items: [...]` — ordered stable: milestones first, then stories, then tasks
- WHEN `group_by: "type"` THEN `groups: { milestone: [...], story: [...], task: [...] }`
- WHEN `epic_id` is not of type `epic` (or alias `initiative`) THEN `-32602 invalid_params` with `EXPECTED_EPIC_TYPE`

### `comments.list(work_item_id, options)`

- WHEN called THEN returns comments including anchored ones with `{ id, author, body, anchor: { section_id, range, orphan } | null, parent_id?, thread_children_count, reactions, mentions, edited_at?, created_at }`
- WHEN `anchored_only: true` THEN only comments with `anchor != null` are returned
- WHEN the comment was written on a since-deleted section and could not be re-anchored THEN `anchor.orphan: true` (comment still listed, never filtered silently)

### `versions.list(work_item_id, cursor)`

- WHEN called THEN returns versions newest-first: `{ id, number, author_kind: human|assistant|system, author_id?, tag?, created_at, change_summary }`
- WHEN caller cannot read the work item THEN `-32003`

### `versions.diff(work_item_id, from_version, to_version)`

- WHEN both versions belong to the item AND caller can read it THEN returns section-level diff: `{ sections: [{ section_id, change: added|removed|modified, old?, new? }] }`
- WHEN `from_version == to_version` THEN returns `{ sections: [] }` — not an error
- WHEN one version id belongs to a different work item THEN `-32602 invalid_params` with `VERSION_MISMATCH`
- AND old/new section bodies are capped at 64 KB each; on overflow the field contains `{ truncated: true, size_bytes }` with no body

### `reviews.list(work_item_id)`

- WHEN called THEN returns every review request with `{ id, version_id, target_kind: user|team, target_id, target_display_name, state, responder_id?, responded_at?, comments_count }`

### `validations.list(work_item_id)`

- WHEN called THEN returns the checklist: `{ rule_id, label, required, satisfied_by_review_id?, overridden, override_reason?, override_by?, override_at? }`
- AND override information is always visible to readers of the work item (functional spec §3.5: "visible en el histórico")

### `timeline.list(work_item_id, event_types?, cursor)`

- WHEN called THEN merges events from versions, state transitions, reviews, validations, comments, exports, locks with uniform `{ kind, actor_kind: human|assistant|system, actor_id?, payload, happened_at }`
- WHEN `event_types` filter is given THEN only matching kinds are returned
- WHEN a payload references another entity the caller cannot read (e.g., a comment in a hidden section) THEN that event is returned with `payload.redacted: true` — the event itself remains chronologically to preserve the timeline shape

## Security (Threat → Mitigation)

| Threat | Mitigation |
|---|---|
| Cross-workspace data leak via crafted id | Every tool ignores any caller-supplied workspace id; service takes `workspace_id` from session |
| Enumeration via `-32002` vs `-32003` error differences | Return `-32003` whenever caller lacks read; reserve `-32002` only for soft-deleted items the caller would otherwise read |
| Payload DoS (pulling a 50 MB spec) | Hard cap on `workitem.get` at 256 KB; diff bodies capped at 64 KB; truncated payloads flagged |
| Cursor tampering | Cursors are HMAC-signed; invalid signature → `INVALID_CURSOR` |
| Search filter injection (e.g., raw SQL via `q`) | `q` passed as parameter to the full-text indexer (existing Postgres tsvector), never concatenated |
| Timeline event actor leak (assistant acting on behalf of user exposes internal user id) | Respect existing actor visibility rules from §3.6 (actor_kind distinguished); `actor_id` only for human events the caller can see; assistant/system events carry no actor_id |
| Over-fetching via unbounded `listByEpic` | Same pagination pattern: `limit` ≤ 100, cursor-based; no flat dump of 10k items |

## Non-Functional Requirements

- `workitem.get` p95 < 150 ms (cached spec) / 300 ms (cold)
- `workitem.search` p95 < 400 ms
- `versions.diff` p95 < 500 ms even for large specs (heavy-section truncation)
- `timeline.list` p95 < 300 ms
- All tools respect per-token rate limit from capability 2
