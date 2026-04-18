/**
 * EP-07 FE — Version API client.
 * Endpoints:
 *   GET /api/v1/work-items/{id}/versions          — list (cursor-paginated)
 *   GET /api/v1/work-items/{id}/versions/{n}      — get snapshot
 *   GET /api/v1/work-items/{id}/versions/diff     — arbitrary diff (?from=N&to=M)
 *   GET /api/v1/work-items/{id}/versions/{n}/diff — diff vs previous
 *   POST /api/v1/work-items/{id}/comments         — create comment
 *   GET /api/v1/work-items/{id}/timeline          — paginated timeline
 */

import { apiGet, apiPost } from '../api-client';
import type { VersionDiff, VersionsPage, Comment, CreateCommentRequest, TimelinePage, TimelineEventType, ActorType } from '../types/versions';

export type {
  VersionDiff,
  VersionsPage,
  SectionDiff,
  DiffHunk,
  DiffChangeType,
  WorkItemVersion,
  Comment,
  CreateCommentRequest,
  TimelinePage,
  TimelineEvent,
  TimelineEventType,
} from '../types/versions';

// ─── legacy shapes kept for backward compat ──────────────────────────────────

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

interface Envelope<T> {
  data: T;
}

// ─── listVersions ─────────────────────────────────────────────────────────────

export async function listVersions(
  workItemId: string,
  cursor?: number,
  limit = 20,
): Promise<VersionsPage> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor !== undefined) params.set('before', String(cursor));
  return apiGet<VersionsPage>(`/api/v1/work-items/${workItemId}/versions?${params.toString()}`);
}

// ─── getVersion ───────────────────────────────────────────────────────────────

export async function getVersion(
  workItemId: string,
  versionNumber: number,
): Promise<WorkItemVersionSnapshot> {
  const res = await apiGet<Envelope<WorkItemVersionSnapshot>>(
    `/api/v1/work-items/${workItemId}/versions/${versionNumber}`,
  );
  return res.data;
}

// ─── getVersionDiff ───────────────────────────────────────────────────────────

export async function getVersionDiff(
  workItemId: string,
  versionNumber: number,
): Promise<VersionDiff> {
  const res = await apiGet<Envelope<VersionDiff>>(
    `/api/v1/work-items/${workItemId}/versions/${versionNumber}/diff`,
  );
  return res.data;
}

// ─── getArbitraryDiff ─────────────────────────────────────────────────────────

export async function getArbitraryDiff(
  workItemId: string,
  from: number,
  to: number,
): Promise<VersionDiff> {
  if (from >= to) {
    return Promise.reject({ code: 'INVALID_DIFF_RANGE' });
  }
  const params = new URLSearchParams({ from: String(from), to: String(to) });
  const res = await apiGet<Envelope<VersionDiff>>(
    `/api/v1/work-items/${workItemId}/versions/diff?${params.toString()}`,
  );
  return res.data;
}

// ─── diffVersions (legacy alias) ─────────────────────────────────────────────

/** @deprecated use getArbitraryDiff */
export async function diffVersions(
  workItemId: string,
  fromVersion: number,
  toVersion: number,
): Promise<VersionDiff> {
  return getArbitraryDiff(workItemId, fromVersion, toVersion);
}

/** @deprecated use getVersionDiff */
export async function diffVsPrevious(
  workItemId: string,
  versionNumber: number,
): Promise<VersionDiff> {
  return getVersionDiff(workItemId, versionNumber);
}

// ─── createComment ────────────────────────────────────────────────────────────

export async function createComment(
  workItemId: string,
  req: CreateCommentRequest,
): Promise<Comment> {
  const { anchor_start_offset, anchor_end_offset } = req;
  if (
    anchor_start_offset !== undefined &&
    anchor_start_offset !== null &&
    anchor_end_offset !== undefined &&
    anchor_end_offset !== null &&
    anchor_start_offset > anchor_end_offset
  ) {
    return Promise.reject({ code: 'INVALID_ANCHOR_RANGE' });
  }

  const res = await apiPost<Envelope<Comment>>(
    `/api/v1/work-items/${workItemId}/comments`,
    req,
  );
  return res.data;
}

// ─── listTimeline ─────────────────────────────────────────────────────────────

export interface TimelineFilters {
  event_type?: TimelineEventType;
  actor_type?: ActorType;
  cursor?: string;
  limit?: number;
}

export async function listTimeline(
  workItemId: string,
  filters: TimelineFilters,
): Promise<TimelinePage> {
  const params = new URLSearchParams({ limit: String(filters.limit ?? 20) });
  if (filters.event_type) params.set('event_type', filters.event_type);
  if (filters.actor_type) params.set('actor_type', filters.actor_type);
  if (filters.cursor) params.set('cursor', filters.cursor);

  return apiGet<TimelinePage>(
    `/api/v1/work-items/${workItemId}/timeline?${params.toString()}`,
  );
}
