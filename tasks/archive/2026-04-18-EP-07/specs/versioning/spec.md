# US-071 & US-072 — Versioning and Diff

## Overview

The system automatically creates version snapshots of a work item when meaningful changes occur. Users can navigate the version history and compare any two versions via a structured, readable diff. Diff operates at two levels: section-level structural changes and text-level content changes within sections.

---

## US-071 — Version Relevant Changes

### SC-071-01: Version created on specification content change

WHEN a user saves changes to any section of a work item's specification (EP-04 `work_item_sections`)
AND at least one section's `content` or `order` has changed
THEN a new `work_item_versions` record is created with a full snapshot of all sections at that point in time
AND the version is tagged with `trigger = content_edit`, `actor_type`, and `actor_id`
AND the version receives an auto-incrementing `version_number` scoped to the work item

---

### SC-071-02: Version created on state transition

WHEN a work item's FSM state changes (EP-01)
THEN a new version is created tagged with `trigger = state_transition`
AND the version captures the state at the moment of transition
AND the new state is stored in the version snapshot metadata

---

### SC-071-03: Version created on review approval or rejection

WHEN a review response is submitted (EP-06) with outcome `approved` or `rejected`
THEN a new version is created tagged with `trigger = review_outcome`
AND the snapshot reflects the content at the moment the review concluded

---

### SC-071-04: No version created for non-meaningful changes

WHEN a user performs an action that does not alter specification content, state, or review outcome
(examples: viewing the item, adding a comment, changing assignee)
THEN no new version record is created
AND the version history is unchanged

---

### SC-071-05: Version created on task hierarchy change

WHEN a task node is added, removed, or reordered in the breakdown (EP-05)
THEN a new version is created tagged with `trigger = breakdown_change`

---

### SC-071-06: Version snapshot content

WHEN a version is created
THEN the snapshot stores a full copy of all `work_item_sections` (section_type, content, order) as a JSON blob
AND stores a copy of the work item top-level fields (title, description, state, owner_id)
AND stores version metadata: `version_number`, `created_at`, `actor_type`, `actor_id`, `trigger`, `commit_message` (optional, human-provided)
AND the snapshot is immutable after creation — no edits to a version record are permitted

---

### SC-071-07: Version count and retention

WHEN a work item accumulates more than 500 versions
THEN the system retains all versions but marks older versions as `archived = true`
AND archived versions are excluded from the default version list (fetchable explicitly)
AND no versions are permanently deleted ⚠️ originally MVP-scoped — see decisions_pending.md

---

### SC-071-08: Navigate version history

WHEN a user opens the version history panel
THEN versions are listed in reverse chronological order with `version_number`, `created_at`, `actor`, `trigger`, and optional `commit_message`
AND selecting a version renders the work item in read-only mode as it was at that version
AND the current (latest) version is highlighted

---

## US-072 — Compare Versions with Diff

### SC-072-01: Diff between two versions — section-level structural diff

WHEN a user selects two versions (version A and version B, A < B) to compare
THEN the diff service computes section-level changes: sections added, sections removed, sections reordered
AND each change is classified as `added`, `removed`, `reordered`, or `modified`
AND sections present in both versions are matched by `section_type` (stable identifier from EP-04)

---

### SC-072-02: Diff between two versions — text-level content diff

WHEN a section exists in both version A and version B
THEN a line-level or word-level text diff is computed for the section `content` field
AND the diff output uses a standard unified format (added lines marked green, removed lines marked red)
AND unchanged lines are shown with configurable context (default: 3 lines around each change)

---

### SC-072-03: Diff for sections with no content change

WHEN a section exists in both versions and its content is identical
THEN the section is shown as "unchanged" and collapsed by default in the diff view
AND the user can expand collapsed sections

---

### SC-072-04: Diff for title and top-level metadata

WHEN title, description, or state differ between the two versions
THEN those fields are shown in a metadata diff panel separate from section diffs
AND the change is displayed as a simple before/after comparison

---

### SC-072-05: Diff against current version

WHEN a user selects a historical version to compare against the current version
THEN the system automatically uses the latest version as the right side of the diff
AND a "compare to current" shortcut is available from any historical version entry

---

### SC-072-06: Diff output must be human-readable

WHEN the diff is displayed
THEN section names are shown (not raw IDs)
AND character-level changes within a word are highlighted (not just whole-line changes)
AND the diff renders correctly for Markdown content (no double-escaping)

---

### SC-072-07: Diff is computed on demand — not stored

WHEN two versions are selected for comparison
THEN the diff is computed in real time by the diff service
AND no pre-computed diff is persisted
AND computation must complete within 2 seconds for sections up to 100KB of combined content

---

## Data Constraints

| Field | Rule |
|-------|------|
| `version_number` | Auto-incrementing integer, scoped per `work_item_id`, starts at 1 |
| `snapshot` | JSON blob, schema-versioned via `snapshot_schema_version` field |
| `trigger` | Enum: `content_edit`, `state_transition`, `review_outcome`, `breakdown_change`, `manual` |
| `actor_type` | Enum: `human`, `ai_suggestion`, `system` |
| Snapshot immutability | No UPDATE permitted on `snapshot` column after insert |

---

## Out of Scope

> ⚠️ Items below were originally MVP-scoped deferrals. Review each against full-product scope; log outcomes in decisions_pending.md.

- Branch/fork versioning (linear history only)
- User-initiated manual version creation with commit message (trigger = `manual` is system-reserved)
- Three-way merge
- Version tagging / aliases (e.g., "baseline", "approved")
