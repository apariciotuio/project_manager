/**
 * EP-04 — Gap API client functions.
 * GET /api/v1/work-items/{id}/gaps returns { data: GapItem[] } (array of gap objects).
 * POST /api/v1/work-items/{id}/gaps/ai-review is EP-03-owned.
 */

import { apiGet, apiPost } from '../api-client';
import type { GapFinding, GapReport } from '../types/gap';
import type { GapItem, GapsApiResponse } from '../types/specification';

/**
 * Fetch gap report for a work item.
 * EP-04 endpoint: GET /api/v1/work-items/{id}/gaps → { data: GapItem[] }
 * Mapped to GapReport for backward compat with EP-03 callers.
 */
export async function getGapReport(workItemId: string): Promise<GapReport> {
  const res = await apiGet<GapsApiResponse>(`/api/v1/work-items/${workItemId}/gaps`);
  const items: GapItem[] = res.data;
  const findings: GapFinding[] = items.map((g) => ({
    dimension: g.dimension,
    severity: g.severity,
    message: g.message,
    source: 'rule' as const,
  }));
  return { work_item_id: workItemId, findings, score: 1.0 };
}

/**
 * Trigger async AI-enhanced gap review.
 * Returns immediately with a job_id; result arrives via SSE / polling.
 */
interface Envelope<T> {
  data: T;
}

export async function triggerAiReview(workItemId: string): Promise<{ job_id: string }> {
  const res = await apiPost<Envelope<{ job_id: string }>>(
    `/api/v1/work-items/${workItemId}/gaps/ai-review`,
    {},
  );
  return res.data;
}

export type { GapFinding, GapReport };
