# Pending Audit — 2026-04-17

Consolidated status of every EP based on `tasks-backend.md` / `tasks-frontend.md` checkbox counters. `tasks.md` umbrella counters are ignored where subfiles exist (they are meta artifact checklists, not implementation trackers).

## Legend

- ✅ **DONE** — ≥ 95% checkboxes + COMPLETED status line
- 🟡 **IN FLIGHT** — some work landed, phases remain
- ⬜ **NOT STARTED** — 0 checkboxes done
- — — file absent

## Top-level summary

| Bucket | Count | Epics |
|---|---|---|
| Shipped end-to-end | 3 | M0, EP-00, EP-21 |
| Backend shipped, frontend pending | 2 | EP-01, EP-02 |
| Backend partial, frontend pending | 3 | EP-03, EP-04, EP-05 |
| Nothing built | 13 | EP-06..EP-18 (minus EP-09/EP-13 already listed as not started), EP-13 |
| Cross-cutting shipped | 2 | EP-19 (frontend 49/59), EP-20 (frontend 37/44) |

## Per-epic breakdown

| EP | Title | Backend | Frontend | Global |
|---|---|---|---|---|
| M0 | Scaffolding | 34/34 ✅ | — | ✅ **COMPLETED** 2026-04-15 |
| EP-00 | Auth + Bootstrap + Superadmin | 99/100 ✅ | 28/28 ✅ | ✅ **COMPLETED** 2026-04-15 |
| EP-01 | Core model + FSM | 71/72 ✅ | 0/44 ⬜ | 🟡 backend shipped, frontend pending |
| EP-02 | Capture + Drafts + Templates | 57/58 ✅ | 0/38 ⬜ | 🟡 backend shipped, frontend pending |
| EP-03 | Chat via Dundun proxy | 60/80 🟡 | 0/56 ⬜ | 🟡 backend ~75%, frontend untouched |
| EP-04 | Completeness + Spec gen | 21/88 🟡 | 0/50 ⬜ | 🟡 backend ~24%, frontend untouched |
| EP-05 | Breakdown + Hierarchy + Deps | 5/100 🟡 | 0/58 ⬜ | 🟡 backend ~5%, frontend untouched |
| EP-06 | Reviews + Validations + Ready | 0/81 ⬜ | 0/48 ⬜ | ⬜ |
| EP-07 | Versions + Diff + Timeline + Comments | 0/81 ⬜ | 0/55 ⬜ | ⬜ |
| EP-08 | Teams + Assignments + Notifications + Inbox | 0/93 ⬜ | 0/65 ⬜ | ⬜ |
| EP-09 | Listings + Dashboards + Search | 0/74 ⬜ | 0/108 ⬜ | ⬜ |
| EP-10 | Configuration + Projects + Rules + Admin | 0/145 ⬜ | 0/116 ⬜ | ⬜ |
| EP-11 | Jira export + import | 0/94 ⬜ | 0/49 ⬜ | ⬜ |
| EP-12 | Responsive + Security + Performance | 0/76 ⬜ | 0/81 ⬜ | ⬜ |
| EP-13 | Puppet integration | 0/85 ⬜ | 0/57 ⬜ | ⬜ |
| EP-14 | Hierarchy: Milestones + Stories | 0/124 ⬜ | 0/92 ⬜ | ⬜ |
| EP-15 | Tags + Labels | 0/63 ⬜ | 0/49 ⬜ | ⬜ |
| EP-16 | Attachments (MinIO) | 0/52 ⬜ | 0/28 ⬜ | ⬜ |
| EP-17 | Edit locking + Presence | 0/70 ⬜ | 0/54 ⬜ | ⬜ |
| EP-18 | MCP Server (read-only) | 0/145 ⬜ | 0/68 ⬜ | ⬜ |
| EP-19 | Design System + FE Foundations | — | 49/59 🟡 | 🟡 catalog near-complete |
| EP-20 | Theme system (light/dark/matrix) | — | 37/44 🟡 | 🟡 ~84% |
| EP-21 | Post-MVP feedback batch | — | — | ✅ **COMPLETED** 2026-04-17 |

