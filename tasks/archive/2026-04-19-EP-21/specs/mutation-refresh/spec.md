# Spec — Frontend Refresh After Mutation (F-3)

**Capability:** After any mutation (create/update/delete), the UI reflects the new state without manual reload.

## Scenarios

### Add team member reflects immediately

- **WHEN** the user adds a member to a team via the `AddMember` dialog
- **AND** the backend returns 201
- **THEN** the team's member list in the UI shows the new member within 200ms
- **AND** no page reload is required

### Create tag reflects immediately

- **WHEN** the user creates a new tag in the admin page
- **AND** the backend returns 201
- **THEN** the tag list shows the new tag without reload

### Delete tag reflects immediately

- **WHEN** the user deletes a tag
- **AND** the backend returns 204
- **THEN** the tag disappears from the list without reload

### Create project reflects immediately

- **WHEN** the user creates a project
- **AND** the backend returns 201
- **THEN** the project list shows the new project without reload

### Add member to project reflects immediately

- **WHEN** the user adds a member to a project
- **AND** the backend returns 201
- **THEN** the member appears in the project's member list without reload

### Work item state transition reflects immediately

- **WHEN** the user transitions a work item to `ready`
- **AND** the backend returns 200
- **THEN** the state chip updates without reload
- **AND** if viewing the items list, the item moves between state columns without reload

### Failed mutation does not mutate local state

- **WHEN** a mutation returns a non-2xx response
- **THEN** local state is unchanged
- **AND** the error is surfaced via the error envelope (see `error-envelope` spec)

## Audit — hooks in scope

Every hook in `frontend/hooks/` with a mutation function must be verified:

- `use-teams.ts` — `addMember` (**confirmed broken**), `createTeam`, `deleteTeam`, `removeMember`
- `use-tags.ts` — all mutations
- `use-projects.ts` — all mutations
- `use-admin.ts` — member operations
- `use-work-item.ts` — state transitions, edits
- `use-work-items.ts` — create, delete

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| Optimistic updates cause inconsistent UI if backend rejects | Pessimistic update: wait for 2xx response before mutating local state |
| Local state drifts from server over time | Each mutation hook either updates locally from response OR re-fetches the list |
| Race condition: two mutations in flight | Sequential mutation guard per hook (disable button while pending) |

## Out of Scope

- Migration to TanStack Query / SWR (separate EP, tracked as refactor candidate)
- Realtime multi-user sync (WS broadcast of mutations)
