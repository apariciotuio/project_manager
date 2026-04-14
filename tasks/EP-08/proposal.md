# EP-08 — Teams, Assignments, Notifications & Inbox

## Business Need

Collaboration requires organizational structure. Teams group users for review routing and workload visibility. Notifications inform relevant actors of events. The inbox is the action hub — what needs my attention right now.

## Objectives

- Create and manage teams (name, description, members, optional lead)
- Assign work manually and suggest assignments based on routing rules
- Send internal notifications for relevant events (reviews, state changes, mentions, blocks)
- Provide a personal inbox prioritized by actionability
- Support quick actions directly from notifications and inbox

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-080 | Create and manage teams | Must |
| US-081 | Assign work manually and suggest assignments | Must |
| US-082 | Send internal notifications for relevant events | Must |
| US-083 | Show prioritized personal inbox | Must |
| US-084 | Execute quick actions from notifications and inbox | Should |

## Acceptance Criteria

- WHEN a team is created THEN members can be added/removed and an optional lead assigned
- WHEN a review is assigned to a team THEN all members are notified
- WHEN a team member responds to a team review THEN traceability shows who responded
- WHEN a relevant event occurs THEN affected users receive notifications
- WHEN the user opens inbox THEN items are sorted by priority: pending reviews > returned items > blocking items > decisions needed
- WHEN a notification has a quick action THEN it can be executed without navigating to the full element
- AND notifications link directly to the relevant context (deeplink)

## Technical Notes

- Team entity with membership (many-to-many users-teams)
- Notification service driven by domain events
- Inbox as aggregated query: pending reviews + owned blocked items + assignments
- Notification states: unread, read, actioned
- Simple assignment heuristics (project default owner, team routing rules)

## Dependencies

- EP-00 (auth, user identity)
- EP-01 (work items to assign and notify about)

## Complexity Assessment

**Medium-High** — Team management is straightforward, but notification fan-out, inbox aggregation queries, and quick actions add complexity. Notification fatigue is a UX risk.

## Risks

- Notification overload kills adoption
- Inbox query performance with many items
- Team review resolution ambiguity
