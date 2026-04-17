/**
 * EP-06 — Review requests API client.
 * Endpoints: /api/v1/work-items/:id/review-requests, /api/v1/review-requests/:id, /api/v1/my/reviews
 */
import { apiGet, apiPost, apiDelete } from '../api-client';

// ─── Types ───────────────────────────────────────────────────────────────────

export type ReviewRequestStatus = 'pending' | 'closed' | 'cancelled';
export type ReviewDecision = 'approved' | 'rejected' | 'changes_requested';

export interface ReviewResponse {
  id: string;
  review_request_id: string;
  responder_id: string;
  decision: ReviewDecision;
  content: string | null;
  responded_at: string;
}

export interface ReviewRequest {
  id: string;
  work_item_id: string;
  version_id: string;
  reviewer_type: 'user' | 'team';
  reviewer_id: string | null;
  team_id: string | null;
  validation_rule_id: string | null;
  status: ReviewRequestStatus;
  requested_by: string;
  requested_at: string;
  cancelled_at: string | null;
  version_outdated?: boolean;
  requested_version?: number;
  current_version?: number;
}

export interface ReviewRequestWithResponses extends ReviewRequest {
  responses: ReviewResponse[];
}

export interface CreateReviewRequestBody {
  reviewer_id: string;
  version_id: string;
  validation_rule_id?: string | null;
}

export interface RespondReviewBody {
  decision: ReviewDecision;
  content?: string | null;
}

// ─── Envelope ────────────────────────────────────────────────────────────────

interface Envelope<T> {
  data: T;
  message?: string;
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function createReviewRequest(
  workItemId: string,
  body: CreateReviewRequestBody,
): Promise<ReviewRequest> {
  const res = await apiPost<Envelope<ReviewRequest>>(
    `/api/v1/work-items/${workItemId}/review-requests`,
    body,
  );
  return res.data;
}

export async function listReviewRequests(
  workItemId: string,
): Promise<ReviewRequestWithResponses[]> {
  const res = await apiGet<Envelope<ReviewRequestWithResponses[]>>(
    `/api/v1/work-items/${workItemId}/review-requests`,
  );
  return res.data;
}

export async function getReviewRequest(requestId: string): Promise<ReviewRequest> {
  const res = await apiGet<Envelope<ReviewRequest>>(
    `/api/v1/review-requests/${requestId}`,
  );
  return res.data;
}

export async function cancelReviewRequest(requestId: string): Promise<void> {
  await apiDelete<Envelope<{ status: string }>>(
    `/api/v1/review-requests/${requestId}`,
  );
}

export async function submitReviewResponse(
  requestId: string,
  body: RespondReviewBody,
): Promise<ReviewRequestWithResponses> {
  const res = await apiPost<Envelope<ReviewRequestWithResponses>>(
    `/api/v1/review-requests/${requestId}/response`,
    body,
  );
  return res.data;
}

export async function listMyPendingReviews(): Promise<ReviewRequest[]> {
  const res = await apiGet<Envelope<ReviewRequest[]>>('/api/v1/my/reviews');
  return res.data;
}
