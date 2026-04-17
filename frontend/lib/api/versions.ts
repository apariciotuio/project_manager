/**
 * EP-07 FE — Version API client.
 * Endpoints:
 *   GET /api/v1/work-items/{id}/versions          — list (cursor-paginated)
 *   GET /api/v1/work-items/{id}/versions/{n}      — get snapshot
 *   GET /api/v1/work-items/{id}/versions/diff     — arbitrary diff (?from=N&to=M)
 *   GET /api/v1/work-items/{id}/versions/{n}/diff — diff vs previous
 */

import { apiGet } from '../api-client';

export interface WorkItemVersionSummary {
  id: string;
  work_item_id: string;
  version_number: number;
  trigger: string;
  actor_type: string;
  actor_id: string | null;
  commit_message: string | null;
  archived: boolean;
  created_at: string;
}

export interface WorkItemVersionSnapshot extends WorkItemVersionSummary {
  snapshot: Record<string, unknown>;
}

export interface VersionsPage {
  data: WorkItemVersionSummary[];
  meta: { has_more: boolean; next_cursor: string | null };
}

export interface VersionDiff {
  from_version: number | null;
  to_version: number;
  sections_added: unknown[];
  sections_removed: unknown[];
  sections_changed: unknown[];
  work_item_changed: boolean;
  task_nodes_changed: boolean;
}

interface Envelope<T> {
  data: T;
}

export async function listVersions(
  workItemId: string,
  cursor?: number,
  limit = 20,
): Promise<VersionsPage> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor !== undefined) params.set('before', String(cursor));
  return apiGet<VersionsPage>(`/api/v1/work-items/${workItemId}/versions?${params.toString()}`);
}

export async function getVersion(
  workItemId: string,
  versionNumber: number,
): Promise<WorkItemVersionSnapshot> {
  const res = await apiGet<Envelope<WorkItemVersionSnapshot>>(
    `/api/v1/work-items/${workItemId}/versions/${versionNumber}`,
  );
  return res.data;
}

export async function diffVersions(
  workItemId: string,
  fromVersion: number,
  toVersion: number,
): Promise<VersionDiff> {
  const params = new URLSearchParams({ from: String(fromVersion), to: String(toVersion) });
  const res = await apiGet<Envelope<VersionDiff>>(
    `/api/v1/work-items/${workItemId}/versions/diff?${params.toString()}`,
  );
  return res.data;
}

export async function diffVsPrevious(
  workItemId: string,
  versionNumber: number,
): Promise<VersionDiff> {
  const res = await apiGet<Envelope<VersionDiff>>(
    `/api/v1/work-items/${workItemId}/versions/${versionNumber}/diff`,
  );
  return res.data;
}
