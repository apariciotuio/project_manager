# MVP Work Maturation Platform — Task Tracker

## Epic Summary

| Epic | Name | Dependencies | Complexity | Status |
|------|------|-------------|------------|--------|
| EP-00 | Access, Identity & Bootstrap | — | Medium | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-01 | Core Model, States & Ownership | EP-00 | High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-02 | Capture, Drafts & Templates | EP-00, EP-01 | Medium | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-03 | Clarification, Conversation & Assisted Actions | EP-02 | High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-04 | Structured Specification & Quality Engine | EP-01, EP-02, EP-03 | High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-05 | Breakdown, Hierarchy & Dependencies | EP-04 | Medium-High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-06 | Reviews, Validations & Flow to Ready | EP-01, EP-04, EP-05, EP-08 | High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-07 | Comments, Versions, Diff & Traceability | EP-01, EP-04, EP-05, EP-06 | High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-08 | Teams, Assignments, Notifications & Inbox | EP-00, EP-01 | Medium-High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-09 | Listings, Dashboards, Search & Workspace | EP-01, EP-02, EP-06, EP-08 | Medium-High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-10 | Configuration, Projects, Rules & Admin | EP-00, EP-08 | High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-11 | Export & Sync with Jira | EP-01, EP-04, EP-06, EP-10 | Medium-High | [x] Proposal [x] Specs [x] Design [x] Tasks |
| EP-12 | Responsive, Security, Performance & Observability | Transversal | Medium | [x] Proposal [x] Specs [x] Design [x] Tasks |

## Implementation Order (Suggested)

```
EP-00 ──> EP-01 ──> EP-02 ──> EP-03 ──> EP-04 ──> EP-05
                                                      │
EP-00 ──> EP-08 ─────────────────────────────> EP-06 ─┤──> EP-07
                                                      │
EP-00 ──> EP-08 ──> EP-10 ───────────────────────────>├──> EP-11
                                                      │
EP-01 ──> EP-02 ──> EP-06 ──> EP-08 ──────────────────├──> EP-09
                                                      │
                                                      └──> EP-12 (transversal)
```

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
| Implementation | PENDING — address review findings first |

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
| **Total** | **64** | **56** | **8** |
