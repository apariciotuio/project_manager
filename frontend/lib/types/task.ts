/**
 * EP-14 — Task node types for the task tree feature (EP-05 backend).
 * These types match the `/api/v1/work-items/{id}/tasks` endpoint contract.
 */

export type TaskStatus = 'draft' | 'in_progress' | 'done';

export type TaskEdgeKind = 'blocks' | 'relates_to';

export interface TaskNode {
  id: string;
  work_item_id: string;
  parent_node_id: string | null;
  materialized_path: string;
  title: string;
  status: TaskStatus;
  position: number;
}

export interface TaskEdge {
  id: string;
  from_node_id: string;
  to_node_id: string;
  kind: TaskEdgeKind;
}

export interface TaskTree {
  nodes: TaskNode[];
  edges: TaskEdge[];
}

// ─── API response envelopes ────────────────────────────────────────────────────

export interface TaskTreeApiResponse {
  data: TaskTree;
}

// ─── Request shapes ────────────────────────────────────────────────────────────

export interface CreateTaskRequest {
  title: string;
  parent_node_id?: string | null;
}

export interface RenameTaskRequest {
  title: string;
}

export interface SetTaskStatusRequest {
  status: TaskStatus;
}

export interface ReparentTaskRequest {
  new_parent_id: string | null;
}

export interface CreateTaskDependencyRequest {
  to_node_id: string;
  kind: TaskEdgeKind;
}
