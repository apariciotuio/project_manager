# Spec: Listings and Unified Work View

**Stories**: US-090 (List elements with filters and quick views), US-095 (Unified work view)
**Epic**: EP-09
**Dependencies**: EP-01 (work_items), EP-02 (drafts/captures), EP-06 (reviews), EP-08 (teams)

---

## US-090 — List Elements with Filters and Quick Views

### Core Listing

WHEN a user opens the work items list
THEN the system returns a paginated list of work items ordered by `updated_at` descending by default
AND each item shows: id, title, type, state, owner display name, team name, project name, completeness percentage, updated_at, and blocked flag
AND the list defaults to 25 items per page using cursor-based pagination
AND a `next_cursor` and `total_count` are included in the response

WHEN the list loads
THEN items in `BLOCKED` state display a visual indicator
AND items with open review requests display a review badge
AND items with `completeness < 30%` display an incomplete indicator

### Filter: By State

WHEN a user applies a `state` filter (single or multi-value)
THEN only items in the selected states are returned
AND valid state values are: `DRAFT`, `CAPTURE`, `ENRICHMENT`, `VALIDATION`, `READY`, `BLOCKED`, `ARCHIVED`
AND multiple states are OR-combined (e.g., `state=DRAFT&state=ENRICHMENT` returns items in either state)

WHEN a user applies an invalid state value
THEN the API returns HTTP 422 with a descriptive validation error
AND no partial results are returned

### Filter: By Owner

WHEN a user applies an `owner_id` filter
THEN only items where `owner_id` matches are returned
AND the filter accepts a single user UUID

WHEN a user applies `owner_id=me`
THEN the system resolves the filter to the authenticated user's ID
AND items owned by that user are returned

### Filter: By Type

WHEN a user applies a `type` filter (single or multi-value)
THEN only items of the selected types are returned
AND valid types are the 8 EP-01 types: `STORY`, `TASK`, `BUG`, `SPIKE`, `EPIC`, `INITIATIVE`, `RFC`, `ADR`
AND multiple types are OR-combined

### Filter: By Team

WHEN a user applies a `team_id` filter
THEN only items assigned to that team are returned
AND the filter accepts a single team UUID
AND items with no team assigned are excluded

WHEN a user applies `team_id=mine`
THEN the system returns items belonging to any team the authenticated user is a member of
AND if the user belongs to multiple teams, results are UNION of all their teams

### Filter: By Project

WHEN a user applies a `project` filter
THEN only items tagged with that project identifier are returned
AND the filter is a string match (exact, case-insensitive)

### Filter Combinations

WHEN multiple filters are applied simultaneously
THEN all filters are AND-combined (intersection)
AND the response includes an `applied_filters` object echoing the parsed filter values
AND the response includes the `total_count` matching the filtered set

WHEN no filters are applied
THEN all items the authenticated user has read access to are returned
AND archived items (`state=ARCHIVED`) are excluded by default
AND a `include_archived=true` query param re-includes them

### Sorting

WHEN a user specifies a `sort_by` parameter
THEN the list is ordered by that field
AND supported sort fields are: `updated_at`, `created_at`, `title`, `state`, `completeness`
AND default sort direction is `desc`

WHEN a user specifies `sort_dir=asc`
THEN the list is ordered ascending by the specified field

WHEN an unsupported `sort_by` value is provided
THEN the API returns HTTP 422 with the list of valid sort fields

### Cursor-Based Pagination

WHEN a user provides a `cursor` query parameter
THEN the list returns items starting after the cursor position
AND the cursor encodes the last item's sort key + id (opaque, base64-encoded)

WHEN a user provides a `limit` parameter (max 100)
THEN the page size is set to that value
AND if `limit > 100`, the API caps at 100 and returns a warning in the response

WHEN there are no more items after the current page
THEN `next_cursor` is `null` in the response

### Quick View (Preview Panel)

