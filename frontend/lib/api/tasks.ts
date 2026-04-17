/**
 * EP-14 — Task API client functions (EP-05 backend endpoints).
 * All functions throw ApiError on 4xx/5xx.
 */
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api-client';
import type {
  TaskTree,
  TaskNode,
  TaskEdge,
  CreateTaskRequest,
  RenameTaskRequest,
  SetTaskStatusRequest,
  ReparentTaskRequest,
  CreateTaskDependencyRequest,
} from '@/lib/types/task';

interface Envelope<T> {
  data: T;
}

/**
 * GET /api/v1/work-items/{workItemId}/tasks
 * Returns the flat node list + edges for the work item's task tree.
 */
export async function getTaskTree(workItemId: string): Promise<TaskTree> {
  const res = await apiGet<Envelope<TaskTree>>(
    `/api/v1/work-items/${workItemId}/tasks`,
  );
  return res.data;
}

/**
 * POST /api/v1/work-items/{workItemId}/tasks
 * Creates a new task node. Returns the created node.
 */
export async function createTask(
  workItemId: string,
  req: CreateTaskRequest,
): Promise<TaskNode> {
  const res = await apiPost<Envelope<TaskNode>>(
    `/api/v1/work-items/${workItemId}/tasks`,
    req,
  );
  return res.data;
}

/**
 * PATCH /api/v1/tasks/{taskId}
 * Renames a task node.
 */
export async function renameTask(
  taskId: string,
  req: RenameTaskRequest,
): Promise<TaskNode> {
  const res = await apiPatch<Envelope<TaskNode>>(`/api/v1/tasks/${taskId}`, req);
  return res.data;
}

/**
 * PATCH /api/v1/tasks/{taskId}/status
 * Transitions a task node status.
 */
export async function setTaskStatus(
  taskId: string,
  req: SetTaskStatusRequest,
): Promise<TaskNode> {
  const res = await apiPatch<Envelope<TaskNode>>(
    `/api/v1/tasks/${taskId}/status`,
    req,
  );
  return res.data;
}

/**
 * PATCH /api/v1/tasks/{taskId}/parent
 * Reparents a task node.
 */
export async function reparentTask(
  taskId: string,
  req: ReparentTaskRequest,
): Promise<TaskNode> {
  const res = await apiPatch<Envelope<TaskNode>>(
    `/api/v1/tasks/${taskId}/parent`,
    req,
  );
  return res.data;
}

/**
 * POST /api/v1/tasks/{taskId}/dependencies
 * Adds a dependency edge from taskId → to_node_id.
 */
export async function createTaskDependency(
  taskId: string,
  req: CreateTaskDependencyRequest,
): Promise<TaskEdge> {
  const res = await apiPost<Envelope<TaskEdge>>(
    `/api/v1/tasks/${taskId}/dependencies`,
    req,
  );
  return res.data;
}

/**
 * DELETE /api/v1/tasks/{taskId}/dependencies/{edgeId}
 * Removes a dependency edge.
 */
export async function deleteTaskDependency(
  taskId: string,
  edgeId: string,
): Promise<void> {
  await apiDelete<void>(`/api/v1/tasks/${taskId}/dependencies/${edgeId}`);
}
