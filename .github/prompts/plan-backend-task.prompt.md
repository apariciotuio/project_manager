---
description: Create detailed backend implementation plan with DDD layered architecture - domain entities, services, repositories, controllers
input:
  - task_id
---

# Plan Backend Task

Create a detailed backend implementation plan following DDD layered architecture.

## Input

Task ID as argument. Expects `tasks/<TASK-ID>/` with specs and design.

## Process

1. Read existing specs and design from `tasks/<TASK-ID>/`
2. Create `tasks/<TASK-ID>/plan-backend.md` with step-by-step implementation plan
3. Each step must reference specific WHEN/THEN/AND scenarios from specs
4. Plan layers: domain entities → application services → repositories → controllers
5. Include security considerations per layer
6. Include test approach per step (which scenario, which boundary)

## Output

Saves plan to `tasks/<TASK-ID>/plan-backend.md`. This is the blueprint for `develop-backend`.

## Related Standards

- backend-standards — API patterns, DDD, clean architecture
- testing-standards — TDD requirements
- security-standards — Security by Design
