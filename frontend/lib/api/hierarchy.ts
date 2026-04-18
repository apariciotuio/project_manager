/**
 * EP-14 — Hierarchy API client.
 * Endpoints:
 *   GET /api/v1/projects/:id/hierarchy
 *   GET /api/v1/work-items/:id/children
 *   GET /api/v1/work-items/:id/ancestors
 *   GET /api/v1/work-items/:id/rollup
 */
import { apiGet } from '../api-client';
import type {
  HierarchyPage,
  ChildrenPage,
  AncestorChain,
  RollupResult,
  PaginationParams,
} from '../types/hierarchy';

interface Envelope<T> {
  data: T;
}

export async function getProjectHierarchy(
  projectId: string,
  cursor?: string,
): Promise<HierarchyPage> {
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);
  const qs = params.toString();
  const url = `/api/v1/projects/${projectId}/hierarchy${qs ? `?${qs}` : ''}`;
  const res = await apiGet<Envelope<HierarchyPage>>(url);
  return res.data;
}

export async function getWorkItemChildren(
  workItemId: string,
  pagination: PaginationParams = {},
): Promise<ChildrenPage> {
  const params = new URLSearchParams();
  if (pagination.cursor) params.set('cursor', pagination.cursor);
  if (pagination.limit !== undefined) params.set('limit', String(pagination.limit));
  const qs = params.toString();
  const url = `/api/v1/work-items/${workItemId}/children${qs ? `?${qs}` : ''}`;
  const res = await apiGet<Envelope<ChildrenPage>>(url);
  return res.data;
}

export async function getWorkItemAncestors(workItemId: string): Promise<AncestorChain> {
  const res = await apiGet<Envelope<AncestorChain>>(
    `/api/v1/work-items/${workItemId}/ancestors`,
  );
  return res.data;
}

export async function getWorkItemRollup(workItemId: string): Promise<RollupResult> {
  const res = await apiGet<Envelope<RollupResult>>(
    `/api/v1/work-items/${workItemId}/rollup`,
  );
  return res.data;
}
