/**
 * EP-09 — Search API client.
 * POST /api/v1/search — Puppet-backed semantic search.
 */
import { apiPost } from '../api-client';
import type { SearchResult } from '../types/work-item';

interface Envelope<T> {
  data: T;
}

export interface SearchRequest {
  q: string;
  limit?: number;
  tags?: string[];
}

export async function searchWorkItems(request: SearchRequest): Promise<SearchResult> {
  const res = await apiPost<Envelope<SearchResult>>('/api/v1/search', request);
  return res.data;
}
