---
description: Implement backend task following TDD (RED+GREEN+REFACTOR) and Security by Design using an existing plan
mode: backend-developer
input:
  - task_id
---

# Develop Backend

Implement backend code following TDD and Security by Design, using the plan created by `plan-backend-task`.

## Input

Task ID as argument. Requires `tasks/<TASK-ID>/plan-backend.md` to exist.

## Prerequisites

Verify plan exists. If not, inform user to run `plan-task` → `plan-backend-task` first.

## Process

1. **Read the plan** — `plan-backend.md` is your blueprint. DO NOT re-plan.
2. **Implement per step** — RED (write failing test from WHEN/THEN/AND scenarios) → GREEN (minimum code to pass) → REFACTOR (clean up without breaking tests)
3. **Apply Security by Design** per step — input validation, authorization, sensitive data handling, OWASP Top 10
4. **Mark progress** — after each step, update `tasks/<TASK-ID>/tasks.md`: mark checkbox, add short note
5. **Final verification** — all tests passing, lint clean, type checks pass, security review complete
6. **Commit** — conventional commits with `Refs: <TASK-ID>`, one per logical step

## Rules

- Follow the plan — DO NOT re-plan
- TDD is mandatory — no implementation without failing test first
- Security by Design — consider security at each step
- Small commits after each logical step
- If a step is unclear, ask about THAT step — don't re-plan everything
