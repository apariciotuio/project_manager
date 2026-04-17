# EP-07 Frontend Tasks — Comments, Versioning, Diff & Timeline

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `DiffHunk` (added/removed/context), `VersionChip`, `RelativeTime` (wraps `<time datetime>`), `SeverityBadge` warning for orphaned-anchor chip, `HumanError`, semantic tokens, i18n `i18n/es/comment.ts` + `i18n/es/version.ts`. Text-range anchoring, timeline filters, comment thread UI remain feature-specific. See `tasks/extensions.md#EP-19`.

Tech stack: Next.js 14+ App Router, TypeScript strict, Tailwind CSS

Blocked by: EP-07 backend Phase 4 complete. EP-19 catalog available.

---

## API Client Contract

```typescript
// src/lib/api/versions.ts

export type VersionTrigger = 'content_edit' | 'state_transition' | 'review_outcome' | 'breakdown_change' | 'manual';
export type ActorType = 'human' | 'ai_suggestion' | 'system';
export type AnchorStatus = 'active' | 'orphaned';
export type TimelineEventType = 'state_transition' | 'comment_added' | 'comment_deleted' | 'version_created' | 'review_submitted' | 'export_triggered';
export type DiffChangeType = 'modified' | 'added' | 'removed' | 'unchanged' | 'reordered';

export interface WorkItemVersion {
  version_number: number;
  trigger: VersionTrigger;
  actor_type: ActorType;
  actor_id: string | null;
  commit_message: string | null;
  archived: boolean;
  created_at: string;
}

export interface VersionSnapshot {
  version_number: number;
  snapshot: {
    schema_version: number;
    work_item: { id: string; title: string; description: string; state: string; owner_id: string };
    sections: Array<{ section_id: string; section_type: string; content: string; order: number }>;
    task_node_ids: string[];
  };
}

export interface DiffHunk {
  type: 'context' | 'added' | 'removed';
  lines: string[];
}

export interface SectionDiff {
  section_type: string;
  change_type: DiffChangeType;
  hunks: DiffHunk[];
}

export interface VersionDiff {
  from_version: number;
  to_version: number;
  metadata_diff: Record<string, { before: string; after: string } | null>;
  sections: SectionDiff[];
}

export interface Comment {
  id: string;
  work_item_id: string;
  parent_comment_id: string | null;
  body: string;
  actor_type: ActorType;
  actor_id: string | null;
  anchor_section_id: string | null;
  anchor_start_offset: number | null;
  anchor_end_offset: number | null;
  anchor_snapshot_text: string | null;
  anchor_status: AnchorStatus;
  is_edited: boolean;
  deleted_at: string | null;
  created_at: string;
  replies: Comment[];
}

export interface TimelineEvent {
  id: string;
  event_type: TimelineEventType;
  actor_type: ActorType;
  actor_id: string | null;
  actor_display_name: string;
  summary: string;
  payload: Record<string, unknown>;
  occurred_at: string;
  source_id: string | null;
  source_table: string | null;
}

// listVersions: GET /api/v1/work-items/:id/versions
// getVersionSnapshot: GET /api/v1/work-items/:id/versions/:version_number
// getVersionDiff: GET /api/v1/work-items/:id/versions/:version_number/diff
// getArbitraryDiff: GET /api/v1/work-items/:id/versions/diff?from=N&to=M
// listComments: GET /api/v1/work-items/:id/comments
// createComment: POST /api/v1/work-items/:id/comments
// updateComment: PATCH /api/v1/work-items/:id/comments/:comment_id
// deleteComment: DELETE /api/v1/work-items/:id/comments/:comment_id
// createReply: POST /api/v1/work-items/:id/comments/:comment_id/replies
// listSectionComments: GET /api/v1/work-items/:id/sections/:section_id/comments
// listTimeline: GET /api/v1/work-items/:id/timeline
```

---

## Group 1 — API Client Layer

### Acceptance Criteria

WHEN `getArbitraryDiff(workItemId, from, to)` is called with `from > to`
THEN the function throws `{ code: 'INVALID_DIFF_RANGE' }` without a network call (client-side guard)
AND if the server returns 400 for any other reason it is propagated as-is

WHEN `createComment` is called with `anchor_start_offset > anchor_end_offset`
THEN the function throws `{ code: 'INVALID_ANCHOR_RANGE' }` (client-side guard before network call)

WHEN `listVersions` cursor is passed
THEN it is sent as `?after=<cursor>` query param; `has_more` and `next_cursor` parsed from `meta`

Blocked by: EP-07 backend Phase 4 complete

