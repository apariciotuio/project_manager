# EP-18 — MCP Server: Read & Query Interface · Task Tracker

**Status (archived 2026-04-18 as MCP v1 PoC)**: ✅ SHIPPED — 9/15 read-only tools end-to-end (~165 tests); auth wiring + MCP SDK + InMemoryCacheAdapter all in place.

### v1 PoC shipped
- **9 tools functional**: `search_work_items`, `read_work_item`, `list_projects`, `list_work_items`, `list_sections`, `create_work_item_draft`, `get_work_item_completeness`, `list_comments`, `list_reviews`.
- **Auth**: `MCP_TOKEN` JWT parsed once at startup, `workspace_id` claim extracted via `_decode_token()`, bound to process lifetime (see `server.py` lines 87–94). `test_mcp_auth_context.py` — 7 tests green.
- **Infrastructure**: `mcp>=1.26.0` declared in `pyproject.toml` (line 25); `InMemoryCacheAdapter` wired to `CompletenessService` (replaced `_NoOpCache`).
- **Workspace isolation**: structural (token binds `workspace_id` once; no per-request override possible → cross-workspace rejection tested).

> **⚠️ v1 scope cut per `proposal.md` §Non-Goals (lines 18, 34)**: "This epic is **read-only first**. Write/mutation operations are explicitly out of scope — a separate follow-up epic." The 6 stubbed tools + write capability + admin UI are explicitly deferred.

### v2 scope (new follow-up epic — NOT EP-18 v1)
- **6 remaining tools**: `get_specification`, `get_gaps`, `get_task_tree`, plus duplicate/alias tools (`get_completeness`, `get_reviews`, `get_comments`) — Capability 4 per `tasks-backend.md` line 294.
- **Auth admin endpoints**: token CRUD (rotate, revoke, list), per-workspace self-service.
- **Frontend token panel**: UI for workspace admins to manage MCP tokens (items 1–2 of `tasks-frontend.md`).
- **Rate limiting**: wire `PgRateLimiter` (shipped in EP-12) into MCP middleware.
- **Write tools** (out of v2 scope too — separate v3 if ever): mutations for create/update/delete operations.

---

## Status (pre-archive, historical)

| Phase | Status |
|---|---|
| Proposal | **COMPLETED** (2026-04-14) |
| Specs (5 capabilities) | **COMPLETED** (2026-04-14) |
| Design | **COMPLETED** (2026-04-14) |
| Division approved | **COMPLETED** (2026-04-14) |
| Backend plan (`tasks-backend.md`) | **COMPLETED** (2026-04-14) |
| Frontend plan (`tasks-frontend.md`) | **COMPLETED** (2026-04-14) |
| `plan-backend-task` detail pass | PENDING |
| `plan-frontend-task` detail pass | PENDING |
| Specialist reviews (arch, sec, back, front, DB) | PENDING |
| Implementation | **v1 PoC COMPLETE** (2026-04-18) — 9/15 tools shipped end-to-end: `search_work_items`, `read_work_item`, `list_projects`, `list_work_items`, `list_sections`, `create_work_item_draft`, `get_work_item_completeness`, `list_comments`, `list_reviews` (~165 tests total). Auth wired (JWT at startup). SDK declared. Cache replaced. |

## Capabilities

| # | Capability | Track | Spec |
|---|---|---|---|
| 1 | Auth & Token Lifecycle | Backend + Frontend | [specs/auth-and-tokens/spec.md](specs/auth-and-tokens/spec.md) |
| 2 | MCP Server Bootstrap | Backend | [specs/server-bootstrap/spec.md](specs/server-bootstrap/spec.md) |
| 3 | Read Tools: Work Items & Content | Backend | [specs/read-tools-workitem-content/spec.md](specs/read-tools-workitem-content/spec.md) |
| 4 | Read Tools: Assistant, Search, Extras | Backend | [specs/read-tools-assistant-search-extras/spec.md](specs/read-tools-assistant-search-extras/spec.md) |
| 5 | Resources & Live Subscriptions | Backend | [specs/resources-subscriptions/spec.md](specs/resources-subscriptions/spec.md) |

## Critical Path

```
cap 1 BE ──┬─> cap 1 FE ──────────────────────────────────────┐
           │                                                   │
           └─> cap 2 BE ──┬─> cap 3 BE ──┐                     │
                          │              ├─> cap 5 BE ──> Review → Ready
                          └─> cap 4 BE ──┘                     │
                                         └─> cap 2 FE (audit) ─┘
```

## Dependencies on Other Epics

| Dep | Usage |
|---|---|
| EP-00 | `mcp_tokens` extends identity model; `mcp:issue` capability |
| EP-01 | Work-item read services |
| EP-03 | Dundun thread reads |
| EP-04 / EP-05 | Spec sections, completeness, hierarchy |
| EP-06 | Reviews + validations + override |
| EP-07 | Comments, versions, diff, timeline |
| EP-08 | Inbox + SSE bus consumer |
| EP-09 | Dashboard aggregator, keyword search |
| EP-10 | Admin surface for token UI |
| EP-11 | Jira snapshot reads |
| EP-12 | Rate limiter, audit queue, SSE bus |
| EP-13 | Puppet client |

## Non-Goals (reminder)

- No write/mutation tools — follow-up epic
- No cross-workspace tokens
- No GraphQL/gRPC
- No binary attachment streaming via MCP
- No superadmin cross-workspace tools

## Artifacts

- `proposal.md`
- `design.md`
- `specs/<capability>/spec.md` × 5
- `tasks-backend.md`
- `tasks-frontend.md`

## Open Questions (from proposal)

1. Granular scopes split — deferred to follow-up
2. Admin delegation (issue on behalf of others) — **self-only MVP**
3. SSE keepalive custom — **SDK default** for MVP
4. Error code `-32002` vs `-32003` — **`-32003` default; `-32002` only for soft-deleted within workspace**
5. Rate limit granularity — **per-token + per-IP**
6. `/metrics` exposure — **cluster-internal only**