## Totals

- Backend checkboxes done: **354 / ~1,845** (~19%)
- Frontend checkboxes done: **114 / ~1,273** (~9%)
- **Overall implementation progress: ~15% of the planned MVP**

## Critical pending by area

### Immediate backend gaps (features with plans + partial code)

| EP | Phases left (high level) |
|---|---|
| EP-03 | 20 tasks remain: Celery callback hardening, SSE event stream, WS proxy integration tests, suggestion apply flow (versioning hand-off) |
| EP-04 | 67 tasks remain: `work_item_sections` ORM + migration, weighted completeness service, spec-gen agent callback, `validation_rules` DB-backed, gaps API |
| EP-05 | 95 tasks remain: `task_nodes` tree (adjacency + materialized path), `task_dependencies`, split/merge services, breakdown agent callback, cycle detection |

### Frontend black hole

No UI exists yet for **EP-01, EP-02, EP-03, EP-04, EP-05**. Backend for EP-01 and EP-02 is shipped; users cannot exercise any of it. Top priority for unblocking manual QA:

1. EP-01 frontend (work-item CRUD + FSM transitions) — 44 tasks
2. EP-02 frontend (capture + drafts + templates) — 38 tasks
3. EP-03 frontend (chat + gaps panel + suggestion preview) — 56 tasks — **this is the "wizard with chat" experience**
4. EP-04 frontend (completeness bar + spec-gen trigger + gaps UI) — 50 tasks

### Not started at all (design done, zero implementation)

EP-06, EP-07, EP-08, EP-09, EP-10, EP-11, EP-12, EP-13, EP-14, EP-15, EP-16, EP-17, EP-18 — 13 epics with a combined **~2,034 pending checkboxes**.

## Blocking dependencies (must-order)

```
EP-01 (done) ──► EP-02 (backend done) ──► EP-03 ──► EP-04 ──► EP-05
                                            │
                                            ▼
                                           EP-07 (diff viewer — consumes suggestions)
                                            │
                                            ▼
                                           EP-06 (reviews gate Ready)
                                            │
                                            ▼
                                           EP-08 (notifications fan-out)
                                            │
                                            ▼
                                           EP-13 (Puppet) ──► EP-09 (search+dashboards)
```

Side tracks (can parallel once EP-01/02 UI exists): EP-14 hierarchy types, EP-15 tags, EP-16 attachments, EP-17 locking/presence, EP-10 admin, EP-11 Jira, EP-12 security/perf hardening, EP-18 MCP.

## Known tracking debt

- `tasks.md` counters at the umbrella level (EP-00, EP-01, EP-02) show 0/84, 0/74, 10/57 despite the epic being shipped. Rule: trust `tasks-backend.md` / `tasks-frontend.md`, not the umbrella.
- EP-03 `tasks.md` says `IN PROGRESS` with 0/84 checked while `tasks-backend.md` is at 60/80 — out of sync. Needs a pass to mirror phase completion upward.
- EP-13 has no `tasks.md` (only backend + frontend) — add an umbrella if consistent tracking matters.

## Recommendation

Do not open more backend fronts until EP-01/EP-02 frontend exist. Without a UI, EP-01/EP-02 code is dead weight for manual validation and drives zero product signal. Order:

1. **EP-01 frontend** (unblocks all QA)
2. **EP-02 frontend** (unblocks capture/template iteration)
3. Finish **EP-03 backend** (20 tasks) + start **EP-03 frontend** — this delivers the guided chat/wizard the product hinges on
4. Then pick between EP-04/EP-05 backend completion vs. EP-07 diff viewer, depending on whether "suggestions that produce versions" is the next perceived value jump

Everything else waits.
