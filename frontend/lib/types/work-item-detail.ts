/**
 * Types for work item detail endpoints (EP-03).
 * Specification, completeness, tasks, reviews, comments, timeline.
 */

// ─── Specification ────────────────────────────────────────────────────────────

export interface Section {
  id: string;
  section_type: string;
  content: string | null;
  order: number;
  is_required: boolean;
  last_updated_at: string | null;
  last_updated_by: string | null;
}

export interface SpecificationResponse {
  data: {
    sections: Section[];
  };
}

// ─── Completeness ─────────────────────────────────────────────────────────────

export type CompletenessLevel = 'low' | 'medium' | 'high' | 'ready';

export interface CompletenessDimension {
  name: string;
  score: number;
  weight: number;
  label: string;
}

export interface CompletenessData {
  score: number;
  level: CompletenessLevel;
  dimensions: CompletenessDimension[];
}

export interface CompletenessResponse {
  data: CompletenessData;
}

// ─── Gaps ─────────────────────────────────────────────────────────────────────

export type GapSeverity = 'blocking' | 'warning' | 'info';

export interface Gap {
  dimension: string;
  message: string;
  severity: GapSeverity;
}

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
  data: TaskNode[];
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
  replies: Comment[];
}

export interface CommentsResponse {
  data: Comment[];
}

export interface AddCommentRequest {
  body: string;
  parent_id?: string | null;
}

// ─── Timeline ─────────────────────────────────────────────────────────────────

export type TimelineEventType =
  | 'state_transition'
  | 'section_updated'
  | 'task_created'
  | 'task_status_changed'
  | 'review_requested'
  | 'review_responded'
  | 'comment_added'
  | 'owner_changed'
  | 'tag_added'
  | 'tag_removed';

export interface TimelineEvent {
  id: string;
  event_type: TimelineEventType;
  actor_id: string | null;
  actor_name: string | null;
  summary: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
}

export interface TimelineResponse {
  data: TimelineEvent[];
  total: number;
  page: number;
  page_size: number;
}
