---
description: Enrich a task from Jira/Notion with technical details, acceptance criteria,
  and complexity assessment
---

# Enrich User Story

Enrich a task/user story with technical details, acceptance criteria, and complexity assessment.

## Process

1. Read the raw task description
2. Clarify ambiguous requirements
3. Add acceptance criteria (WHEN/THEN/AND format)
4. Assess complexity and dependencies
5. Create `tasks/<TASK-ID>/proposal.md` with enriched details

## Output

Creates `tasks/<TASK-ID>/proposal.md` — the input for `plan-task`.