# EP-10 — Configuration, Projects, Rules & Administration

## Business Need

The system needs governance. Workspace admins must manage members, teams, validation rules, routing rules, templates, project context, and integrations. Without this layer, the product depends on informal configuration and engineering support for every change.

## Objectives

- Manage workspace members: invite, activate, suspend, logical delete
- Manage teams and team leads
- Configure validation rules (required/recommended, by element type, by project)
- Configure routing rules (suggested team, suggested owner, suggested validators)
- Configure templates per element type and project
- Manage projects/spaces: name, description, associated teams, context sources, local rules
- Configure Jira integration (credentials, mappings, health check)
- Manage operational capabilities (permission matrix per role)
- Provide admin audit log
- Provide admin health dashboard
- Provide basic support tools (reassign orphaned items, retry exports, resend invites)

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-100 | Select relevant context sources | Must |
| US-101 | Save reusable context configurations | Should |
| US-102 | Configure participants, teams, and validation rules | Must |
| US-103 | Use roles as contextual labels and routing hints | Must |
| US-104 | Configure Jira integration | Must |
| US-105 | Manage workspace members | Must |
| US-106 | Manage operational capabilities and admin scope | Must |
| US-107 | View admin audit log | Must |
| US-108 | View admin health dashboard | Should |
| US-109 | Operate basic support tools | Should |

## Acceptance Criteria

- WHEN an admin invites a member THEN the invitation is trackable and resendable
- WHEN a member is suspended THEN they cannot operate AND owned items trigger reassignment alert
- WHEN validation rules are configured THEN they apply to new elements of the matching type/project
- WHEN routing rules are configured THEN the system suggests accordingly during reviews/assignments
- WHEN Jira is configured THEN a health check validates the connection
- WHEN an admin action occurs THEN it is recorded in the audit log (actor, timestamp, action, entity, before/after)
- WHEN viewing the health dashboard THEN workspace health (elements by state, aging blocks), org health (inactive members, teamless users), process health (override rate, validation compliance), integration health (Jira status, export failures) are visible
- AND context labels are separate from operational permissions
- AND the system works with minimal configuration (sensible defaults)

## Technical Notes

- Configuration entities with workspace/project scoping
- Permission matrix implementation (capability-based, not full RBAC)
- Audit events table with before/after values
- Health dashboard as aggregation queries
- Jira health check as async probe
- Rule precedence: project overrides workspace (except global blockers)

## Dependencies

- EP-00 (auth, user identity)
- EP-08 (teams to configure)

## Complexity Assessment

**High** — This is the largest epic by surface area: 10 user stories spanning members, teams, rules, templates, projects, integrations, audit, dashboards, and support tools. Needs careful scoping to avoid building an enterprise admin console.

## Risks

- Admin complexity deters adoption
- Rule configuration UX too abstract
- Permission edge cases (overlapping roles, delegated capabilities)
- Audit log storage growth
