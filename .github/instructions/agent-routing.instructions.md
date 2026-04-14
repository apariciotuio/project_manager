---
description: Agent hierarchy, delegation rules, routing logic, and pipeline enforcement for multi-agent workflows
applyTo: "**"
---

# Agent Routing & Delegation

## Agent Tiers

| Tier | Agents | Model |
|------|--------|-------|
| **Thinking** | code-reviewer, sw-architect, product-analyst, test-engineer, poc-developer | Opus |
| **Execution** | backend-developer, frontend-developer, data-engineer, ml-engineer, qa-automation-engineer | Sonnet |
| **Trivial** | quick-fix-developer | Haiku |

Delegation flows **downward only**. Never upward.

## Routing

| Condition | Route to |
|-----------|----------|
| Vague requirement | `enrich-us` → `plan-task` |
| Feature without plan | `plan-task` (refuse implementation) |
| Backend plan exists | `develop-backend` |
| Frontend plan exists | `develop-frontend` |
| Trivial (≤3 files, no API/schema/security) | `develop-quick-fix` |
| Architecture question | `sw-architect` (advise only) |
| Code review | `code-review` (read-only) |
| PoC | `plan-poc` → `develop-poc` |

## Delegation Rules

- **Refuse & redirect** out-of-scope work: no plan → point to `plan-task`, architect can't implement, reviewer can't fix
- **Scope assessment**: trivial → `quick-fix-developer`, feature → check plan exists, `quick-fix-developer` exceeds scope → escalate back
- **Auto-chain**: `plan-task` → `plan-backend-task` / `plan-frontend-task` based on detected layers
- **Code-review** detects DB changes → spawn `db-reviewer`

## Feature Pipeline (non-negotiable)

```
enrich-us → plan-task → plan-backend/frontend-task → develop-backend/frontend (TDD) → code-review → review-before-push
```

Each phase produces artifacts the next requires. Skipping phases is forbidden.

## Progress Tracking

Every agent updates `tasks/<TASK-ID>/tasks.md` after each step: `[ ]` → `[x]` with note. Phase complete → `**Status: COMPLETED** (YYYY-MM-DD)`.

## Plan-Driven Execution

`develop-*` reads the plan, **never re-plans**. Execute step by step: RED → GREEN → REFACTOR.
