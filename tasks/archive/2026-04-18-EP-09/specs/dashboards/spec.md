# Spec: Dashboards and Pipeline View

**Stories**: US-091 (Global dashboard), US-092 (By-person and by-team dashboards), US-093 (Pipeline view)
**Epic**: EP-09
**Dependencies**: EP-01 (work_items FSM), EP-06 (review_requests, validation_requirements), EP-08 (teams, members)

---

## US-091 — Global Dashboard

### Loading the Global Dashboard

WHEN a user opens the global dashboard
THEN the system returns aggregated metrics for all work items in the user's accessible scope
AND the response is served from a Redis cache (TTL: 120 seconds — owned by EP-12 caching policy)
AND a `cache_age_seconds` field is included in the response metadata

WHEN the Redis cache is cold (first load or after TTL expiry)
THEN the system computes aggregations via optimized SQL and populates the cache
AND the response time must be under 500ms including cache write

### State Distribution Widget

WHEN the state distribution widget loads
THEN it shows item counts grouped by state: `draft`, `in_clarification`, `in_review`, `partially_validated`, `ready`, `blocked`, `archived`
AND archived items are excluded from the default view
AND a toggle "Include archived" re-fetches with archived items included
AND each state bucket shows: count and percentage of total non-archived items

### Blocked Items Widget

WHEN the blocked items widget loads
THEN it shows the total count of items in `blocked` state
AND a list of up to 10 most recently blocked items is shown (id, title, owner, blocked_since)
AND a "View all blocked" link navigates to the list view pre-filtered by `state=blocked`

### Aging Metrics Widget

WHEN the aging metrics widget loads
THEN it shows average time in each state (in days), computed from state transition history
AND states with average age > 14 days are highlighted as a warning
AND states with no items show "—"

WHEN average age for `in_clarification` or `partially_validated` states exceeds 7 days
THEN those states are flagged with an "aging" indicator
AND the threshold values are configurable (default: 7 days for active states, 14 days for blocked)

### Completeness Distribution Widget

WHEN the completeness widget loads
THEN it shows counts in buckets: `0-25%`, `26-50%`, `51-75%`, `76-99%`, `100%`
AND each bucket links to a filtered list view

### Review Activity Widget

WHEN the review activity widget loads
THEN it shows: total open review requests, reviews pending > 48h (aging threshold), reviews closed in the last 7 days
AND "pending > 48h" reviews are listed with reviewer name and item title (up to 5 items)

### Global Dashboard Refresh

WHEN a user explicitly triggers "Refresh"
THEN the system invalidates the Redis cache key and re-fetches
AND the loading state is shown during re-fetch
AND the `last_updated` timestamp is updated in the UI

WHEN the dashboard auto-refreshes (polling interval: 5 minutes)
THEN the UI silently updates without showing a loading state
AND the `last_updated` timestamp updates

---

## US-092 — Dashboards By Person and By Team

### By-Person Dashboard

WHEN a user opens the by-person dashboard for a given `user_id`
THEN the system returns metrics scoped to items where `owner_id = user_id`
AND the response includes: display name, avatar URL, item count by state, completeness distribution, open review requests assigned to them, items blocked by their action

WHEN the authenticated user views their own by-person dashboard
THEN additionally, their inbox item counts are shown: items to review, items returned to them, items pending their decision

WHEN no items are owned by the specified user
THEN the dashboard shows zero-state widgets with "No items assigned"
AND the HTTP status is 200 (not 404)

WHEN the specified `user_id` does not exist
THEN the API returns HTTP 404

### By-Person: Workload Widget

WHEN the workload widget loads for a person
THEN it shows item counts per state (same as global state distribution but scoped to that owner)
AND it highlights if the person has more than 5 items in `in_clarification` simultaneously (overload indicator)
AND average item age in active states is shown per person

### By-Team Dashboard

