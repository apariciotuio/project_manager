# Backend Implementation Playbook

Use this playbook for medium/large backend changes. Keep instruction files short and treat this as the long-form reference.

## Scope

- DDD layering and dependency direction
- API contract changes and error envelopes
- Data model changes and migration hygiene
- Service/repository boundaries and anti-pattern checks

## Execution Checklist

1. Plan API/data impacts before code changes.
2. Implement application/domain changes with type-safe contracts.
3. Add/adjust tests for behavior and edge cases.
4. Run review gate and verify no layering violations.

## Review Focus

- No business logic in controllers/handlers.
- No direct persistence in orchestration layer.
- No catch-and-ignore errors.
- No untyped public boundaries.

## Escalation

If architecture changes are broad (cross-bounded contexts, large migration surface), involve architecture review before implementation.
