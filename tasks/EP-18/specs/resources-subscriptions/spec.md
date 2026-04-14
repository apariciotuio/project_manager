# EP-18 · Capability 5 — Resources & Live Subscriptions

> **Addendum (Round-2 reviews, 2026-04-14)**:
> - **[A-M3]** Per-(session, uri) authz cache with **5 s TTL**. Bridge checks cache before re-authorizing on emit. Invalidation triggers: `capability.changed`, `workspace_member.status_changed`, `workitem.visibility_changed`, `workitem.ownership_changed` — bridge subscribes to these events too and purges affected cache entries. Eliminates the N-authz-calls-per-event scaling issue at ≥ 1000 subs/pod.
> - **[S-M5]** SSE sessions **periodically re-verify the bearer token** every 60 s using the cached-verify path (capability 1). On failed re-verify: emit `notifications/resources/unsubscribed` with `reason: "token_revoked"` for each subscription, then close the session. Revocation SLO for long-lived subs: `≤ 60 s + 5 s cache TTL`.

## Scope

Expose long-lived aggregates as MCP resources (`resources/list`, `resources/read`, `resources/subscribe`, `resources/unsubscribe`). Wire subscriptions into the existing EP-12 SSE bus so agents receive `notifications/resources/updated` events within 2 s of platform changes.

## In Scope

- Resources: `workitem://<id>`, `epic://<id>/tree`, `workspace://<id>/dashboard`, `user://me/inbox`
- Subscription lifecycle (subscribe, heartbeat, unsubscribe, auto-cleanup on disconnect)
- Bridge from EP-12 SSE bus events (`work_item.updated`, `inbox.changed`, …) to MCP notifications
- Per-session subscription cap
- Re-authorization on every update (authz can change mid-session)

## Out of Scope

- Push of arbitrary events beyond the four resources
- Writable resources
- Multi-hop tree subscriptions (watching a whole epic subtree — high fanout; revisit post-MVP)

## Scenarios

### `resources/list`

- WHEN called THEN returns `[{ uri_template: "workitem://{id}", description, mimeType: "application/json", subscribable: true }, { uri_template: "epic://{id}/tree", ... subscribable: true }, { uri_template: "workspace://{id}/dashboard", subscribable: false }, { uri_template: "user://me/inbox", subscribable: true }]`

### `resources/read`

- WHEN called with `workitem://<id>` AND caller can read THEN returns the same payload shape as `workitem.get` wrapped in `{ contents: [{ uri, mimeType: "application/json", text: JSON.stringify(...) }] }`
- WHEN called with `epic://<id>/tree` THEN returns the epic + full descendant tree up to depth 4; beyond depth 4, nodes appear as `{ id, type, title, has_more_descendants: true }` and a follow-up `workitem.children` call is required
- WHEN called with `workspace://<id>/dashboard` AND id matches session workspace THEN returns the same payload as `workspace.dashboard`
- WHEN `id` in URI refers to a different workspace THEN `-32003`
- WHEN `user://me/inbox` is read THEN returns the same shape as `inbox.list`

### `resources/subscribe`

- WHEN a client subscribes to `workitem://<id>` AND any event changes the item (new version, state, lock, review outcome, new comment, tag change) THEN the server emits `notifications/resources/updated` with `{ uri }` within 2 s
- WHEN the client then calls `resources/read` on the URI THEN the latest payload is returned
- WHEN a client subscribes to `user://me/inbox` AND any event changes inbox composition (new review request, review resolved, decision answered) THEN notification emitted within 2 s
- WHEN a client subscribes to a URI they cannot read THEN subscribe returns `-32003` immediately; no event stream is created
- AND the server caps subscriptions at **50 per session**; extras return `-32005 rate_limited` with `data.reason: "SUBSCRIPTION_CAP"`
- AND SSE keepalive ping every 25 s; session idle > 30 min → close
- AND on `resources/unsubscribe` THEN the bridge removes the listener; on client disconnect, all subscriptions are cleaned up within 10 s

### Authz Re-check on Updates

- WHEN an update is emitted for a subscribed URI BUT the caller's permission to read it has been revoked since subscribe THEN the server sends `notifications/resources/updated` followed immediately by `notifications/resources/unsubscribed` with `reason: "forbidden"` — the client MUST treat this as final
- WHEN the underlying resource is deleted THEN the server sends `notifications/resources/updated`; a subsequent `resources/read` returns `-32002 not_found` (only if caller would have read it)

### Bridge to EP-12 SSE Bus

- AND the MCP process subscribes to the EP-12 Redis pub/sub channels as a **consumer**, not a peer publisher
- AND the bridge debounces bursts: if 10 updates on the same URI arrive within 500 ms, only the latest emits one notification (prevents notification storms during multi-field saves)
- AND the bridge tracks lag: `mcp_sse_bridge_lag_ms` metric reports time between bus event and MCP notification; alert if p95 > 2 s

### Epic Tree Subscription

- WHEN a client subscribes to `epic://<id>/tree` AND any descendant within the subscribed depth changes THEN a single `notifications/resources/updated` is emitted for the epic URI (coarse-grained — clients re-read to get changes)
- WHEN fanout would exceed 100 changes/minute for a tree THEN the bridge throttles to 1 notification per 10 s and sets `data.throttled: true` on the re-read payload (meta field)

## Security (Threat → Mitigation)

| Threat | Mitigation |
|---|---|
| Subscribe to a resource then lose permission; continue receiving updates | Every update re-authorizes before emitting; revocation ends the subscription with explicit `unsubscribed` notification |
| Amplification via many subscriptions to the same noisy resource | Per-session cap (50); per-URI debounce (500 ms); per-tree throttle (1/10s) |
| Channel cross-contamination (workspace A receives workspace B updates) | Bridge filters events by `workspace_id` before dispatching; integration test with two workspaces in parallel |
| Leaked internal bus topics via URI construction | URI templates are fixed; server rejects URIs not matching registered templates with `-32602` |
| Idle session resource exhaustion | 30-min idle timeout; per-pod session cap from capability 2 |
| Debounced updates hiding security-relevant changes (e.g., force-unlock) | Security-relevant events (lock force-released, ownership change, visibility change) bypass debounce |

## Non-Functional Requirements

- Bridge lag p95 < 2 s
- `resources/subscribe` ACK p95 < 100 ms
- Supports ≥ 1000 active subscriptions per pod
- Memory per subscription < 4 KB
