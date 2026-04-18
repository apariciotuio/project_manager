# US-083 — Personal Inbox

## Overview

The inbox is the user's action hub. It aggregates actionable items across the system, sorted by priority tier, not raw recency. It shows what needs the user's attention right now.

---

## Priority Tiers (descending)

| Tier | Condition | Label |
|---|---|---|
| 1 | `review_requests` where `reviewer_id = user` (type=user) OR `team_id IN user's teams` (type=team), status=`pending` | Pending reviews |
| 2 | `work_items` where `owner_id = user` AND state=`changes_requested` | Changes requested |
| 3 | `review_responses` where `responder_id = user` AND `decision=changes_requested` AND the linked `review_request.status` is still `pending` | Pending my feedback |
| 4 | `work_items` where `owner_id = user` AND state IN (`draft`, `in_clarification`) AND `completeness_score < 50` | Needs attention |

Within each tier, items are ordered by `created_at` ascending (oldest first = most urgent).

---

## Scenarios

### Inbox Load

WHEN an authenticated user opens the inbox
THEN the response contains items grouped by priority tier
AND each tier shows a count and a paginated list of items
AND the total actionable count is returned as a badge value
AND items resolved since the last load are excluded

WHEN the inbox is empty (no actionable items)
THEN the response returns an empty list per tier
AND the total count is 0

WHEN a user opens the inbox and has team-assigned reviews
THEN those reviews appear in tier 1 attributed to the team with a team indicator
AND if the review has already been resolved by a teammate, it is excluded from the user's inbox

### Inbox Item Structure

WHEN an inbox item is returned
THEN each item includes: item ID, item type, item title, owner, current state, priority tier, tier label, age (created_at of the triggering event), deeplink URL, optional quick action payload, and a `source` field (direct or team)

WHEN an inbox item belongs to tier 1 and has a quick action available
THEN the quick action payload is included in the item response
AND the user can execute the action without leaving the inbox

### Aggregation Logic

WHEN computing tier 1 (pending reviews)
THEN query includes: review_requests where (reviewer_id = user AND reviewer_type = 'user') OR (reviewer_type = 'team' AND team_id IN user's active team memberships) AND status = 'pending'
AND team reviews where a review_response already exists are excluded (NOT EXISTS on review_responses)
AND workspace_id filter is applied on every branch

WHEN computing tier 2 (changes requested)
THEN query includes: work_items where owner_id = user AND state = 'changes_requested' AND workspace_id = user's workspace

WHEN computing tier 3 (pending my feedback)
THEN query includes: review_responses where responder_id = user AND decision = 'changes_requested'
AND the linked review_request still has status = 'pending' (NOT EXISTS on approved/rejected status)
AND workspace_id filter applied via work_items join

WHEN computing tier 4 (needs attention)
THEN query includes: work_items where owner_id = user AND state IN ('draft', 'in_clarification') AND completeness_score < 50 AND workspace_id = user's workspace

### Inbox Refresh and Real-Time Updates

WHEN a new actionable event occurs for the user
THEN the inbox badge count increments in real time (via SSE event `inbox_count_updated`)
AND the full inbox list is refreshed lazily on next user interaction, not pushed wholesale

WHEN the user resolves an action (e.g., approves a review from quick action)
THEN the corresponding inbox item is removed from the list without a full page reload
AND the tier count and total badge update immediately

### Deeplinks from Inbox

WHEN the user clicks an inbox item
THEN they are navigated to the exact context: item detail, review panel, or block detail
AND the inbox item is not automatically marked resolved — resolution depends on the action taken

### Pagination and Performance

WHEN a user has more than 20 items in a single tier
THEN pagination is applied per tier (cursor-based, page size 20)
AND the user can load more items within a tier independently

WHEN the inbox query executes
THEN it runs as a single aggregated query (or at most one query per tier) with proper indexes
AND response time must be under 300ms at p99 for users with up to 500 inbox items

### Filtering and Search within Inbox

WHEN a user applies a type filter to the inbox
THEN only items of the selected type are shown across all tiers
AND tier counts update to reflect the filter

WHEN a user applies a state filter
THEN items outside the selected state are excluded

---

## Edge Cases

- An item appears in multiple tiers (owned + returned + blocking): it appears only in the highest priority tier to avoid duplication.
- A user is removed from a team while having team reviews in tier 1: those reviews are removed from their inbox immediately.
- An item owner changes while the item is in tier 2: the inbox item is removed from the previous owner's inbox and added to the new owner's inbox.
- Inbox query must handle users with 0 team memberships without failing (empty IN clause handled as no-match).
