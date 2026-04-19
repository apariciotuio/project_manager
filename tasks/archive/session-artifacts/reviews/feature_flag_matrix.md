# Feature Flag Matrix

**Source**: Round-2 architect review **A-M8** (no precedence defined across the three flags governing EP-18 and EP-19).

## Flags

| Flag | Owner | Scope | Default (dev) | Default (staging) | Default (prod) | Kill switch? |
|---|---|---|---|---|---|---|
| `MCP_SERVER_ENABLED` | EP-18 backend | Global per deployment. If `false`: the MCP server rejects all `initialize` calls with `-32001`. REST unaffected. | `true` | `true` | `false` (flip on GA) | **Yes** — rejects all tokens instantly |
| `MCP_ENABLED_FOR_WORKSPACE` | EP-18 backend | Per-workspace. Evaluated at token-verify time via `workspaces.feature_flags ?? 'mcp_enabled'`. Fall back to `false` when missing. | `true` for all | Alpha workspaces only | Per-workspace rollout | Per-workspace disable |
| `DESIGN_SYSTEM_V1` | EP-19 frontend | Per-route. Gates the admin-UI + self-service UI for MCP tokens behind the EP-19 catalog. When `false`, old ad-hoc admin pages serve the same endpoints. | `true` | `true` | Off-by-default initially; flipped per route as retrofit lands | Per-route off |

## Precedence (resolution order)

```
MCP request path                    Frontend path
━━━━━━━━━━━━━━━━━                    ━━━━━━━━━━━━━━
1. MCP_SERVER_ENABLED               1. route-level DESIGN_SYSTEM_V1
   ├── false → -32001 (done)
   └── true  → step 2                  ├── false → legacy UI
                                       └── true  → EP-19 catalog UI
2. MCP_ENABLED_FOR_WORKSPACE
   ├── false → -32003 forbidden
   └── true  → authorize + dispatch
```

The frontend flag is **independent** of the MCP flags. A workspace can have MCP enabled on the backend but still render the legacy admin UI (or vice-versa). Matrix examples:

| `MCP_SERVER_ENABLED` | `MCP_ENABLED_FOR_WORKSPACE` | `DESIGN_SYSTEM_V1` | Observed |
|---|---|---|---|
| false | any | any | MCP dead everywhere; admin UI renders regardless |
| true | false | true | EP-19 catalog UI issues/lists tokens via REST; agents can't connect |
| true | true | false | Legacy admin UI issues tokens; agents work via MCP |
| true | true | true | Full EP-18 + EP-19 experience (GA target) |

## Rollout sequence (target)

1. **Phase α** — dev + staging: all three flags `true`. Pilot workspaces only.
2. **Phase β** — prod: `MCP_SERVER_ENABLED=true`, `MCP_ENABLED_FOR_WORKSPACE=true` for 3 pilot workspaces, `DESIGN_SYSTEM_V1=true` on `/admin/mcp-tokens` + `/settings/mcp-tokens` only. 2-week soak.
3. **Phase γ** — GA: per-workspace flag rollout expands. `DESIGN_SYSTEM_V1` flips on per route as each epic's retrofit lands (per `tasks/extensions.md#EP-19` execution order).
4. **Phase δ** — flag removal: when all EP-00..EP-18 retrofits ship, `DESIGN_SYSTEM_V1` becomes the only path and the flag is removed from code.

## Rollback

Each flag independently reversible. `MCP_SERVER_ENABLED=false` is the global kill switch (rejects tokens instantly, within the 5 s cache TTL). Per-workspace disable is the surgical switch. `DESIGN_SYSTEM_V1` rollback is cosmetic only (no data implication).

## Tests

- Configuration-matrix test: every valid combination exercised in CI (12 combinations = 2×2×2 of non-absurd values, excluding `MCP_SERVER_ENABLED=false` + `MCP_ENABLED_FOR_WORKSPACE=true` which is nonsensical).
- Flag-read observability: every tool invocation logs the effective flag values (redacted if sensitive).

## Ownership

- `MCP_SERVER_ENABLED` — platform engineer on-call; flip requires 2 approvals
- `MCP_ENABLED_FOR_WORKSPACE` — workspace admin self-service via admin UI (EP-10 extension tracked in backlog)
- `DESIGN_SYSTEM_V1` — frontend lead + product, per-route decision