WHEN a user opens the by-team dashboard for a given `team_id`
THEN the system returns metrics scoped to items assigned to that team
AND the response includes: team name, member count, item count by state, pending reviews (review_requests where reviewer is a team member), items blocked by team members

WHEN the team has sub-teams or parent teams
THEN the dashboard shows only direct team items (not recursive by default)
AND a toggle "Include sub-teams" triggers a recursive aggregation (extra 200ms budget)

WHEN the specified `team_id` does not exist
THEN the API returns HTTP 404

### By-Team: Pending Reviews Widget

WHEN the pending reviews widget loads
THEN it shows all open review_requests where the reviewer is a member of the team
AND each row shows: item title, requester name, reviewer name, requested_at, days pending
AND rows are sorted by `requested_at` ascending (oldest first)

### By-Team: Team Velocity Proxy Widget

WHEN the team velocity proxy widget loads
THEN it shows items that reached `ready` state in the last 30 days (count)
AND it shows items that reached `ready` state in the previous 30 days (count)
AND the delta (positive or negative trend) is displayed
AND this is explicitly labeled "Maturation velocity (items reaching ready)"

### Caching for By-Person and By-Team

WHEN a by-person dashboard is requested
THEN the result is cached in Redis with key `dashboard:person:{user_id}` and TTL: 120 seconds (EP-12)

WHEN a by-team dashboard is requested
THEN the result is cached in Redis with key `dashboard:team:{team_id}` and TTL: 120 seconds (EP-12)

WHEN any work item owned by a user changes state
THEN the `dashboard:person:{user_id}` cache key is invalidated immediately

WHEN any work item assigned to a team changes state
THEN the `dashboard:team:{team_id}` cache key is invalidated immediately

---

## US-093 — Pipeline / Flow View

### Loading the Pipeline View

WHEN a user opens the pipeline view
THEN items are displayed in columns, one column per maturation state (excluding `archived`)
AND columns follow the canonical FSM order: `draft` → `in_clarification` → `in_review` → `partially_validated` → `ready`
AND `blocked` items appear in a separate `blocked` lane visible across all pipeline stages
AND each column header shows: state name and item count

WHEN a user applies team or owner filters to the pipeline view
THEN only items matching those filters appear in the columns
AND column counts update to reflect the filtered set
AND filters are identical to the list view filter parameters

### Pipeline Column Content

WHEN a pipeline column loads
THEN each item card shows: title (truncated to 60 chars), type badge, owner avatar, completeness bar, and days-in-state
AND at most 20 cards are shown per column (virtual scroll or "load more" for overflow)
AND items are ordered within each column by `updated_at` descending

### Aging Indicators in Pipeline

WHEN an item has been in its current state for more than 7 days
THEN its card displays an amber aging badge showing "X days"

WHEN an item has been in its current state for more than 14 days
THEN the aging badge turns red

WHEN an item is in `blocked` state
THEN it always shows a red blocked badge regardless of age

### Pipeline: Blocked Lane

WHEN the blocked lane renders
THEN all blocked items are shown with their blocker description (first 80 chars)
AND each blocked item shows which state it was in before being blocked
AND a "Resolve" CTA on each blocked card navigates to the item detail

### Pipeline State Transition (Read-Only in Pipeline)

WHEN a user views the pipeline
THEN the pipeline is read-only — no drag-and-drop state transitions
AND state transitions happen only from the item detail view
AND this constraint is explicitly communicated in the UI ("To change state, open the item")

### Pipeline Aggregations (Data Layer)

WHEN computing pipeline data
THEN the query groups items by state with counts and computes `avg(NOW() - state_entered_at)` per state
AND the query runs against `work_items` with an index on `(state, updated_at)`
AND the pipeline data endpoint response time target is < 300ms for up to 500 items

WHEN the pipeline is requested
THEN the response is cached in Redis with key `pipeline:{filter_hash}` and TTL: 30 seconds
AND `filter_hash` is a deterministic hash of the applied filter parameters
