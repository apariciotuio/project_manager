# Temporal Workflow Playbook

Use this playbook when creating/updating workflows, activities, workers, and launchers.

## Scope

- Deterministic workflow logic
- Activity design and retries
- Worker registration and queue boundaries
- Signals/updates/queries patterns

## Determinism Guardrails

- Keep all I/O in activities.
- Keep workflow state typed and minimal.
- Use Temporal-safe time/uuid APIs in workflows.

## Execution Checklist

1. Define typed workflow/activity inputs and outputs.
2. Implement activities with explicit timeouts and idempotency.
3. Register workflow/activity in workers.
4. Test workflow paths including signals/updates where relevant.

## Review Focus

- No non-deterministic operations in workflow code.
- No hidden activity imports in restricted contexts.
- No unregistered workflows/activities.

## Escalation

For in-flight workflow behavior changes, require versioning strategy before merge.
