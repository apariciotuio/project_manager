/**
 * EP-09 — Search API client.
 * POST /api/v1/search — Puppet-backed semantic search.
 * EP-13 — GET /api/v1/search — cursor-paginated Puppet search.
 */
import { apiPost, apiGet } from '../api-client';
import type { SearchResult } from '../types/work-item';
import type { PuppetSearchResponse, PuppetSearchParams } from '../types/search';

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

// ─── Suggest ──────────────────────────────────────────────────────────────────

export interface SuggestResult {
  id: string;
  title: string;
  type: string;
}

export interface SuggestResponse {
  data: SuggestResult[];
}

/**
 * EP-13 — GET /api/v1/search/suggest?q=... — prefix type-ahead.
 */
export async function fetchSuggest(q: string): Promise<SuggestResponse> {
  const qs = new URLSearchParams({ q });
  return apiGet<SuggestResponse>(`/api/v1/search/suggest?${qs.toString()}`);
}

/**
 * EP-13 — GET /api/v1/search with cursor pagination.
 */
export async function puppetSearch(params: PuppetSearchParams): Promise<PuppetSearchResponse> {
  const qs = new URLSearchParams();
  qs.set('q', params.q);
  if (params.cursor) qs.set('cursor', params.cursor);
  if (params.limit !== undefined) qs.set('limit', String(params.limit));
  if (params.state) qs.set('state', params.state);
  if (params.type) qs.set('type', params.type);
  if (params.team_id) qs.set('team_id', params.team_id);
  if (params.owner_id) qs.set('owner_id', params.owner_id);
  if (params.include_archived !== undefined) qs.set('include_archived', String(params.include_archived));
  return apiGet<PuppetSearchResponse>(`/api/v1/search?${qs.toString()}`);
}