WHEN a user triggers a quick view on a list item
THEN the system returns a summary payload for that item
AND the payload includes: title, type, state, owner, team, completeness, description excerpt (first 300 chars), open review count, blocker description if blocked, last activity timestamp
AND the quick view does NOT load the full spec, tasks, or comment thread
AND the quick view payload is returned in a single API call to `GET /api/v1/work-items/{id}/summary`

---

## US-095 — Unified Work View (Detail)

### Loading the Unified View

WHEN a user opens a work item detail
THEN a single API call to `GET /api/v1/work-items/{id}` returns the full unified payload
AND the payload includes all sections: header, spec, tasks, validation checklist, reviews, comments, timeline, and Jira reference if present
AND the response is assembled server-side (no N+1 client fetches)

### Header Section

WHEN the detail view loads
THEN the header shows: item id (human-readable slug), type badge, owner display name + avatar, current state, completeness percentage, and team name
AND the header shows a "next recommended action" derived from current state and completeness
AND if the item is blocked, the blocker reason is shown prominently in the header

### Recommended Next Action Logic

WHEN state is `DRAFT` AND completeness < 50%
THEN recommended action is "Complete specification"

WHEN state is `ENRICHMENT` AND open review requests exist
THEN recommended action is "Respond to review request from [reviewer name]"

WHEN state is `VALIDATION` AND validation requirements are not all met
THEN recommended action is "Complete validation checklist"

WHEN state is `READY`
THEN recommended action is "Item is ready — no action required"

WHEN state is `BLOCKED`
THEN recommended action is "Resolve blocker: [blocker description]"

### Specification Section

WHEN the spec section loads
THEN the current spec version is displayed
AND a diff toggle shows changes from the previous version (using EP-01 history)
AND if no spec exists, a prompt to add a spec is shown
AND spec is rendered as structured markdown

### Tasks Section

WHEN the tasks section loads
THEN all sub-tasks are listed with their states and assignees
AND a progress bar shows completed/total task count
AND tasks can be checked off directly from the detail view (action fires PATCH to task endpoint)

### Validation Checklist Section

WHEN the validation section loads
THEN the EP-06 validation_requirements for this item are listed
AND each requirement shows: description, met/unmet status, who verified it, and when
AND if no requirements exist, a message "No validation requirements defined" is shown

### Reviews Section

WHEN the reviews section loads
THEN all review_requests for this item are listed, grouped by open and closed
AND each review shows: reviewer, requested_by, created_at, status, and response summary if closed
AND open reviews are shown first
AND a user with the reviewer role can submit a response directly from this section

### Comments Section

WHEN the comments section loads
THEN all comments are shown in chronological order (oldest first)
AND each comment shows: author display name, avatar, timestamp, and content (markdown rendered)
AND the authenticated user can post a new comment from the detail view
AND comments support @mention (frontend renders mention as bold name; mention creates an EP-08 notification)

### Timeline / History Section

WHEN the timeline section loads
THEN all state transitions, ownership changes, review events, and comments are listed in reverse chronological order
AND each event shows: event type, actor, timestamp, and brief description
AND the timeline is loaded lazily (not included in the initial unified payload — separate call to `GET /api/v1/work-items/{id}/timeline`)

### Jira Reference

WHEN a Jira reference exists on the item
THEN a Jira badge is displayed in the header with the issue key
AND clicking it opens the Jira URL in a new tab
AND if no Jira is configured, the badge is absent — no error, no empty state

### Access Control

WHEN an unauthenticated user requests a work item detail
THEN the API returns HTTP 401

WHEN an authenticated user requests an item outside their accessible scope
THEN the API returns HTTP 403
AND no item data is leaked in the error body

### Mobile Behavior

WHEN the detail view is accessed on a mobile viewport
THEN sections collapse to an accordion layout
AND the header, next action, and open reviews are visible without scrolling
AND the user can post a comment and respond to reviews from mobile
