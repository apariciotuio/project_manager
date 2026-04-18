# US-080 — Team Management

## Overview

Teams group users to receive reviews and validations. A team review is resolved when one authorized member responds. The team does not replace the owner — it channels work and validation.

---

## Scenarios

### Team Creation

WHEN an authenticated user with admin or team-manager role submits a create team request with a unique name and optional description
THEN a new team is created with status `active`
AND the creator is automatically added as team lead
AND the team is returned with its generated ID, name, description, lead, and member count of 1

WHEN a user submits a create team request with a name that already exists in the workspace
THEN the request is rejected with HTTP 409 Conflict
AND the error identifies the duplicate field

WHEN a user submits a create team request with a missing or empty name
THEN the request is rejected with HTTP 422 Unprocessable Entity

### Team Retrieval

WHEN any authenticated user requests the list of teams
THEN all active teams are returned with ID, name, description, lead user, and member count
AND suspended or deleted teams are excluded unless the `include_inactive=true` query param is present

WHEN a user requests a specific team by ID
THEN the team detail is returned including the full member list with user IDs, names, roles, and join date
AND if the team does not exist, HTTP 404 is returned

### Team Update

WHEN a team lead or admin submits an update for name or description
THEN the team record is updated
AND a `team.updated` audit event is logged with actor, timestamp, and changed fields

WHEN a non-lead, non-admin user attempts to update a team
THEN the request is rejected with HTTP 403 Forbidden

### Team Deletion (Logical)

WHEN an admin marks a team as deleted
THEN the team status is set to `deleted` and it no longer appears in active lists
AND historical references (audit, review traceability) are preserved
AND all pending team-assigned reviews remain visible to the original reviewers with a `team_dissolved` flag

WHEN a non-admin attempts to delete a team
THEN the request is rejected with HTTP 403 Forbidden

### Member Management — Add

WHEN a team lead or admin adds a user to a team
THEN a membership record is created with role `member` and join timestamp
AND the added user receives a notification of type `team.joined`
AND the team member count increments

WHEN attempting to add a user who is already a team member
THEN the request is rejected with HTTP 409 Conflict

WHEN attempting to add a suspended user to a team
THEN the request is rejected with HTTP 422
AND the error states the user is suspended and cannot receive new assignments

### Member Management — Remove

WHEN a team lead or admin removes a member from the team
THEN the membership record is soft-deleted (removed_at timestamp set)
AND historical audit entries and review traceability referencing this member are preserved
AND the removed user receives a notification of type `team.left`

WHEN a team lead attempts to remove themselves as the last team lead and no other lead exists
THEN the request is rejected with HTTP 422
AND the error states a team must always have at least one lead

### Team Lead Assignment

WHEN a team lead or admin assigns a different member as team lead
THEN the target member's role is updated to `lead`
AND the previous lead's role is downgraded to `member`
AND both users receive a notification (`team.lead_assigned`, `team.lead_removed`)
AND an audit event is logged

WHEN a team lead or admin assigns a user who is not a member as lead
THEN the user is first added as a member
AND then promoted to lead in a single atomic operation

### Review-Enabled Flag

WHEN an admin sets a team's `can_receive_reviews` flag to `true`
THEN the team becomes selectable as a reviewer target in the review creation flow
AND if set to `false`, the team is hidden from reviewer selection and existing pending team reviews are unaffected

### Team Review Resolution

WHEN a review is assigned to a team
THEN all active, non-suspended members of that team receive a notification
AND the review shows as pending for each member in their inbox

WHEN one authorized team member submits a final response (approve/reject/request_changes) on the review
THEN the review status transitions to the appropriate resolved state
AND a traceability record is created linking the review, the responding member, and the team
AND a notification is sent to the review requester
AND the review is removed from all other team members' inboxes

WHEN a team member submits a comment (not a final response) on a team review
THEN the comment is recorded and attributed to that member
AND other team members see the comment but the review remains open
AND the traceability record reflects this partial participation

WHEN a team has no active non-suspended members at the time of review assignment
THEN the assignment is rejected with HTTP 422
AND the error states the team has no active members to receive the review

---

## Edge Cases

- A team member suspended after being notified of a team review: the review remains assigned to the team; the suspended member's inbox item is suppressed; remaining active members continue to see it.
- A team is deleted while a review is assigned to it: the review is marked `team_dissolved` and the requester is notified to reassign.
- Multiple members respond before the first response is processed (race condition): the first commit wins; subsequent submissions are rejected with HTTP 409 stating the review is already resolved.
