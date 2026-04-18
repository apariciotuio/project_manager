/**
 * Types for work item detail endpoints (EP-03).
 * Specification, completeness, tasks, reviews, comments, timeline.
 */

// ─── Specification ────────────────────────────────────────────────────────────

/**
 * @deprecated Use `Section` from `@/lib/types/specification` (EP-04 contract).
 * Kept for backward compat with callers predating EP-04.
 */
export interface Section {
  id: string;
  section_type: string;
  content: string | null;
  order: number;
  is_required: boolean;
  last_updated_at: string | null;
  last_updated_by: string | null;
}

/**
 * @deprecated Use `SpecificationApiResponse` from `@/lib/types/specification`.
 */
export interface SpecificationResponse {
  data: {
    sections: Section[];
  };
}

// ─── Completeness ─────────────────────────────────────────────────────────────

/**
 * @deprecated Use `CompletenessLevel` from `@/lib/types/specification`.
 */
export type CompletenessLevel = 'low' | 'medium' | 'high' | 'ready';

/**
 * @deprecated Use `CompletenessDimension` from `@/lib/types/specification`.
 * Note: `score` here is 0.0–1.0 float (per-dimension), matching the EP-04 backend contract.
 */
export interface CompletenessDimension {
  dimension: string;
  score: number;    // 0.0–1.0 float
  weight: number;
  applicable: boolean;
  filled: boolean;
  message: string | null;
}

/**
 * @deprecated Use `CompletenessReport` from `@/lib/types/specification`.
 */
export interface CompletenessData {
  score: number;    // 0–100 int (overall)
  level: CompletenessLevel;
  dimensions: CompletenessDimension[];
  cached?: boolean;
}

/**
 * @deprecated Use `CompletenessApiResponse` from `@/lib/types/specification`.
 */
export interface CompletenessResponse {
  data: CompletenessData;
}

// ─── Gaps ─────────────────────────────────────────────────────────────────────

/**
 * @deprecated Use `GapSeverity` from `@/lib/types/specification`.
 */
export type GapSeverity = 'blocking' | 'warning' | 'info';

/**
 * @deprecated Use `GapItem` from `@/lib/types/specification`.
 */
export interface Gap {
  dimension: string;
  message: string;
  severity: GapSeverity;
}

/**
 * @deprecated Use `GapsApiResponse` from `@/lib/types/specification`.
 */
export interface GapsResponse {
  data: Gap[];
}

// ─── Section Lock ─────────────────────────────────────────────────────────────

export interface SectionLock {
  section_id: string;
  locked_by: string;
  locked_by_name: string | null;
  locked_at: string;
}

export interface LocksResponse {
  data: SectionLock[];
}

// ─── Task Tree ────────────────────────────────────────────────────────────────

export type TaskStatus = 'draft' | 'in_progress' | 'done';

export interface TaskNode {
  id: string;
  title: string;
  status: TaskStatus;
  order: number;
  parent_id: string | null;
  dependencies: string[];
  children: TaskNode[];
}

export interface TaskTreeResponse {
  data: {
    work_item_id: string;
    tree: TaskNode[];
  };
}

export interface CreateTaskRequest {
  title: string;
  parent_id?: string | null;
}

// ─── Reviews ─────────────────────────────────────────────────────────────────

export type ReviewStatus = 'pending' | 'approved' | 'changes_requested' | 'dismissed';

export interface ReviewResponse {
  id: string;
  reviewer_id: string;
  reviewer_name: string | null;
  status: ReviewStatus;
  requested_at: string;
  responses: ReviewResponseItem[];
}

export interface ReviewResponseItem {
  id: string;
  decision: 'approved' | 'changes_requested';
  content: string | null;
  responded_at: string;
}

export interface ReviewsListResponse {
  data: ReviewResponse[];
}

export interface RequestReviewRequest {
  reviewer_id: string;
  note?: string;
}

// ─── Comments ─────────────────────────────────────────────────────────────────

export interface Comment {
  id: string;
  author_id: string;
  author_name: string | null;
  author_avatar_url: string | null;
  body: string;
  parent_id: string | null;
  created_at: string;
  replies?: Comment[];
}

export interface CommentsResponse {
  data: Comment[];
}

export interface AddCommentRequest {
  body: string;
  parent_id?: string | null;
}

// ─── Timeline ─────────────────────────────────────────────────────────────────

/**
 * Event types emitted by the EP-07 backend timeline subscriber.
 * Matches the values written in timeline_subscriber.py and comment_service.py.
 */
export type TimelineEventType =
  | 'state_transition'
  | 'owner_changed'
  | 'section_updated'
  | 'task_added'
  | 'task_completed'
  | 'review_requested'
  | 'review_completed'
  | 'review_submitted'
  | 'comment_added'
  | 'comment_deleted'
  | 'version_created'
  | 'export_triggered'
  | 'tag_added'
  | 'tag_removed';

/** Actor category — mirrors TimelineActorType in the BE domain model. */
export type TimelineActorType = 'human' | 'ai_suggestion' | 'system';

/**
 * Shape returned by GET /api/v1/work-items/:id/timeline for each event.
 * Matches _event_payload() in timeline_controller.py.
 */
export interface TimelineEvent {
  id: string;
  work_item_id: string;
  workspace_id: string;
  event_type: TimelineEventType;
  actor_type: TimelineActorType;
  actor_id: string | null;
  /** Resolved display name (user full_name or "System"). */
  actor_display_name: string | null;
  summary: string;
  payload: Record<string, unknown>;
  occurred_at: string;
  source_id: string | null;
  source_table: string | null;
}

/**
 * Envelope returned by GET /api/v1/work-items/:id/timeline.
 * BE explicitly includes has_more (not inferred from next_cursor).
 */
export interface TimelineResponse {
  data: {
    events: TimelineEvent[];
    has_more: boolean;
    next_cursor: string | null;
  };
}
