# US-081 — Assignments and Suggestions

## Overview

Assignments connect work items to owners and reviewers. Manual assignment is always permitted. The system suggests assignees based on routing rules (project default owner, team by item type, reviewer by context label). Suggestions are non-binding.

---

## Scenarios

### Manual Assignment — Owner

WHEN an authorized user (admin, item creator, or current owner) submits an assignment request for a work item with a target user ID
THEN the item's `owner_id` is updated to the target user
AND an `assignment.changed` notification is sent to both the new owner and the previous owner
AND an audit event is logged with actor, previous owner, new owner, and timestamp

WHEN a user attempts to manually assign a work item to a suspended user
THEN the request is rejected with HTTP 422
AND the error states the target user is suspended and cannot receive assignments

WHEN a user without assignment permission attempts to assign a work item
THEN the request is rejected with HTTP 403 Forbidden

### Manual Assignment — Reviewer

WHEN an authorized user creates a review on a work item and specifies a target user or team
THEN the review is created with the specified assignee
AND the assignee (user or all team members) receives a `review.assigned` / `review.team_assigned` notification

WHEN no reviewer is specified during review creation
THEN the review is created without an assignee
AND the system optionally attaches a suggested reviewer from routing rules (non-binding, not auto-assigned)

### Suggested Assignment — Owner

WHEN a new work item is created in a project that has a configured `default_owner_rule`
THEN the system evaluates the rule and returns a suggested owner in the creation response
AND the suggestion is surfaced in the UI as a pre-filled but editable field
AND if the user accepts the suggestion, a manual assignment is performed with the suggested user

WHEN a project has no `default_owner_rule`
THEN no owner suggestion is returned
AND the item is created with `owner_id = null` (unowned)

### Suggested Assignment — Reviewer (Routing Rules)

WHEN a review is being created and the item has a type that matches a routing rule
THEN the system suggests the configured team or user for that item type
AND the suggestion is returned in the review creation form response as `suggested_reviewer`
AND the user can accept, change, or ignore the suggestion

WHEN a routing rule matches by context label
THEN the suggested reviewer is the user or team associated with that label in the routing configuration
AND multiple matches return the highest-priority match (rule ordering)

WHEN no routing rule matches the item type or context labels
THEN no suggestion is returned
AND the reviewer field is left blank for manual entry

### Routing Rule Evaluation

WHEN the system evaluates routing rules
THEN rules are evaluated in priority order (explicit type match > label match > project default > no match)
AND suspended users or teams with no active members are skipped in suggestions
AND the first valid match is returned

WHEN a suggested team has no active non-suspended members
THEN the suggestion is skipped and the next matching rule is evaluated

### Assignment Validation

WHEN the system processes any assignment (manual or accepted suggestion)
THEN it validates: target user/team exists, is active, and has workspace access
AND if the target is a team, the team must have `can_receive_reviews = true` for reviewer assignments

---

## Edge Cases

- Owner is suspended after assignment: existing ownership is preserved; an `admin.owner_suspended_alert` is sent to admins; the item appears in the admin observability view as needing reassignment.
- Default owner rule references a deleted user: the rule is skipped; no suggestion is made; no error is surfaced to the end user; an admin-visible configuration warning is flagged.
- Routing rule references a deleted team: same as above — skip and flag.
- Bulk assignment (assigning multiple items to one owner): supported as a batch endpoint; each item generates its own audit event and notification; suspended target rejects the entire batch.
