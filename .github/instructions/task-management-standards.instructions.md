---
description: Task artifacts structure, subtask division criteria, and progress tracking
applyTo: "tasks/**/*.md,**/proposal.md,**/tasks.md,**/design.md,**/docs/**/*.md"
---

# Task Management Standards

## Task Artifacts

| Artifact | Purpose |
|----------|---------|
| `tasks/<ID>/proposal.md` | **Why** — business need, objectives, acceptance criteria |
| `tasks/<ID>/specs/<cap>/spec.md` | **What** — requirements with WHEN/THEN/AND scenarios |
| `tasks/<ID>/design.md` | **How** — technical decisions, tradeoffs, alternatives |
| `tasks/<ID>/tasks.md` | **Steps** — implementation checklist with progress tracking |

Completed tasks → `tasks/archive/YYYY-MM-DD-<TASK-ID>/`

## Lifecycle

1. `enrich-us <source>:<id>` → `proposal.md`
2. Assess complexity, divide if needed
3. `plan-task <ID>` → specs, design, tasks
4. Implement (TDD), update `tasks.md` after every step
5. Archive

## When to Divide

Frontend + Backend → always. >3 components → by component. Task B needs Task A → divide to unblock.

## Progress Tracking (MANDATORY)

After each step: `[ ]` → `[x]` with specific note. Phase complete → `**Status: COMPLETED** (YYYY-MM-DD)`. Update immediately, not batched. Be specific — "3 tests for GET/POST/PATCH /api/users/profile" not "added tests".
