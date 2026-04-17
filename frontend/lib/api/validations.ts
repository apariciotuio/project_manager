/**
 * EP-06 — Validations checklist API client.
 * Endpoints: /api/v1/work-items/:id/validations, /api/v1/work-items/:id/validations/:rule_id/waive
 */
import { apiGet, apiPost } from '../api-client';

// ─── Types ────────────────────────────────────────────────────────────────────

export type ValidationState = 'pending' | 'passed' | 'waived' | 'obsolete';

export interface ValidationRuleStatus {
  rule_id: string;
  label: string;
  required: boolean;
  status: ValidationState;
  passed_at: string | null;
  passed_by_review_request_id: string | null;
  waived_at: string | null;
  waived_by: string | null;
}

export interface ValidationChecklist {
  required: ValidationRuleStatus[];
  recommended: ValidationRuleStatus[];
}

export interface WaiveResponse {
  rule_id: string;
  status: ValidationState;
  waived_at: string | null;
  waived_by: string | null;
}

// ─── Envelope ────────────────────────────────────────────────────────────────

interface Envelope<T> {
  data: T;
  message?: string;
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function getValidations(workItemId: string): Promise<ValidationChecklist> {
  const res = await apiGet<Envelope<ValidationChecklist>>(
    `/api/v1/work-items/${workItemId}/validations`,
  );
  return res.data;
}

export async function waiveValidation(
  workItemId: string,
  ruleId: string,
): Promise<WaiveResponse> {
  const res = await apiPost<Envelope<WaiveResponse>>(
    `/api/v1/work-items/${workItemId}/validations/${ruleId}/waive`,
    {},
  );
  return res.data;
}
