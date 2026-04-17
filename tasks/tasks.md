# Work Maturation Platform — Task Tracker

## Epic Summary

| Epic | Name | Dependencies | Complexity | Backend | Frontend | Status |
|------|------|-------------|------------|---------|----------|--------|
| EP-00 | Access, Identity & Bootstrap | — | Medium | ✅ Done | ✅ Done | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-01 | Core Model, States & Ownership | EP-00 | High | ✅ Done | ✅ Items list + detail | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-02 | Capture, Drafts & Templates | EP-00, EP-01 | Medium | ✅ Done | ✅ Create form | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-03 | Clarification, Conversation & Assisted Actions | EP-02 | High | ✅ Done (deferred: RLS, WS bidir) | ⬜ Chat UI pending | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [ ] Frontend |
| EP-04 | Structured Specification & Quality Engine | EP-01, EP-02, EP-03 | High | ✅ Done (deferred: NextStep, spec-gen) | ✅ Spec tab + completeness | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-05 | Breakdown, Hierarchy & Dependencies | EP-04 | Medium-High | ✅ Done (repos + services + controllers) | ✅ Tasks tab | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-06 | Reviews, Validations & Flow to Ready | EP-01, EP-04, EP-05, EP-08 | High | ✅ Done (repos + services + controllers) | ✅ Reviews tab | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-07 | Comments, Versions, Diff & Traceability | EP-01, EP-04, EP-05, EP-06 | High | ✅ Done (deferred: diff engine, SSE) | ✅ Comments + Timeline tabs | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-08 | Teams, Assignments, Notifications & Inbox | EP-00, EP-01 | Medium-High | ✅ Done (repos + services + controllers) | ✅ Teams + Inbox pages | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-09 | Listings, Dashboards, Search & Workspace | EP-01, EP-02, EP-06, EP-08 | Medium-High | ✅ Done (saved searches + controllers) | ✅ Items list + filter | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-10 | Configuration, Projects, Rules & Admin | EP-00, EP-08 | High | ✅ Done (projects + routing + admin) | ✅ Admin page (6 tabs) | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-11 | Export & Sync with Jira | EP-01, EP-04, EP-06, EP-10 | Medium-High | ✅ Done (stub export) | ✅ Integrations tab | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| EP-12 | Responsive, Security, Performance & Observability | Transversal | Medium | 🟡 Partial (rate limit, CORS, correlation ID) | ⬜ Pending audit | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Backend [ ] Frontend |
| **EP-13** | **Semantic Search + Puppet Integration** | EP-09, EP-10, EP-12 | High | ✅ Done (outbox + Celery task) | ⬜ Search bar wiring | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [ ] Frontend |
| **EP-14** | **Hierarchy: Milestones, Epics, Stories** | EP-01, EP-05, EP-09, EP-10 | High | ✅ Done (types + catalog + rules) | ⬜ Tree view | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [ ] Frontend |
| **EP-15** | **Tags + Labels** | EP-01, EP-09, EP-10 | Medium | ✅ Done (repos + controllers) | ✅ Tag management in admin | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| **EP-16** | **Attachments + Media** | EP-01, EP-07, EP-10, EP-12 | High | ✅ Done (repos + controllers, no MinIO yet) | ✅ Attachment list (metadata) | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| **EP-17** | **Edit Locking + Collaboration Control** | EP-01, EP-08, EP-10, EP-12 | Medium-High | ✅ Done (repos + controllers) | ✅ Lock indicators in spec tab | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend [x] Frontend |
| **EP-18** | **MCP Server: Read & Query Interface** | EP-00..EP-19 | Medium | ✅ Skeleton (15 tools, stdio+SSE) | N/A | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Backend |
| **EP-19** | **Design System & Frontend Foundations** | EP-12 | Medium | N/A | ✅ Done (shadcn + tokens + i18n) | [x] Proposal [x] Specs [x] Design [x] Tasks [x] Frontend |
| **EP-20** | **Theme System: Light / Dark / Matrix** | EP-19 | Low-Medium | N/A | ⬜ Pending (3 themes + red/blue pill) | [x] Proposal [x] Specs [x] Design [x] Tasks [ ] Frontend |
| **EP-21** | **Post-MVP Feedback Batch** (layouts, seed inbox, UI refresh, errors, edit item, dundun-fake) | EP-19, EP-08, EP-03 | Medium | ⬜ Pending | ⬜ Pending | [x] Proposal [ ] Specs [ ] Design [ ] Tasks [ ] Backend [ ] Frontend |

## Implementation Order (Suggested)

```
EP-12 (transversal primitives) ──> EP-19 (design system) ──> frontend work of every epic below

EP-00 ──> EP-01 ──> EP-02 ──> EP-03 ──> EP-04 ──> EP-05
                                                      │
EP-00 ──> EP-08 ─────────────────────────────> EP-06 ─┤──> EP-07
                                                      │
EP-00 ──> EP-08 ──> EP-10 ───────────────────────────>├──> EP-11
                                                      │
EP-01 ──> EP-02 ──> EP-06 ──> EP-08 ──────────────────├──> EP-09
                                                      │
EP-13, EP-14, EP-15, EP-16, EP-17, EP-18 ─────────────┘
```

