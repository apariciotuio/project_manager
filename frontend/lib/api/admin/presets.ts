import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api-client';
import type {
  ContextPresetsResponse,
  ContextPresetResponse,
  CreateContextPresetRequest,
  PatchContextPresetRequest,
} from '@/lib/types/api';

export async function listContextPresets(): Promise<ContextPresetsResponse> {
  return apiGet<ContextPresetsResponse>('/api/v1/admin/context-presets');
}

export async function createContextPreset(
  body: CreateContextPresetRequest
): Promise<ContextPresetResponse> {
  return apiPost('/api/v1/admin/context-presets', body);
}

export async function updateContextPreset(
  id: string,
  body: PatchContextPresetRequest
): Promise<ContextPresetResponse> {
  return apiPatch(`/api/v1/admin/context-presets/${id}`, body);
}

export async function deleteContextPreset(id: string): Promise<void> {
  await apiDelete(`/api/v1/admin/context-presets/${id}`);
}
