/**
 * EP-03 — Suggestion API client functions.
 * Endpoints: GET/POST /api/v1/work-items/{id}/suggestion-sets,
 *            GET /api/v1/suggestion-sets/{batch_id},
 *            PATCH /api/v1/suggestion-items/{item_id}
 */

import { apiGet, apiPost, apiPatch } from '../api-client';
import { ApiError } from '../api-client';
import type { SuggestionSet, SuggestionItemStatus, ApplySuggestionsResult } from '../types/suggestion';

interface Envelope<T> {
  data: T;
}

export async function generateSuggestionSet(workItemId: string): Promise<{ set_id: string }> {
  const res = await apiPost<Envelope<{ set_id: string }>>(
    `/api/v1/work-items/${workItemId}/suggestion-sets`,
    {},
  );
  return res.data;
}

export async function getSuggestionSets(workItemId: string): Promise<SuggestionSet[]> {
  const res = await apiGet<Envelope<SuggestionSet[]>>(
    `/api/v1/work-items/${workItemId}/suggestion-sets`,
  );
  return res.data;
}

export async function getSuggestionSet(batchId: string): Promise<SuggestionSet> {
  const res = await apiGet<Envelope<SuggestionSet>>(`/api/v1/suggestion-sets/${batchId}`);
  return res.data;
}

export async function updateSuggestionItemStatus(
  itemId: string,
  status: SuggestionItemStatus,
): Promise<void> {
  await apiPatch<void>(`/api/v1/suggestion-items/${itemId}`, { status });
}

/**
 * Apply all accepted suggestions in a batch.
 * Throws ApiError(404) if batch not found, ApiError(422) if no accepted suggestions,
 * ApiError(409) on version conflict.
 */
export async function applyBatch(batchId: string): Promise<ApplySuggestionsResult> {
  const res = await apiPost<Envelope<ApplySuggestionsResult>>(
    `/api/v1/suggestion-sets/${batchId}/apply`,
    {},
  );
  return res.data;
}

/**
 * @deprecated Use applyBatch(batchId) instead.
 */
export async function applySuggestions(
  setId: string,
  _acceptedItemIds: string[],
): Promise<ApplySuggestionsResult> {
  return applyBatch(setId);
}

export { ApiError };
