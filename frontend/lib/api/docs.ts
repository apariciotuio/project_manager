/**
 * EP-13 — Doc content + related docs API clients.
 */
import { apiGet } from '../api-client';
import type { DocContentResponse, RelatedDocsResponse, PuppetSearchResponse } from '../types/search';

export async function fetchDocContent(docId: string): Promise<DocContentResponse> {
  return apiGet<DocContentResponse>(`/api/v1/docs/${docId}/content`);
}

export async function fetchRelatedDocs(workItemId: string): Promise<RelatedDocsResponse> {
  return apiGet<RelatedDocsResponse>(`/api/v1/work-items/${workItemId}/related-docs`);
}

export type { PuppetSearchResponse };
