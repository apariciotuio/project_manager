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
 * Apply selected suggestions. Throws ApiError(409) on version conflict.
 */
export async function applySuggestions(
  setId: string,
  acceptedItemIds: string[],
): Promise<ApplySuggestionsResult> {
  try {
    const res = await apiPost<Envelope<ApplySuggestionsResult>>(
      `/api/v1/suggestion-sets/${setId}/apply`,
      { accepted_item_ids: acceptedItemIds },
    );
    return res.data;
  } catch (err) {
    // Re-throw so callers can handle 409 specifically
    throw err;
  }
}

export { ApiError };
