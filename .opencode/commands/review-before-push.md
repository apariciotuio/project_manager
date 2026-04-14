---
description: Pre-push quality review gate - self-review for correctness, security,
  code quality, and completeness
---

# Review Before Push

Self-review before pushing. Not just "done" — "done well."

## Process

1. **UNDERSTAND** — Verify you can explain what problem this solves and why this approach was chosen.
2. **VERIFY** — Run tests (full suite, no skipped), lint/types (no errors), build (succeeds).
3. **REVIEW** (as if reviewing someone else's code):
   - Security: no hardcoded secrets, no debug code, input validation, authorization, OWASP Top 10
   - Code quality: readable, clear naming, proper error handling, edge cases, no duplication
   - Consistency: follows existing patterns, matches project conventions
   - Documentation: comments explain "why", public APIs have docstrings
4. **DOCUMENTATION** — Check if changes affect architecture, patterns, conventions, or developer workflows. If so, update the project's living documentation (architecture docs, project instructions, README). Do not defer — update now.
5. **QUESTION** — Surface doubts before pushing: unconsidered edge cases, hacky solutions, wrong assumptions, stale documentation.
6. **IMPROVE** — Reflect: what was learned, what went well, what could improve.

## Rules

- Be honest — if something is unclear or concerning, say so
- Be thorough — don't skip steps
- Be critical — review your own code as you would review others'