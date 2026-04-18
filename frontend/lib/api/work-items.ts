/**
 * EP-01 — Work Item API client functions.
 * All functions throw ApiError on 4xx/5xx (never resolve to null).
 * Response envelope: { data: T, message?: string }
 */
import { apiGet, apiPost, apiPatch, apiDelete } from '../api-client';
import type {
  WorkItemResponse,
  WorkItemCreateRequest,
  WorkItemUpdateRequest,
  TransitionRequest,
  ForceReadyRequest,
  ReassignOwnerRequest,
  PagedWorkItemResponse,
  StateTransitionRecord,
  OwnershipRecord,
  WorkItemFilters,
} from '../types/work-item';

// Backend wraps successful responses in { data: T }
interface Envelope<T> {
  data: T;
}

function buildQuery(filters: WorkItemFilters): string {
  const params = new URLSearchParams();
  if (filters.state !== undefined) params.set('state', filters.state);
  // multi-value state (EP-09 advanced filters)
  if (filters.states !== undefined) {
    for (const s of filters.states) params.append('state', s);
  }
  if (filters.type !== undefined) params.set('type', filters.type);
  if (filters.types !== undefined) {
    for (const t of filters.types) params.append('type', t);
  }
  if (filters.has_override !== undefined)
    params.set('has_override', String(filters.has_override));
  if (filters.owner_id !== undefined) params.set('owner_id', filters.owner_id);
  if (filters.page !== undefined) params.set('page', String(filters.page));
  if (filters.page_size !== undefined) params.set('page_size', String(filters.page_size));
  // EP-09 extended params
  if (filters.priority !== undefined) params.set('priority', filters.priority);
  if (filters.tag_ids !== undefined) {
    for (const id of filters.tag_ids) params.append('tag_id', id);
  }
  if (filters.completeness_min !== undefined) params.set('completeness_min', String(filters.completeness_min));
  if (filters.completeness_max !== undefined) params.set('completeness_max', String(filters.completeness_max));
  if (filters.updated_after !== undefined) params.set('updated_after', filters.updated_after);
  if (filters.updated_before !== undefined) params.set('updated_before', filters.updated_before);
  if (filters.creator_id !== undefined) params.set('creator_id', filters.creator_id);
  if (filters.project_id !== undefined) params.set('project_id', filters.project_id);
  if (filters.parent_work_item_id !== undefined) params.set('parent_work_item_id', filters.parent_work_item_id);
  if (filters.ancestor_id !== undefined) params.set('ancestor_id', filters.ancestor_id);
  if (filters.q !== undefined && filters.q !== '') params.set('q', filters.q);
  if (filters.sort !== undefined) params.set('sort', filters.sort);
  if (filters.cursor !== undefined) params.set('cursor', filters.cursor);
  if (filters.limit !== undefined) params.set('limit', String(filters.limit));
  if (filters.use_puppet !== undefined) params.set('use_puppet', String(filters.use_puppet));
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function createWorkItem(
  data: WorkItemCreateRequest,
): Promise<WorkItemResponse> {
  const res = await apiPost<Envelope<WorkItemResponse>>('/api/v1/work-items', data);
  return res.data;
}

export async function getWorkItem(id: string): Promise<WorkItemResponse> {
  const res = await apiGet<Envelope<WorkItemResponse>>(`/api/v1/work-items/${id}`);
  return res.data;
}

export async function listWorkItems(
  _projectId: string | null,
  filters: WorkItemFilters,
): Promise<PagedWorkItemResponse<WorkItemResponse>> {
  const qs = buildQuery(filters);
  // Use workspace-scoped endpoint (no project_id needed — RLS scopes by workspace)
  const res = await apiGet<Envelope<PagedWorkItemResponse<WorkItemResponse>>>(
    `/api/v1/work-items${qs}`,
  );
  return res.data;
}

export async function updateWorkItem(
  id: string,
  data: WorkItemUpdateRequest,
): Promise<WorkItemResponse> {
  const res = await apiPatch<Envelope<WorkItemResponse>>(`/api/v1/work-items/${id}`, data);
  return res.data;
}

export async function deleteWorkItem(id: string): Promise<void> {
  await apiDelete<void>(`/api/v1/work-items/${id}`);
}

export async function transitionState(
  id: string,
  data: TransitionRequest,
): Promise<WorkItemResponse> {
  const res = await apiPost<Envelope<WorkItemResponse>>(
    `/api/v1/work-items/${id}/transitions`,
    data,
  );
  return res.data;
}

export async function forceReady(
  id: string,
  data: ForceReadyRequest,
): Promise<WorkItemResponse> {
  const res = await apiPost<Envelope<WorkItemResponse>>(
    `/api/v1/work-items/${id}/force-ready`,
    data,
  );
  return res.data;
}

export async function reassignOwner(
  id: string,
  data: ReassignOwnerRequest,
): Promise<WorkItemResponse> {
  const res = await apiPatch<Envelope<WorkItemResponse>>(
    `/api/v1/work-items/${id}/owner`,
    data,
  );
  return res.data;
}

export async function getTransitions(id: string): Promise<StateTransitionRecord[]> {
  const res = await apiGet<Envelope<StateTransitionRecord[]>>(
    `/api/v1/work-items/${id}/transitions`,
  );
  return res.data;
}

export async function getOwnershipHistory(id: string): Promise<OwnershipRecord[]> {
  const res = await apiGet<Envelope<OwnershipRecord[]>>(
    `/api/v1/work-items/${id}/ownership-history`,
  );
  return res.data;
}

// EP-11 — Jira export
export interface JiraExportJobResponse {
  job_id: string;
  status: string;
}

export async function exportToJira(id: string): Promise<JiraExportJobResponse> {
  const res = await apiPost<Envelope<JiraExportJobResponse>>(
    `/api/v1/work-items/${id}/export/jira`,
    {},
  );
  return res.data;
}
