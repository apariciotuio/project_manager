/**
 * EP-09 — Saved Searches API client.
 */
import { apiGet, apiPost, apiPatch, apiDelete } from '../api-client';
import type { SavedSearch } from '../types/work-item';

interface Envelope<T> {
  data: T;
}

export interface CreateSavedSearchRequest {
  name: string;
  query_params?: Record<string, unknown>;
  is_shared?: boolean;
}

export interface UpdateSavedSearchRequest {
  name?: string;
  query_params?: Record<string, unknown>;
  is_shared?: boolean;
}

export async function listSavedSearches(): Promise<SavedSearch[]> {
  const res = await apiGet<Envelope<SavedSearch[]>>('/api/v1/saved-searches');
  return res.data;
}

export async function createSavedSearch(data: CreateSavedSearchRequest): Promise<SavedSearch> {
  const res = await apiPost<Envelope<SavedSearch>>('/api/v1/saved-searches', data);
  return res.data;
}

export async function updateSavedSearch(id: string, data: UpdateSavedSearchRequest): Promise<SavedSearch> {
  const res = await apiPatch<Envelope<SavedSearch>>(`/api/v1/saved-searches/${id}`, data);
  return res.data;
}

export async function deleteSavedSearch(id: string): Promise<void> {
  await apiDelete<void>(`/api/v1/saved-searches/${id}`);
}

export async function runSavedSearch(id: string): Promise<{ items: unknown[]; total: number; has_next: boolean }> {
  const res = await apiGet<Envelope<{ items: unknown[]; total: number; has_next: boolean }>>(
    `/api/v1/saved-searches/${id}/run`,
  );
  return res.data;
}
