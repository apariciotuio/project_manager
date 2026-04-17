# Attack Plan — 2026-04-17

Execution order for the remaining ~85% of the MVP given current state (`pending_audit_2026-04-17.md`). Not a re-plan — a sequence with cuts, tracks, and exit criteria.

## TL;DR

- **Cut 4 epics to post-MVP**: EP-11, EP-16, EP-17, EP-18
- **Run 2 parallel tracks**: frontend catch-up + backend completion
- **First deliverable milestone**: EP-01/02 FE + EP-03 closed → users can capture, converse, and accept suggestions end-to-end
- **Before anything**: fix tracking debt (30 min)

## MVP cut

Moved to post-MVP. These do not block the core "capture → clarify → spec → breakdown → review → Ready" pipeline.

| EP | Reason for cut |
|---|---|
| EP-11 Jira export/import | Nice-to-have integration. No user is blocked without it for v1 |
| EP-16 Attachments (MinIO) | Rich content parity, not core to maturation. Adds ops surface (storage, quotas) |
| EP-17 Edit locking + presence | Collaboration polish. Single-user sessions work without it |
| EP-18 MCP server (read-only) | External integration. UI surface is the MVP, not programmatic access |

Net saving: **4 EPs, ~564 pending checkboxes**.

## Tracks (run in parallel, 2 max)

### Track A — Frontend catch-up

Goal: close the gap between shipped backend and visible product.

| Order | EP | Why now |
|---|---|---|
| A1 | EP-01 FE (0/44) | Unblocks all manual QA. Work items must exist in UI |
| A2 | EP-02 FE (0/38) | Capture + drafts + templates — the entry point |
| A3 | EP-03 FE (0/56) | The chat/wizard with gaps + suggestion preview — this is the differentiator |
| A4 | EP-04 FE (0/50) | Completeness bar + spec-gen trigger on the detail page |
| A5 | EP-05 FE (0/58) | Breakdown tree + dnd-kit |

### Track B — Backend completion

Goal: finish the intelligence layer so Track A has something to render.

| Order | EP | Scope remaining |
|---|---|---|
| B1 | EP-03 BE close | 20 tasks: SSE event stream, WS proxy ITs, suggestion apply → version hand-off, callback hardening |
| B2 | EP-04 BE | 67 tasks: `work_item_sections`, weighted completeness, spec-gen agent callback, `validation_rules` DB-backed, gaps API |
| B3 | EP-05 BE | 95 tasks: `task_nodes` (adjacency + materialized path), dependencies, split/merge, breakdown agent, cycle detection |
| B4 | EP-07 BE | Versions + diff engine + outbox + timeline events — precondition for the diff viewer FE |
| B5 | EP-06 BE | Reviews + validations + Ready gate |
| B6 | EP-08 BE | Notifications + inbox + event bus |
| B7 | EP-13 BE | Puppet sync (enables EP-09 search) |
| B8 | EP-09 BE | Listings + dashboards + search |
| B9 | EP-10 BE | Admin + projects + rules |
| B10 | EP-12 BE | Security + perf hardening (rate limits, CORS, CSRF) |
| B11 | EP-14 BE | Milestones + stories hierarchy types |
| B12 | EP-15 BE | Tags + labels |

Frontend counterparts (EP-06..EP-10, EP-12..EP-15) follow the same order once backend lands.

## Value milestones (what "done" looks like at each checkpoint)

| # | Delivered when | What you can demo |
|---|---|---|
| **V1** | A1+A2 done | Create / edit / transition a work item via UI. Draft + templates |
| **V2** | V1 + B1 + A3 done | Chat with Dundun about a work item, gaps panel populates, accept a suggestion, new version created |
| **V3** | V2 + B2 + A4 done | Completeness bar reacts live; trigger spec-gen; sections populate async |
| **V4** | V3 + B3 + A5 done | Full breakdown of an element into hierarchical tasks with dependencies |
| **V5** | V4 + B4 + EP-07 FE | Version diff viewer with partial accept, timeline events |
| **V6** | V5 + B5..B10 + FE | Reviews, Ready gate, inbox, dashboards, search, admin |
| **MVP** | V6 + B11 + B12 + FE + EP-12 polish | Shippable |

V1-V3 is the minimum for internal QA with users. V4-V5 is the core product story. V6+ is the productization layer.

## Tracking debt — fix before starting (≈30 min)

1. EP-00 `tasks.md` — mark umbrella as COMPLETED (backend + frontend done)
2. EP-01 `tasks.md` — mark backend phase COMPLETED, frontend PENDING
3. EP-02 `tasks.md` — same treatment
4. EP-03 `tasks.md` — reflect Phase 1-3 COMPLETED (backend at 60/80), Phase 4+ pending, frontend PENDING
5. EP-13 — create umbrella `tasks.md` for consistency with other epics

This is non-negotiable. Resuming sessions from another machine (per `feedback_task_tracking.md`) depends on these files being truthful.

## First week (concrete)

Day 1 — 30-min tracking debt fix + re-plan EP-01 FE.

Day 2-3 — EP-01 FE plan executed via `develop-frontend` (Phase 1-2: work-item list + detail page with FSM transitions).

Day 4-5 — EP-01 FE Phase 3+ (editing, ownership, reassignment) + kick off EP-03 BE close (SSE event stream is the next blocker).

End of week 1: work-item CRUD + FSM fully usable in UI. Track B advancing on EP-03 BE.

## Rules for this plan

1. **No epic gets started without its predecessor's exit criteria met.** Backend-first always, never ship FE against a moving BE contract.
2. **Two tracks max.** Context switching across 5 fronts is how we get to 15% in 4 months.
3. **Cut list is final until V3 ships.** No quietly re-adding EP-11/16/17/18 mid-sprint.
4. **Update `tasks-*.md` after every step.** Not batched. Resume-from-another-machine rule.
5. **Review before push**, always. `code-reviewer` + `review-before-push`. No exceptions.

## Risks

- **Dundun contract drift**: EP-03..EP-05 all depend on agents (`wm_gap_agent`, `wm_spec_gen_agent`, `wm_breakdown_agent`). Lock callback schemas early; `FakeDundunClient` must mirror real contract.
- **Frontend velocity unknown**: no shipped EP-01/02 frontend means the FE/BE ratio is unproven. If A1+A2 take longer than 2 weeks, cut more scope (candidates: EP-10 admin UI reduced to minimal, EP-09 dashboards deferred).
- **Puppet dependency on V6**: EP-09 search + EP-07 timeline search both need Puppet (EP-13). If Puppet integration slips, ship V6 with degraded-mode "search unavailable" banner as designed.

## Not in this plan

- Re-planning already-enriched EPs
- Estimates in days/hours (no historical velocity data)
- Team/resourcing assumptions (solo execution assumed)
