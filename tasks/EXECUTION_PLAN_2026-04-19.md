# Execution Plan — Closeout of 14 Active Epics

> **Author**: Keira · **Date**: 2026-04-19
> **Status**: Fase 0 confirmed by user. Plan ready for remote-session execution.
> **Baseline**: Backend 1964/1964 ✅ · Frontend 1672/1672 ✅

## Context

Audit on 2026-04-19 found that the previous "26/26 archived" status was inaccurate:
- 18 EPs had explicit `DEFERRED` markers or unchecked work
- Those were **unarchived** and moved back to `tasks/EP-XX/`
- Fase 0 decision re-archived **4 of them** as MVP-complete with v2 carveouts (see each folder's `v2-carveout.md`): EP-13, EP-16, EP-18, EP-22
- **14 EPs remain active** for closeout

This plan sequences those 14 by dependency + urgency.

## Ground rules (non-negotiable)

1. **Pipeline per EP**: `plan-task` (refresh if stale) → `develop-backend` / `develop-frontend` (TDD: RED → GREEN → REFACTOR) → `code-reviewer` → `review-before-push`
2. **Progress tracking**: update `tasks/EP-XX/tasks-*.md` after every step. Mark `[ ]` → `[x]` with a specific note. On phase completion add `**Status: COMPLETED** (YYYY-MM-DD)`.
3. **Archive criterion**: zero `[ ]` + zero `DEFERRED` markers → move to `tasks/archive/YYYY-MM-DD-EP-XX/`. Any remaining deferral requires a `v2-carveout.md` + user sign-off.
4. **Commits**: Conventional Commits with `Refs: EP-XX`. One logical step per commit.
5. **No git push without explicit user confirmation.**

---

## Fase 1 — Foundations (serial, unblocks everything)

### Step 1 — EP-12: Responsive, Security, Performance & Observability (no CI)
- **Scope**: close out non-CI items — correlation-id polish, CSP review, secrets-scrub verification, observability gaps. Exclude: axe-core CI gate, Lighthouse, image-virt (tracked separately as v2 CI epic).
- **Dependencies**: none
- **Effort**: ~4h
- **Artifacts to refresh before starting**:
  - `tasks/EP-12/tasks-backend.md` and `tasks-frontend.md` — audit 163 unchecked items; flag which are stale-tick vs real work
- **Exit**: zero DEFERRED markers in EP-12 tasks-*.md (excluding CI carveout).

### Step 2 — EP-19: Design System & Frontend Foundations
- **Scope**: close 10 DEFERRED markers. Likely polish items on tokens, shared components, a11y.
- **Dependencies**: EP-12 closed (shares design primitives)
- **Effort**: ~6h
- **Artifacts**: `tasks/EP-19/tasks-frontend.md` — audit deferrals
- **Exit**: zero DEFERRED + all `[ ]` resolved or explicitly carved out.

### Step 3 — EP-20: Theme System (Light / Dark / Matrix)
- **Scope**: close 10 DEFERRED markers.
- **Dependencies**: EP-19
- **Effort**: ~3h
- **Exit**: theme primitives fully reactive + no deferred items.

---

## Fase 2 — Critical Path (serial, dependency-forced)

### Step 4 — EP-03: Clarification, Conversation & Assisted Actions
- **Scope**: 40 DEFERRED markers — the heaviest unknown; full audit needed before real estimate.
- **Dependencies**: EP-02 (done)
- **Effort**: ~8-12h (floor, may double after audit)
- **First action**: audit `tasks/EP-03/tasks-backend.md` + `tasks-frontend.md` + `phase_8_security_findings.md`. Triage each DEFERRED into (a) real pending work, (b) stale tick, (c) v2 carveout candidate. Report back before implementation.

### Step 5 — EP-04: Structured Specification & Quality Engine
- **Scope**: `NextStep` service + `spec-gen` (the two tracker-acknowledged deferrals)
- **Dependencies**: EP-03 closed
- **Effort**: ~6-8h
- **Artifacts**: review `tasks/EP-04/design.md` for NextStep + spec-gen specs

### Step 6 — EP-05: Breakdown, Hierarchy & Dependencies
- **Scope**: two scope-excluded endpoints (`TaskService.update_section_links()`, `GET /work-items/:id/sections/:sid/tasks`) + audit the 232 unchecked items (likely stale-tick heavy).
- **Dependencies**: EP-04
- **Effort**: ~4h first pass (audit) + estimate real remainder after

### Step 7 — EP-06: Reviews, Validations & Flow to Ready
- **Scope**: Groups 6.3–6.8, 7, 8 (deferred pending EP-08 SSE — now shipped).
- **Dependencies**: EP-05 closed, EP-08 SSE stream (done)
- **Effort**: ~8h

### Step 8 — EP-07: Comments, Versions, Diff & Traceability
- **Scope**: real diff engine (not fake) + SSE push for comments/timeline (tracker-acknowledged deferrals). 22 DEFERRED markers.
- **Dependencies**: EP-06
- **Effort**: ~10h
- **Decision pending**: diff algorithm — custom LCS vs library (e.g., `diff-match-patch`). Recommend library-backed (lower risk, battle-tested).

---

## Fase 3 — Horizontals (2-3 in parallel acceptable)

### Step 9 — EP-08: Teams, Assignments, Notifications & Inbox
- **Scope**: "Still missing / deferred" section of tasks-backend.md. Inbox Group C, TeamValidator refactor, `owner_id` EP-06 follow-up.
- **Dependencies**: EP-06 closed (owner_id depends on reviews flow)
- **Effort**: ~6h

### Step 10 — EP-09: Listings, Dashboards, Search & Workspace
- **Scope**: `GET /work-items/{id}/summary`, N+1 query audit (tests that count SQL calls), naming drift `saved-searches` vs `saved-filters`.
- **Dependencies**: none (horizontal)
- **Effort**: ~5h

### Step 11 — EP-10: Configuration, Projects, Rules & Admin
- **Scope**: CLI superadmin command, `context_sources` table + migration, `AlertService` extraction from the admin controller, EXPLAIN ANALYZE audit on admin queries. 29 DEFERRED markers.
- **Dependencies**: none (horizontal)
- **Effort**: ~8h
- **First action**: audit — granular TDD checklist was never synced. Reconstruct real state of 316 unchecked items before estimating.

### Step 12 — EP-14: Hierarchy — Milestones, Epics, Stories
- **Scope**: BE position PATCH endpoint (`PATCH /work-items/{id}/position`) + FE DnD reparenting wire.
- **Dependencies**: EP-09 (listing consumer)
- **Effort**: ~4h

### Step 13 — EP-17: Edit Locking & Collaboration Control
- **Scope**:
  - BE: finish migration 0119 (lock_unlock_requests) + unlock-request controller tests
  - FE: G8 detail-integration + G10 full draft capture + G11 axe-core audit
- **Dependencies**: EP-08 SSE (done)
- **Effort**: ~8h

---

## Fase 4 — Closeout

### Step 14 — EP-23: Post-MVP Feedback Batch 2
- **Scope**: F-7 page-integration (shell component already shipped) + axe-core CI + keyboard a11y audit.
- **Dependencies**: EP-17 G11 a11y closed
- **Effort**: ~5h
- **Note**: axe-core CI may move to v2 CI epic; confirm before closing.

---

## Totals & Risks

| Metric | Value |
|---|---|
| **Active EPs** | 14 |
| **Effort floor** | ~90 h |
| **Effort ceiling** | ~120 h (if EP-03 doubles post-audit) |
| **Serial phases** | Fase 1 (3 EPs) + Fase 2 (5 EPs) |
| **Parallel window** | Fase 3 (5 EPs, up to 3 concurrent) |
| **Final phase** | Fase 4 (1 EP) |

### Top risks

1. **EP-03 audit floor floats** — 40 markers unread; first action is triage, not implementation
2. **EP-10 state drift** — granular TDD checklist was never synced; real progress unknown
3. **EP-07 diff engine library choice** — affects ~4h of the estimate; recommend picking library before starting
4. **EP-05 stale-tick ratio** — 232 unchecked may mostly be ticked work that never got its box updated

## Pre-execution checklist (remote session kickoff)

Before touching code in any EP, run:

```bash
# 1. Sync to latest
git status                                    # must be clean
git log --oneline -1                          # last commit should be 833f148 (v2 carveouts)

# 2. Baseline tests
cd backend && uv run pytest tests/unit --tb=no -q          # 1964/1964
cd ../frontend && npx vitest run --reporter=basic          # 1672/1672

# 3. Open the EP folder
cat tasks/EP-XX/tasks-backend.md | head -60                # current state
cat tasks/EP-XX/tasks-frontend.md | head -60               # current state
```

## How to resume this plan

Each step corresponds to a real epic. To resume:
1. Pick the next unstarted step (lowest Fase, then lowest step number)
2. Read `tasks/EP-XX/tasks-*.md` for current state
3. If plan is stale (>7 days), run `plan-task EP-XX` first to refresh
4. Execute via `develop-backend` / `develop-frontend` — TDD mandatory
5. After closeout, move folder to `tasks/archive/YYYY-MM-DD-EP-XX/` and update `tasks/tasks.md`

## Archive policy reminder

**Do not archive** an EP unless:
- Zero unchecked `[ ]` items in any `tasks-*.md`
- Zero `DEFERRED` markers (or each has an accompanying `v2-carveout.md`)
- User has given explicit sign-off on any v2 carveout

This is the rule that was violated in the previous session and caused this plan to exist.