- [x] 1.1 [RED] Test `listVersions`: cursor pagination, `has_more` field (2026-04-17 — in use-versions.test.ts)
- [ ] 1.2 [RED] Test `getVersionDiff` and `getArbitraryDiff`: map to `VersionDiff` type; `from > to` → 400 error
- [ ] 1.3 [RED] Test `createComment`: general and anchored; `anchor_start_offset > anchor_end_offset` → 422 error
- [ ] 1.4 [RED] Test `listTimeline`: filter params serialized correctly; cursor pagination
- [x] 1.5 [GREEN] Implement `frontend/lib/api/versions.ts` — listVersions, getVersion, diffVsPrevious, diffVersions (2026-04-17)

---

## Group 2 — Hooks

### Acceptance Criteria

WHEN `useVersionDiff(workItemId, from, to)` is called with `from === to`
THEN the hook returns `{ diff: null, isLoading: false, error: null }` without fetching

WHEN `useVersionDiff` is called with valid `from < to`
THEN `diff` is the `VersionDiff` object with `sections` and `metadata_diff`

WHEN `useComments.addComment` is called and optimistically appended
THEN on server error, the optimistic item is removed and `error` is set

WHEN `useTimeline` filters change
THEN cursor is reset to page 1; previous result is not blended with new

Blocked by: Group 1 complete

- [x] 2.1 [RED] Test `useVersions(workItemId)`: fetches paginated list, `loadMore` fetches next page (2026-04-17 — 4 tests in __tests__/hooks/work-item/use-versions.test.ts)
- [x] 2.2 [GREEN] Implement `frontend/hooks/work-item/use-versions.ts` — useVersions + useDiffVsPrevious (2026-04-17)
- [x] 2.3 [RED] Test `useDiffVsPrevious(workItemId, versionNumber)`: diff loaded, null when versionNumber null (2026-04-17 — covered in version-history-panel.test.tsx)
- [x] 2.4 [GREEN] Implement `useDiffVsPrevious` (exported from use-versions.ts) (2026-04-17)
- [ ] 2.5 [RED] Test `useComments(workItemId)`: fetches list; `addComment` mutation appends optimistically; `deleteComment` removes optimistically
- [ ] 2.6 [GREEN] Implement `src/hooks/useComments.ts`
- [ ] 2.7 [RED] Test `useSectionComments(workItemId, sectionId)`: fetches anchored comments for section
- [ ] 2.8 [GREEN] Implement `src/hooks/useSectionComments.ts`
- [ ] 2.9 [RED] Test `useTimeline(workItemId, filters)`: fetches with filters; cursor pagination; filter changes reset to page 1
- [ ] 2.10 [GREEN] Implement `src/hooks/useTimeline.ts`

---

## Group 3 — Version History Panel

### Acceptance Criteria

**VersionDiffViewer**

WHEN `change_type = added`
THEN hunk lines render with green background

WHEN `change_type = removed`
THEN hunk lines render with red background

WHEN `change_type = unchanged`
THEN section is collapsed by default; "Show unchanged" toggle expands it

WHEN `change_type = reordered`
THEN "Reordered" badge rendered; no diff hunks shown (no line-level diff needed for reorder)

WHEN `from === to`
THEN "No changes" message renders; no diff request made

WHEN diff fetch fails
THEN retry button rendered with error message; skeleton is cleared

**VersionCompareSelector**

WHEN user sets `from > to` via dropdowns
THEN the component swaps them automatically OR disables the submit; it must not allow a backwards diff to be requested

**VersionList**

WHEN a version is selected
THEN it is highlighted; `onSelectVersion(vn)` is called with the version number

Blocked by: Group 2 complete

### VersionList component

Props:
```typescript
interface VersionListProps {
  workItemId: string;
  selectedVersion: number | null;
  onSelectVersion: (vn: number) => void;
}
```

- [x] 3.1 [RED] Test: renders list of versions reverse-chron; trigger badge; commit_message; created_at; loading skeleton; empty/error states; load more (2026-04-17 — 4 tests in __tests__/components/work-item/version-history-panel.test.tsx)
- [x] 3.2 [GREEN] Implement `frontend/components/work-item/version-history-panel.tsx` (2026-04-17)

### VersionDiffViewer component

Props:
```typescript
interface VersionDiffViewerProps {
  workItemId: string;
  fromVersion: number;
  toVersion: number;
}
```

- [x] 3.3 [RED] Test: diff dialog opens on button click; renders changed sections (via MSW); error/empty states (2026-04-17 — in version-history-panel.test.tsx)
- [x] 3.4 [GREEN] Implement `frontend/components/work-item/diff-viewer.tsx` — renders sections_changed/added/removed with colored lines (2026-04-17)
- [ ] 3.5 [RED] Test: `change_type=reordered` renders "Reordered" badge without diff hunks
- [ ] 3.6 [GREEN] Handle `reordered` and `removed` section display in `VersionDiffViewer`

