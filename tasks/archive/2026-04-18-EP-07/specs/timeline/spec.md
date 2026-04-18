# US-073 — Unified Timeline

## Overview

The timeline presents all events in a work item's lifecycle in reverse-chronological order. It aggregates events from: state changes, specification edits (versioning), review requests and responses, exports, comments, and AI suggestions. Every event identifies the actor and their type (human / AI / system). The timeline is filterable and paginated.

---

## Scenarios

### SC-073-01: Timeline shows all event types chronologically

WHEN a user opens the timeline for a work item
THEN all events are returned in descending `occurred_at` order
AND the following event types are included:

| Event Type | Source | Actor |
|------------|--------|-------|
| `state_transition` | `audit_events` (EP-01) | human or system |
| `content_edit` | `work_item_versions` (EP-07) | human or ai_suggestion |
| `breakdown_change` | `work_item_versions` (EP-07) | human |
| `review_requested` | `review_requests` (EP-06) | human |
| `review_submitted` | `review_responses` (EP-06) | human |
| `comment_added` | `comments` (EP-07) | human or ai_suggestion |
| `comment_deleted` | `comments` soft-delete (EP-07) | human |
| `export_triggered` | `export_events` (EP-11) | human |
| `suggestion_applied` | `audit_events` or `work_item_versions` | ai_suggestion |

AND each event record contains: `event_type`, `occurred_at`, `actor_id`, `actor_type`, `actor_display_name`, `summary` (human-readable one-liner), and optional `payload` (event-specific detail)

---

### SC-073-02: Actor type is always present and accurate

WHEN any event appears in the timeline
THEN `actor_type` is one of: `human`, `ai_suggestion`, `system`
AND `actor_type = system` is used for automated transitions (e.g., scheduled state promotions, system-generated versions)
AND `actor_type = ai_suggestion` is used for any action initiated by an AI agent
AND `actor_type = human` is used for any action initiated by an authenticated user
AND the UI renders each actor type with a distinct visual indicator (icon or badge)

---

### SC-073-03: Filter timeline by event type

WHEN a user applies an event type filter (one or more types from the enum above)
THEN only events matching the selected types are returned
AND the filter is applied server-side
AND pagination is recalculated for the filtered result set

---

### SC-073-04: Filter timeline by actor type

WHEN a user applies an actor type filter (`human`, `ai_suggestion`, or `system`)
THEN only events with matching `actor_type` are returned

---

### SC-073-05: Filter timeline by date range

WHEN a user specifies `from_date` and/or `to_date`
THEN only events with `occurred_at` within the range are returned
AND `from_date` is inclusive, `to_date` is inclusive

---

### SC-073-06: Pagination

WHEN the timeline is fetched
THEN the default page size is 50 events
AND the API supports cursor-based pagination via `before` (timestamp + id) to enable stable paging on an append-only log
AND total count is NOT required (unbounded log — return `has_more: true/false` instead)

---

### SC-073-07: Timeline event for a comment thread

WHEN a comment is added to the timeline feed
THEN only the root comment appears as a timeline event (replies do not generate separate events)
AND the event `payload` includes `comment_id`, `is_anchored`, `anchor_section_id` (if applicable), and `reply_count`

---

### SC-073-08: Timeline event for version / diff navigation

WHEN a `content_edit` or `breakdown_change` event appears
THEN the event `payload` includes `version_number` and a direct link to the version diff view (diff from previous version)
AND if no previous version exists (first version), the diff link shows the full content as "added"

---

### SC-073-09: Timeline event for review

WHEN a `review_submitted` event appears
THEN the `payload` includes `review_id`, `outcome` (`approved` / `rejected` / `changes_requested`), `reviewer_id`, and `comment_count`
AND the timeline event links to the full review detail

---

### SC-073-10: Timeline event for export

WHEN an `export_triggered` event appears
THEN the `payload` includes `export_target` (e.g., `jira`), `exported_version_number`, and `external_reference` (e.g., Jira ticket key) if available
AND the event is only created for explicit user-triggered exports (no silent export events)

---

### SC-073-11: Timeline is immutable from the user's perspective

WHEN events appear in the timeline
THEN no event can be deleted or edited by a user
AND soft-deleted comments appear as `[deleted]` events rather than disappearing from the log
AND the timeline reflects the true history without gaps

---

### SC-073-12: Empty timeline

WHEN a work item has no events beyond its creation
THEN the timeline returns a single `item_created` event
AND the response includes `has_more: false`
AND the API returns HTTP 200 with an empty-but-valid event list structure (not 404)

---

## API Contract

```
GET /api/v1/work-items/{work_item_id}/timeline
  ?event_types=state_transition,comment_added   (optional, comma-separated)
  &actor_types=human,ai_suggestion              (optional)
  &from_date=2025-01-01                         (optional, ISO 8601 date)
  &to_date=2025-12-31                           (optional, ISO 8601 date)
  &before=<cursor>                              (optional, for pagination)
  &limit=50                                     (optional, max 200)

Response:
{
  "data": {
    "events": [...],
    "has_more": true,
    "next_cursor": "<cursor>"
  }
}
```

---

## Data Constraints

| Field | Rule |
|-------|------|
| `event_type` | Enum — closed set (extensible via migration, not open-ended) |
| `actor_type` | Enum: `human`, `ai_suggestion`, `system` — required, never null |
| `occurred_at` | UTC timestamp, indexed for range queries |
| `payload` | JSONB, schema varies per event_type — validated at write time |
| `summary` | Required, max 255 characters, human-readable |

---

## Out of Scope

> ⚠️ Items below were originally MVP-scoped deferrals. Review each against full-product scope; log outcomes in decisions_pending.md.

- Real-time timeline push (WebSocket / SSE)
- Per-user timeline views (everyone sees the full timeline)
- Export of timeline to PDF/CSV
- Search within timeline (full-text on `summary` or `payload`)
