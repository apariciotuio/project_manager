# EP-06 — Reviews, Validations & Flow to Ready

## Business Need

The maturation process requires explicit human validation. Owners request reviews from individuals or teams, reviewers approve/reject/request changes, and validation checklists gate the transition to Ready. This is the governance layer that ensures quality before execution.

## Objectives

- Request reviews from specific users or teams
- Support review responses: approve, reject, request changes
- Manage validation checklists (required vs recommended)
- Support iterative back-and-forth between owner and reviewers
- Control normal flow to Ready (all validations pass) and override flow (owner forces with justification)

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-060 | Request review from users or teams | Must |
| US-061 | Respond to review: approve, reject, or request changes | Must |
| US-062 | Manage validation checklist | Must |
| US-063 | Support iterative owner-reviewer flow | Must |
| US-064 | Apply normal and override flow to Ready | Must |

## Acceptance Criteria

- WHEN a review is requested THEN specific users/team members are notified
- WHEN a reviewer responds THEN the result is recorded with actor, timestamp, and content
- WHEN a team review is resolved THEN the responding member is identified
- WHEN all required validations pass THEN the owner can mark Ready normally
- WHEN required validations are pending THEN normal Ready is blocked
- WHEN the owner forces Ready THEN confirmation + justification + visible trace are required
- AND reviews reference a specific version of the element
- AND the validation checklist updates when a relevant review closes

## Technical Notes

- Review request/response entities
- Validation requirement/status entities
- Fan-out notifications to team members
- Version-pinned reviews (review targets a specific version)
- Override audit with justification field

## Dependencies

- EP-01 (states, ownership)
- EP-04 (specification to review)
- EP-05 (breakdown to validate)
- EP-08 (teams for team-based reviews)

## Complexity Assessment

**High** — Multiple entity interactions, version-pinned reviews, team fan-out, validation checklist logic, and the override mechanism. This is the governance backbone.

## Risks

- Review fatigue if too many validations required
- Team review resolution ambiguity (who speaks for the team?)
- Version drift: review targets v3 but element is now v5
