# EP-18 — MCP Server: Read & Query Interface · Task Tracker

## Status

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
| Implementation | **IN PROGRESS** (2026-04-18) — 9/15 tools shipped end-to-end: `search_work_items`, `read_work_item`, `list_projects`, `list_work_items`, `list_sections`, `create_work_item_draft`, `get_work_item_completeness`, `list_comments`, `list_reviews` (~140 tests total). **Skeleton rot**: `workspace_id=uuid4()` placeholder (no auth wiring — cap 1 BE), MCP SDK not in `pyproject.toml`, `_NoOpCache` stand-in, some existing tools still stubbed. |

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
