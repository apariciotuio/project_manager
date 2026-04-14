# EP-07 — Comments, Versions, Diff & Traceability

## Business Need

Decisions need to be reconstructible. Every meaningful change creates a version, comments can anchor to specific content, diffs show what changed between versions, and a timeline captures the full evolution of an element. This is the institutional memory of the product.

## Objectives

- Support general and anchored comments (linked to specific content sections)
- Version meaningful changes automatically
- Compare any two versions with readable diff
- Provide complete timeline: state changes, reviews, exports, edits, comments
- Distinguish human changes from AI suggestions from system actions

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-070 | Add anchored comments | Must |
| US-071 | Version relevant changes | Must |
| US-072 | Compare versions and proposals with diff | Must |
| US-073 | View complete element timeline | Must |

## Acceptance Criteria

- WHEN a user adds a comment THEN it can optionally anchor to a specific section/content
- WHEN a meaningful change occurs THEN a new version snapshot is created
- WHEN the user selects two versions THEN a readable diff is displayed
- WHEN viewing the timeline THEN all events (state changes, edits, reviews, exports, comments) appear chronologically
- AND the timeline distinguishes actor type: human, AI suggestion, system
- AND anchored comments remain stable even after the target content changes (best-effort anchor stability)

## Technical Notes

- Version snapshots (full or delta-based)
- Comment anchors with stable references (section ID + offset, not line numbers)
- Diff service (structured diff for sections, text diff for content)
- Immutable audit log as timeline source
- Integration with EP-04 (spec versions), EP-06 (review events), EP-11 (export events)

## Dependencies

- EP-01 (work item model)
- EP-04 (specification structure to version)
- EP-05 (breakdown to version)
- EP-06 (review events for timeline)

## Complexity Assessment

**High** — Stable anchors across evolving content, structured diff, and a unified timeline from multiple event sources are technically demanding. Snapshot storage strategy affects performance at scale.

## Risks

- Anchor drift when content is heavily rewritten
- Snapshot storage bloat for large elements
- Diff readability for structural changes (section reorder, merge)
