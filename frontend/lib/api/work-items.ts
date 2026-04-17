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
  if (filters.type !== undefined) params.set('type', filters.type);
  if (filters.has_override !== undefined)
    params.set('has_override', String(filters.has_override));
  if (filters.owner_id !== undefined) params.set('owner_id', filters.owner_id);
  if (filters.page !== undefined) params.set('page', String(filters.page));
  if (filters.page_size !== undefined) params.set('page_size', String(filters.page_size));
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
  projectId: string,
  filters: WorkItemFilters,
): Promise<PagedWorkItemResponse<WorkItemResponse>> {
  const qs = buildQuery(filters);
  const res = await apiGet<Envelope<PagedWorkItemResponse<WorkItemResponse>>>(
    `/api/v1/projects/${projectId}/work-items${qs}`,
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