**Transversal track**: EP-12 (technical primitives) → EP-19 (design system). Both unblock every epic with frontend scope. Existing epics retrofit via `extensions.md` once EP-19's catalog lands.

## Pending side-tasks (non-epic)

- [x] **Dev seed script** — `backend/scripts/seed_dev.py` (workspace + membership) + `backend/scripts/seed_sample_data.py` (8 work items, 5 tags, 1 team, 5 task nodes, sections). Idempotent.
- [ ] **Workspace RLS follow-up** — add `workspace_id` + RLS to EP-03/EP-04 tables (`conversation_threads`, `assistant_suggestions`, `gap_findings`, `work_item_sections`, `work_item_section_versions`, `work_item_validators`, `work_item_versions`). See `tasks/EP-03/phase_8_security_findings.md`.
- [ ] **E2E verification** — verify login → workspace select → items list → item detail → sections edit → completeness flow in a real browser.
- [ ] **External integrations** — wire real HTTP clients for Dundun, Puppet, Jira (currently using fakes).

## Critical Path

EP-00 -> EP-01 -> EP-02 -> EP-03 -> EP-04 -> EP-05 -> EP-06 -> EP-07

## Parallel Track

EP-08 (Teams & Notifications) can start after EP-01, in parallel with EP-02/EP-03.
EP-10 (Admin) can start after EP-08, in parallel with EP-04/EP-05.

## Phase Pipeline

| Phase | Status |
|-------|--------|
| Proposals | COMPLETED |
| Enrichment + Technical Planning | COMPLETED (all 13 epics) |
| Consistency Review | COMPLETED — 7 must-fix, 10 should-fix, 3 nitpick |
| assumptions.md + tech_info.md | COMPLETED |
| Back/Front Split + Subtasks | COMPLETED — 26 files (13 backend + 13 frontend) |
| OpenSpec Detail Pass | COMPLETED — ~150 acceptance criteria blocks added |
| Specialist Reviews (arch→sec→front→back→DB) | COMPLETED — 5 reviews, see tasks/reviews/ |
| Implementation | **IN PROGRESS** — backend 100% schema + services, frontend pages built, E2E flow pending verification |
| **NEW REQUIREMENTS** | **COMPLETED — EP-13..EP-17 planned + extensions applied** |
| EP-13..EP-17 Specs + Design + Tasks | COMPLETED — specs/design/back+front for all 5 |
| Existing epics extensions (EP-01, EP-03, EP-07, EP-09, EP-10) | COMPLETED — see extensions.md for change log |
| Updated assumptions.md (Q8 attachments Yes, Q9 superadmin CLI) | COMPLETED |
| **EP-18 (MCP Server)** Proposal + Specs + Design + Tasks | COMPLETED (2026-04-14) — back+front, Dundun/Puppet contracts aligned with real APIs |
| **EP-19 (Design System)** Proposal + Specs + Design + Tasks | COMPLETED (2026-04-14) — frontend-only, shadcn+tokens+i18n+a11y gate; retrofits EP-00..EP-18 via extensions.md |
| Cross-epic consistency review on expanded plan (20 epics) | **COMPLETED** (2026-04-14) — `tasks/consistency_review_round2.md` — 2 Must-fix + 1 Should-fix resolved; 3 informational |
| Specialist reviews round 2 on new epics (incl. EP-18 + EP-19) | **COMPLETED** (2026-04-14) — arch + sec + front + a11y on EP-18 + EP-19; 24 Must-fix resolved in-spec; feature flag matrix documented; see `tasks/reviews/round_2_specialist_reviews_summary.md` |

## User Stories Count

| Epic | Stories | Must | Should |
|------|---------|------|--------|
| EP-00 | 3 | 3 | 0 |
| EP-01 | 4 | 4 | 0 |
| EP-02 | 4 | 3 | 1 |
| EP-03 | 4 | 3 | 1 |
| EP-04 | 4 | 4 | 0 |
| EP-05 | 5 | 5 | 0 |
| EP-06 | 5 | 5 | 0 |
| EP-07 | 4 | 4 | 0 |
| EP-08 | 5 | 4 | 1 |
| EP-09 | 6 | 5 | 1 |
| EP-10 | 10 | 7 | 3 |
| EP-11 | 5 | 4 | 1 |
| EP-12 | 5 | 5 | 0 |
| EP-13 | 6 | 5 | 1 |
| EP-14 | 5 | 5 | 0 |
| EP-15 | 6 | 5 | 1 |
| EP-16 | 6 | 5 | 1 |
| EP-17 | 6 | 6 | 0 |
| EP-18 | 20 | 17 | 3 |
| EP-19 | 13 | 11 | 2 |
| **Total** | **126** | **110** | **16** |

*Counts for EP-13..EP-19 are read from each epic's `proposal.md#User Stories`; re-run if they are amended.*