### VersionCompareSelector

Props:
```typescript
interface VersionCompareSelectorProps {
  workItemId: string;
  versions: WorkItemVersion[];
  fromVersion: number;
  toVersion: number;
  onChange: (from: number, to: number) => void;
}
```

- [ ] 3.7 [RED] Test: two dropdowns for from/to; `from` cannot be > `to`; swap button swaps values
- [ ] 3.8 [GREEN] Implement `src/components/versions/VersionCompareSelector.tsx`

### VersionHistoryPage

- [x] 3.9 [GREEN] Wire "Versiones" tab into `frontend/app/workspace/[slug]/items/[id]/page.tsx` (canEdit guard) — renders VersionHistoryPanel (2026-04-17)
- [ ] 3.10 [DEFERRED] Dedicated `/history` page with sidebar layout — deferred, tab is sufficient for MVP

---

## Group 4 — Comments

### Acceptance Criteria

**CommentThread**

WHEN `comment.actor_type = 'ai_suggestion'`
THEN edit button is hidden; delete button may remain for authorized humans

WHEN `comment.deleted_at` is set and `comment.replies` is non-empty
THEN body renders as "[deleted]" in greyed italic; replies remain fully visible

WHEN `comment.anchor_status = 'orphaned'`
THEN orange/yellow warning chip "Anchor text no longer found" renders adjacent to comment

WHEN own comment with `actor_type = 'human'`
THEN edit and delete buttons visible

**CommentInput**

WHEN body is empty
THEN submit button is disabled; Cmd/Ctrl+Enter does nothing

WHEN anchor data is provided (section_id, start, end, snapshot_text)
THEN it is passed to `onSubmit` as the second argument

WHEN an image is pasted into the comment editor
THEN the EP-16 upload flow starts immediately, a `![Uploading…]()` placeholder is inserted at cursor
AND on upload success the placeholder is replaced with `![filename](attachment_id)` markdown syntax
AND on upload failure the placeholder is removed and an inline error is shown

WHEN an image is dragged and dropped onto the comment editor
THEN the same upload flow triggers as paste (identical behavior)

**AnchoredCommentMarker**

WHEN an anchored comment's `anchor_status = 'orphaned'`
THEN marker renders in a different visual style (e.g., dashed underline vs solid) to distinguish orphaned from active

Blocked by: Group 2 complete

### CommentThread component

Props:
```typescript
interface CommentThreadProps {
  comment: Comment;
  currentUserId: string;
  onEdit: (id: string, body: string) => void;
  onDelete: (id: string) => void;
  onReply: (parentId: string, body: string) => void;
}
```

- [ ] 4.1 [RED] Test: renders body; edit button only for own non-AI comments; delete button for own; deleted comment shows `[deleted]` with greyed styling; reply count badge; orphaned anchor shows warning chip "Anchor text no longer found"
- [ ] 4.2 [GREEN] Implement `src/components/comments/CommentThread.tsx`

### CommentInput component

Props:
```typescript
interface CommentInputProps {
  onSubmit: (body: string, anchor?: { section_id: string; start: number; end: number; snapshot_text: string }) => void;
  placeholder?: string;
  initialBody?: string;
}
```

