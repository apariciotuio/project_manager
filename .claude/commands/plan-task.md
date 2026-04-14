---
description: Analyze task, create specs with WHEN/THEN/AND scenarios, design decisions,
  propose division if large, auto-chain to plan-backend-task/plan-frontend-task
---

# Plan Task

Analyze an existing task proposal and create detailed specs, design decisions, and implementation tasks.

## Input

Task ID as argument. Expects `tasks/<TASK-ID>/proposal.md` to exist.

## Process

1. **Verify** `tasks/<TASK-ID>/proposal.md` exists. If not, inform user to run `enrich-us` first.
2. **Read proposal** — understand business need, changes, acceptance criteria, complexity.
3. **Create specs** — `tasks/<TASK-ID>/specs/<capability>/spec.md` using WHEN/THEN/AND format for testable scenarios. Include security considerations (Threat → Mitigation) per spec.
4. **Create design** — `tasks/<TASK-ID>/design.md` with context, goals/non-goals, key technical decisions with reasoning and alternatives, security approach, testing strategy.
5. **Propose division** if task involves multiple layers or >3 components. Present division to user and WAIT for approval before creating tasks.md.
6. **Create tasks** — `tasks/<TASK-ID>/tasks.md` with implementation steps. Every step starts with failing tests (TDD). Include security review tasks.
7. **Auto-chain** — analyze which layers are involved and execute `plan-backend-task` and/or `plan-frontend-task` automatically. If ambiguous, ask user first.
8. **Show status** — `tree tasks/<TASK-ID>/` listing all created artifacts.

## Related Standards

- task-management-standards — Task artifacts, division criteria
- testing-standards — TDD requirements
- security-standards — Security considerations for design

## Rules

- Always read proposal.md first
- Wait for user approval before creating tasks.md if dividing
- Include TDD tasks and security tasks
- Use WHEN/THEN/AND format in specs
- Create real files, don't describe
- Always generate implementation plans — auto-chain plan-backend-task and/or plan-frontend-task
- Do NOT generate test code — WHEN/THEN/AND scenarios are the contract