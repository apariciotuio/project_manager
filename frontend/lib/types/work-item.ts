/**
 * EP-01 — Work Item domain types.
 * Mirrors backend enums exactly (lowercase snake_case string unions).
 */

// ─── Enums ────────────────────────────────────────────────────────────────────

export type WorkItemState =
  | 'draft'
  | 'in_clarification'
  | 'in_review'
  | 'changes_requested'
  | 'partially_validated'
  | 'ready'
  | 'exported';

export type WorkItemType =
  | 'idea'
  | 'bug'
  | 'enhancement'
  | 'task'
  | 'initiative'
  | 'spike'
  | 'business_change'
  | 'requirement'
  | 'milestone'
  | 'story';

export type DerivedState = 'in_progress' | 'blocked' | 'ready';

export type Priority = 'low' | 'medium' | 'high' | 'critical';

// ─── Core response shape ──────────────────────────────────────────────────────

export interface WorkItemResponse {
  id: string;
  title: string;
  type: WorkItemType;
  state: WorkItemState;
  derived_state: DerivedState | null;
  owner_id: string;
  creator_id: string;
  project_id: string | null;
  description: string | null;
  priority: Priority | null;
  due_date: string | null; // ISO 8601 date
  tags: string[];
  completeness_score: number; // 0–100
  has_override: boolean;
  override_justification: string | null;
  owner_suspended_flag: boolean;
  parent_work_item_id: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

// ─── Tag types ────────────────────────────────────────────────────────────────

export interface WorkItemTag {
  id: string;
  name: string;
  color: string;
  is_archived: boolean;
}

// ─── Paged response ───────────────────────────────────────────────────────────

export interface PagedWorkItemResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Request types ────────────────────────────────────────────────────────────

export interface WorkItemCreateRequest {
  title: string;
  type: WorkItemType;
  project_id?: string;
  parent_work_item_id?: string;
  description?: string;
  priority?: Priority;
  due_date?: string;
  tags?: string[];
  owner_id?: string;
  template_id?: string;
}

export interface WorkItemUpdateRequest {
  title?: string;
  description?: string;
  priority?: Priority;
  due_date?: string;
  tags?: string[];
}

export interface TransitionRequest {
  target_state: WorkItemState;
  reason?: string;
}

export interface ForceReadyRequest {
  justification: string;
  confirmed: true;
}

export interface ReassignOwnerRequest {
  new_owner_id: string;
  reason?: string;
}

// ─── Audit trail types ────────────────────────────────────────────────────────

export interface StateTransitionRecord {
  id: string;
  work_item_id: string;
  from_state: WorkItemState;
  to_state: WorkItemState;
  actor_id: string | null;
  triggered_at: string;
  transition_reason: string | null;
  is_override: boolean;
  override_justification: string | null;
}

export interface OwnershipRecord {
  id: string;
  work_item_id: string;
  previous_owner_id: string;
  new_owner_id: string;
  changed_by: string;
  changed_at: string;
  reason: string | null;
}

// ─── Filter types ─────────────────────────────────────────────────────────────

export interface WorkItemFilters {
  state?: WorkItemState;
  type?: WorkItemType;
  has_override?: boolean;
  owner_id?: string;
  page?: number;
  page_size?: number;
}
