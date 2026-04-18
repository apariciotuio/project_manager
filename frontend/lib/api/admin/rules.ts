import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api-client';
import type {
  ValidationRulesResponse,
  ValidationRule,
  CreateValidationRuleRequest,
  PatchValidationRuleRequest,
} from '@/lib/types/api';

export async function listValidationRules(params?: {
  project_id?: string;
  work_item_type?: string;
}): Promise<ValidationRulesResponse> {
  const qs = new URLSearchParams();
  if (params?.project_id) qs.set('project_id', params.project_id);
  if (params?.work_item_type) qs.set('work_item_type', params.work_item_type);
  const query = qs.toString();
  return apiGet<ValidationRulesResponse>(
    `/api/v1/admin/rules/validation${query ? `?${query}` : ''}`
  );
}

export async function createValidationRule(
  body: CreateValidationRuleRequest
): Promise<{ data: ValidationRule; message: string }> {
  return apiPost('/api/v1/admin/rules/validation', body);
}

export async function updateValidationRule(
  id: string,
  body: PatchValidationRuleRequest
): Promise<{ data: ValidationRule & { warnings: string[] }; message: string }> {
  return apiPatch(`/api/v1/admin/rules/validation/${id}`, body);
}

export async function deleteValidationRule(id: string): Promise<void> {
  await apiDelete(`/api/v1/admin/rules/validation/${id}`);
}
