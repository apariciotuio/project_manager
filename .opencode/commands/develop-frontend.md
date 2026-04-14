---
description: Implement frontend task following TDD (RED+GREEN+REFACTOR) using an existing
  plan
---

# Develop Frontend

Implement frontend code following TDD, using the plan from `plan-frontend-task`.

## Input

Task ID as argument. Requires `tasks/<TASK-ID>/plan-frontend.md`.

## Process

1. Read the plan — DO NOT re-plan
2. Implement per step: RED → GREEN → REFACTOR
3. Mark progress in `tasks/<TASK-ID>/tasks.md` after each step
4. Final verification — tests, lint, type checks, build
5. Conventional commits with `Refs: <TASK-ID>`

## Rules

- Follow the plan, don't re-plan
- TDD mandatory
- Small commits per logical step