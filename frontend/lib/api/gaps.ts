/**
 * EP-03 — Gap API client functions.
 * TODO: GET /api/v1/work-items/{id}/gaps is EP-04-owned; returns stub until EP-04 ships.
 * POST /api/v1/work-items/{id}/gaps/ai-review is EP-03-owned.
 */

import { apiGet, apiPost } from '../api-client';
import type { GapFinding, GapReport } from '../types/gap';

interface Envelope<T> {
  data: T;
}

/**
 * TODO: EP-04 endpoint — stubs empty findings until EP-04 ships.
 */
export async function getGapReport(workItemId: string): Promise<GapReport> {
  try {
    const res = await apiGet<Envelope<GapReport>>(`/api/v1/work-items/${workItemId}/gaps`);
    return res.data;
  } catch {
    // EP-04 endpoint not yet shipped — return empty stub
    return { work_item_id: workItemId, findings: [], score: 1.0 };
  }
}

/**
 * Trigger async AI-enhanced gap review.
 * Returns immediately with a job_id; result arrives via SSE / polling.
 */
export async function triggerAiReview(workItemId: string): Promise<{ job_id: string }> {
  const res = await apiPost<Envelope<{ job_id: string }>>(
    `/api/v1/work-items/${workItemId}/gaps/ai-review`,
    {},
  );
  return res.data;
}

export type { GapFinding, GapReport };