- [ ] 4.3 [RED] Test: textarea; submit on Cmd/Ctrl+Enter or button; empty body disabled; anchor data passed when provided
- [ ] 4.3a [RED] Test: paste image from clipboard → upload starts via EP-16 upload flow, placeholder `![Uploading…]()` inserted at cursor, replaced with `![filename](attachment_id)` on upload success; drag-drop image onto editor same flow; failed upload shows inline error and removes placeholder
- [ ] 4.4 [GREEN] Implement `src/components/comments/CommentInput.tsx` — support paste-from-clipboard (`paste` event on `ClipboardData.files`) and drag-drop (`drop` event) for images; each image triggers EP-16 upload flow (`POST /api/v1/work-items/:id/attachments` multipart → authenticated streaming, no presigned URL — decision #29); markdown image syntax `![filename](attachment_id)` inserted at cursor position on success

### CommentFeed component

Props:
```typescript
interface CommentFeedProps {
  workItemId: string;
  currentUserId: string;
}
```

- [ ] 4.5 [RED] Test: renders all `CommentThread` components; `CommentInput` at top; loading skeleton; empty state "No comments yet"; cursor pagination "Load more" button
- [ ] 4.6 [GREEN] Implement `src/components/comments/CommentFeed.tsx`

### Anchored inline comments (section view integration)

- [ ] 4.7 [RED] Test: section editor renders comment count badge on selected text ranges; clicking range opens comment popover showing anchored comments + `CommentInput`; orphaned anchors render in a different style
- [ ] 4.8 [GREEN] Implement `src/components/comments/AnchoredCommentMarker.tsx` — renders highlight over text range with comment count
- [ ] 4.9 [GREEN] Implement `src/components/comments/AnchoredCommentPopover.tsx` — shows anchored comments and input for a specific anchor range
- [ ] 4.10 [GREEN] Integrate `AnchoredCommentMarker` into the spec section editor (EP-04 component)

---

## Group 5 — Timeline

### Acceptance Criteria

**TimelineEventItem**

WHEN `event.event_type = 'state_transition'`
THEN renders `payload.from_state → payload.to_state` (e.g., "Draft → In Review")

WHEN `event.event_type = 'comment_added'`
THEN renders a link that scrolls to the comment in the comments tab (uses `payload.comment_id`)

WHEN `event.event_type = 'review_submitted'`
THEN decision chip (Approved/Rejected/Changes Requested) renders; links to review panel

WHEN `event.actor_type = 'ai_suggestion'`
THEN robot icon renders instead of user avatar

**TimelineFeed**

WHEN `useTimeline` is loading
THEN skeleton renders; previous results not shown (no stale-data flash)

WHEN timeline is empty after filtering
THEN "No events match these filters" message shown (distinct from true-empty "No activity yet")

WHEN filter changes
THEN component scrolls to top; old page cursor discarded

Blocked by: Group 2 complete

### TimelineEventItem component

Props:
```typescript
interface TimelineEventItemProps {
  event: TimelineEvent;
}
```

- [ ] 5.1 [RED] Test: renders icon by `event_type`; `actor_display_name` and relative timestamp; `summary` text; `state_transition` shows from→to state; `comment_added` links to comment; `review_submitted` shows decision chip; `ai_suggestion` actor renders robot icon
- [ ] 5.2 [GREEN] Implement `src/components/timeline/TimelineEventItem.tsx`

### TimelineFilters component

Props:
```typescript
interface TimelineFiltersProps {
  eventTypes: TimelineEventType[];
  actorTypes: ActorType[];
  dateRange: { from: string | null; to: string | null };
  onChange: (filters: TimelineFilters) => void;
}
```

- [ ] 5.3 [RED] Test: event type multi-select checkboxes; actor type filter; date range pickers; "Reset filters" clears all
- [ ] 5.4 [GREEN] Implement `src/components/timeline/TimelineFilters.tsx`

### TimelineFeed component

Props:
```typescript
interface TimelineFeedProps {
  workItemId: string;
}
```

- [ ] 5.5 [RED] Test: renders all `TimelineEventItem` components; loading skeleton; empty filtered state "No events match these filters" vs true empty "No activity yet"; cursor pagination; filter changes reset to page 1
- [ ] 5.6 [GREEN] Implement `src/components/timeline/TimelineFeed.tsx`

### Timeline page / tab

- [ ] 5.7 [GREEN] Add Timeline tab to work item detail page at `src/app/(workspace)/items/[id]/timeline/page.tsx`

---

## Group 6 — Page Integration

Blocked by: Groups 3–5 complete

- [ ] 6.1 [RED] Test: work item detail page has "History", "Comments", and "Timeline" tabs
- [ ] 6.2 [GREEN] Add tabs to existing work item detail page layout
- [ ] 6.3 [RED] Test: comments tab comment count badge updates on new comment without page reload (optimistic update from `useComments`)
- [ ] 6.4 [RED] Test: version history tab shows diff between consecutive versions on initial load (latest vs previous)
- [ ] 6.5 [GREEN] Wire initial diff selection in history page

---

## Group 7 — States & Responsive

- [ ] 7.1 [RED] Test: diff viewer loading skeleton renders section placeholders
- [ ] 7.2 [GREEN] Implement `VersionDiffViewerSkeleton`
- [ ] 7.3 [RED] Test: comment feed loading skeleton renders 3 comment placeholders
- [ ] 7.4 [GREEN] Implement `CommentFeedSkeleton`
- [ ] 7.5 Mobile: version history full-screen — version list collapses to dropdown; diff viewer scrollable; anchored comment popover renders as bottom sheet
- [ ] 7.6 [RED] Test: error state on diff fetch shows retry button with error message
- [ ] 7.7 [GREEN] Implement error state in `VersionDiffViewer`
