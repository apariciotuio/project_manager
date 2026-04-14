# Security by Design Playbook

Use this playbook for threat-first implementation and review on any externally reachable path.

## Scope

- Input validation and boundary hardening
- Authentication/authorization checks
- Secrets and configuration hygiene
- Failure-mode and abuse-case analysis

## Threat-First Checklist

1. Identify abuse paths (IDOR, injection, privilege escalation, replay, data leakage).
2. Validate all external inputs at boundaries.
3. Enforce authn/authz for every sensitive action.
4. Confirm secrets are never hardcoded or logged.

## Review Focus

- Deny-by-default behavior on error.
- No custom cryptography primitives.
- No trust in client-provided identity/authorization context.

## Escalation

For high-impact auth/session/token changes, require explicit security review before deployment.
