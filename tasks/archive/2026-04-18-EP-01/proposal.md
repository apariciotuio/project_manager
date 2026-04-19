# EP-01 — Core Model, States & Ownership

## Business Need

The work item is the central entity of the entire system. Before any capture, clarification, or review can happen, the domain model must exist with its state machine, ownership rules, and type system. This epic defines the backbone of the product.

## Objectives

- Define the work item entity with all supported types (Idea, Bug, Enhancement, Task, Initiative, Spike, Business Change, Requirement)
- Implement state machine: Draft -> In Clarification -> In Review -> Changes Requested -> Partially Validated -> Ready -> Exported
- Implement derived operational states: In Progress, Blocked, Ready
- Enforce single-owner model with reassignment
- Implement controlled override to Ready with justification and traceability

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-010 | Create core work item model | Must |
| US-011 | Implement state machine with transition rules | Must |
| US-012 | Manage single owner with reassignment | Must |
| US-013 | Force Ready with controlled override | Must |

## Acceptance Criteria

- WHEN a work item is created THEN it starts in Draft state with a single owner
- WHEN a state transition is attempted THEN the system validates it against the transition rules
- WHEN an invalid transition is attempted THEN the system rejects it with a clear reason
- WHEN the owner is reassigned THEN the change is audited with actor, timestamp, and previous owner
- WHEN the owner forces Ready with pending validations THEN the system requires confirmation AND justification AND records the override visibly
- AND the system supports all 8 element types
- AND both primary state and derived operational state are always computable

## Technical Notes

- State machine in backend (not just UI flags)
- Transition service with validation hooks
- Audit trail for all state changes and ownership changes
- Domain entity with business logic (not anemic model)
- Types as enum/value object, not separate tables unless needed

## Dependencies

- EP-00 (auth, user identity)

## Complexity Assessment

**High** — State machine design, override logic, audit trail, and ownership rules are the structural foundation. Getting this wrong cascades everywhere.

## Risks

- State machine too rigid (blocks UX) or too loose (no governance)
- Override abuse without proper tracking
- Ownership edge cases: suspended owner, orphaned items
