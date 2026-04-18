/**
 * EP-07 — Version, diff, comment, and timeline domain types.
 * Source of truth: tasks/EP-07/tasks-frontend.md API Contract section.
 */

export type VersionTrigger =
  | 'content_edit'
  | 'state_transition'
  | 'review_outcome'
  | 'breakdown_change'
  | 'manual';

export type ActorType = 'human' | 'ai_suggestion' | 'system';

export type AnchorStatus = 'active' | 'orphaned';

export type DiffChangeType =
  | 'modified'
  | 'added'
  | 'removed'
  | 'unchanged'
  | 'reordered';

export interface WorkItemVersion {
  version_number: number;
  trigger: VersionTrigger;
  actor_type: ActorType;
  actor_id: string | null;
  commit_message: string | null;
  archived: boolean;
  created_at: string;
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

export interface VersionsPage {
  data: WorkItemVersion[];
  meta: { has_more: boolean; next_cursor: string | null };
}

// ─── Comments ──────────────────────────────────────────────────────────────

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

export interface CreateCommentRequest {
  body: string;
  parent_comment_id?: string | null;
  anchor_section_id?: string | null;
  anchor_start_offset?: number | null;
  anchor_end_offset?: number | null;
  anchor_snapshot_text?: string | null;
}

// ─── Timeline ──────────────────────────────────────────────────────────────

export type TimelineEventType =
  | 'state_transition'
  | 'comment_added'
  | 'comment_deleted'
  | 'version_created'
  | 'review_submitted'
  | 'export_triggered';

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

export interface TimelinePage {
  data: {
    events: TimelineEvent[];
    has_more: boolean;
    next_cursor: string | null;
  };
}
