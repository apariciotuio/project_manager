# US-070 — Anchored Comments

## Overview

Users can attach comments to a work item either generally (top-level) or anchored to a specific content section and optional text range within that section. Comments support threaded replies. Anchors survive content edits with best-effort stability.

---

## Scenarios

### SC-070-01: Add a general comment

WHEN a user submits a comment on a work item without selecting a section or text range
THEN a comment record is created with `anchor_section_id = NULL` and `anchor_range = NULL`
AND the comment is visible in the work item comment feed ordered by `created_at` descending
AND the comment stores `actor_type` (human | ai_suggestion | system), `actor_id`, and `created_at`

---

### SC-070-02: Add a comment anchored to a section

WHEN a user submits a comment with a target section selected
THEN a comment record is created with `anchor_section_id` set to the stable UUID of that section
AND the comment is visible in the section's inline comment thread
AND the comment is also visible in the unified comment feed with its anchor context

---

### SC-070-03: Add a comment anchored to a text range within a section

WHEN a user submits a comment with a text range selected (start offset, end offset) within a section
THEN a comment record is created with `anchor_section_id`, `anchor_start_offset`, and `anchor_end_offset`
AND the selected text at the time of anchoring is stored as `anchor_snapshot_text` (immutable)
AND the comment is visible inline adjacent to the anchored text region

---

### SC-070-04: Anchor stability after section content is edited

WHEN a section's content is updated after a text-range-anchored comment exists
THEN the comment's `anchor_section_id` remains valid (section UUID does not change)
AND the system attempts to re-locate the `anchor_snapshot_text` within the updated content using fuzzy matching
AND IF the snapshot text is found at a new offset THEN `anchor_start_offset` and `anchor_end_offset` are updated silently
AND IF the snapshot text cannot be found THEN the anchor is marked `anchor_status = orphaned` and the comment is displayed as a general section comment with a visual indicator
AND the original `anchor_snapshot_text` is never modified

---

### SC-070-05: Section is deleted after comment was anchored to it

WHEN a section that has anchored comments is deleted
THEN the affected comments' `anchor_status` is set to `orphaned`
AND the comments are NOT deleted — they remain visible in the general comment feed with an orphan indicator
AND the `anchor_section_id` is preserved for audit purposes

---

### SC-070-06: Edit own comment

WHEN the comment author edits their comment
THEN the comment body is updated
AND an `edited_at` timestamp is recorded
AND a flag `is_edited = true` is set
AND the original body is NOT preserved (no comment version history required for MVP)
AND other users see the edited label next to the comment

---

### SC-070-07: Delete own comment

WHEN the comment author deletes their comment
THEN the comment is soft-deleted (`deleted_at` is set, record is retained)
AND the comment is hidden from the UI feed
AND if the comment is a parent with replies, the body is replaced with "[deleted]" and replies remain visible
AND timeline events referencing this comment survive deletion

---

### SC-070-08: Reply to a comment (thread)

WHEN a user submits a reply to an existing comment
THEN the reply is created with `parent_comment_id` set to the parent comment UUID
AND replies are nested one level deep only (replies cannot be replied to)
AND the parent comment's `reply_count` is incremented
AND the anchor context of the parent is inherited for display but the reply itself has no independent anchor

---

### SC-070-09: AI suggestion as comment

WHEN the system creates a comment on behalf of an AI process
THEN the comment is stored with `actor_type = ai_suggestion`
AND the comment is visually distinguished in the feed
AND the comment cannot be "edited" — AI comments are immutable; only deletion by an authorized human is permitted

---

### SC-070-10: Pagination of comments

WHEN a user loads the comment feed for a work item
THEN comments are returned paginated (default page size: 25)
AND the API supports cursor-based pagination via `after` parameter
AND the total comment count is returned in the response

---

## Data Constraints

| Field | Rule |
|-------|------|
| `body` | Required, 1–10,000 characters |
| `anchor_start_offset` | Non-negative integer; must be <= `anchor_end_offset` |
| `anchor_end_offset` | Must be <= length of section content at time of creation |
| `anchor_snapshot_text` | Immutable after creation |
| `parent_comment_id` | Must reference a comment with `parent_comment_id = NULL` (no deep nesting) |
| `actor_type` | Enum: `human`, `ai_suggestion`, `system` |
| `anchor_status` | Enum: `active`, `orphaned` — default `active` |

---

## Out of Scope (MVP)

- Reactions / emoji responses
- Mentions / notifications
- Comment search
- Comment version history (edit audit trail)
