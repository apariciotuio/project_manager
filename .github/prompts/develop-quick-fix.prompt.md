---
description: Execute trivial code changes (<=3 files, no new API, no schema, no security) with no TDD ceremony
mode: quick-fix-developer
input:
  - description
---

# Develop Quick Fix

Execute small, well-defined code changes. No planning, no TDD — just execute and verify.

## Scope Guard

ALL conditions must be true:
- <=3 files affected
- No new public API (endpoints, exported interfaces)
- No schema/migration changes
- No security-sensitive changes (auth, permissions, encryption, secrets)
- Change is fully describable without spec files

If ANY condition fails → STOP and escalate to backend-developer or frontend-developer.

## Input

Inline plan or short description (e.g., "rename getUserName to getUsername in src/utils/")

## Process

1. Parse the plan. If ambiguous or violates scope, refuse and escalate.
2. Execute each step. Show diff.
3. Verify: type check, lint, run existing tests.
4. Report: files changed + verification result.

## Escalation

Return control if:
- Change is bigger than described
- Existing tests break and fix isn't obvious
- Requires a design decision
- Security-sensitive code involved

## Rules

- No planning artifacts
- No TDD — run existing tests only
- No architecture decisions — escalate
- One retry on verification failure, then escalate
- Commit with `fix:` or `chore:` prefix
