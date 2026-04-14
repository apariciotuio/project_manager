# US-082, US-084 — Notifications

## Overview

Notifications are event-driven. Every relevant domain event produces one or more notifications, routed to specific users. Notifications have a lifecycle (unread → read → actioned) and may carry a quick action payload.

---

## Triggering Events

| Domain Event | Recipient(s) | Notification Type |
|---|---|---|
| Review assigned to user | Assignee | `review.assigned` |
| Review assigned to team | All active team members | `review.team_assigned` |
| Review response submitted | Review requester | `review.responded` |
| Team review resolved | All team members + requester | `review.team_resolved` |
| Work item returned (request_changes) | Item owner | `item.returned` |
| Work item blocked | Item owner, blocker creator | `item.blocked` |
| Block removed | Item owner | `item.unblocked` |
| Work item state changed to Ready | Item owner | `item.ready` |
| User mentioned in comment | Mentioned user | `mention` |
| Assignment changed (owner changed) | New owner, previous owner | `assignment.changed` |
| Team membership added | New member | `team.joined` |
| Team membership removed | Removed member | `team.left` |
| Team lead assigned | New lead, previous lead | `team.lead_assigned` / `team.lead_removed` |
| Owner suspended with open items | Workspace admins | `admin.owner_suspended_alert` |

---

## Scenarios

### Notification Creation (US-082)

WHEN a domain event is published
THEN the notification service creates one notification record per recipient
AND each notification is created with state `unread`
AND each notification includes: type, actor (who triggered), subject entity (type + ID), workspace context, deeplink URL, optional quick action payload, created_at timestamp

WHEN a review is assigned to a team
THEN individual notification records are created for each active, non-suspended team member
AND notifications to suspended members are skipped silently

WHEN a notification is created for a user who has disabled that notification type in their preferences
THEN the notification is still created and stored (for inbox completeness)
AND real-time delivery is suppressed for that type

### Notification States (US-082)

WHEN a user reads a notification (opens the notification or navigates via deeplink)
THEN the notification state transitions from `unread` to `read`
AND the unread count for that user decrements

WHEN a user executes a quick action from a notification
THEN the notification state transitions to `actioned`
AND the action result is returned inline
AND the notification is marked `actioned` regardless of prior read state

WHEN a user marks all notifications as read
THEN all `unread` notifications for that user are bulk-updated to `read`
AND the unread count resets to 0

### Notification Retrieval

WHEN a user requests their notification list
THEN notifications are returned ordered by `created_at` descending, newest first
AND the response includes pagination (cursor-based)
AND the response includes aggregate counts: `total_unread`, `total`

WHEN a user filters notifications by type or state
THEN only matching notifications are returned
AND pagination applies to the filtered result set

WHEN a user requests a specific notification by ID that does not belong to them
THEN HTTP 403 Forbidden is returned

### Deeplinks (US-082)

WHEN a notification is created
THEN it includes a `deeplink` field pointing to the exact context: `/items/{id}`, `/items/{id}/reviews/{review_id}`, `/items/{id}#comment-{comment_id}`
AND the deeplink is always absolute within the application path

WHEN a user follows a deeplink from a notification
THEN the notification state transitions to `read` (if not already actioned)
AND the target view scrolls to the relevant element if anchor is present

### Quick Actions (US-084)

WHEN a notification of type `review.assigned` is displayed
THEN a quick action payload is included with options: `approve`, `reject`, `request_changes`
AND each option includes the action endpoint, HTTP method, and required payload schema

WHEN a user submits a quick action `approve` from a `review.assigned` notification
THEN the review is approved without navigating to the full item view
AND the notification transitions to `actioned`
AND a confirmation response is returned with the updated review state
AND if the review was a team review, the team review resolution flow applies

WHEN a user submits a quick action on a notification for a review that has already been resolved
THEN the request is rejected with HTTP 409 Conflict
AND the notification is updated to `actioned` with a `stale_action` flag
AND the user receives an inline error: "This review has already been resolved."

WHEN a notification of type `item.blocked` is displayed
THEN a quick action `resolve_block` is included for the blocker creator
AND submitting it removes the block and transitions the notification to `actioned`

WHEN a notification of type `item.returned` is displayed
THEN no quick action is included — the user must navigate to the item to respond

### Real-Time Delivery

WHEN a notification is created for a user who has an active WebSocket/SSE connection
THEN the notification payload is pushed to that connection immediately
AND the client unread count is incremented without requiring a full page refresh

WHEN a user's connection is inactive at notification creation time
THEN the notification is persisted in the DB and delivered on next inbox load

---

## Edge Cases

- Notification for a deleted item: the notification is preserved; the deeplink renders a "item no longer available" state; no quick action is available.
- Duplicate event fan-out (Celery retry): notifications are idempotent on `(user_id, event_id)`. Duplicate delivery attempts are silently skipped.
- User deleted: notifications for that user are soft-suppressed (not fan-out to deleted users).
