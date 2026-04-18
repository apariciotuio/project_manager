import { apiGet, apiPost, apiPatch } from '@/lib/api-client';
import type {
  JiraConfigsResponse,
  JiraConfigResponse,
  JiraConfig,
  CreateJiraConfigRequest,
  JiraMappingsResponse,
  JiraTestResult,
} from '@/lib/types/api';

export async function listJiraConfigs(): Promise<JiraConfigsResponse> {
  return apiGet<JiraConfigsResponse>('/api/v1/admin/integrations/jira');
}

export async function getJiraConfig(id: string): Promise<JiraConfigResponse> {
  return apiGet<JiraConfigResponse>(`/api/v1/admin/integrations/jira/${id}`);
}

export async function createJiraConfig(
  body: CreateJiraConfigRequest
): Promise<{ data: Pick<JiraConfig, 'id' | 'state'>; message: string }> {
  return apiPost('/api/v1/admin/integrations/jira', body);
}

export async function updateJiraConfig(
  id: string,
  body: { credentials?: Record<string, string>; state?: string }
): Promise<JiraConfigResponse> {
  return apiPatch(`/api/v1/admin/integrations/jira/${id}`, body);
}

export async function testJiraConnection(
  id: string
): Promise<{ data: JiraTestResult; message: string }> {
  return apiPost(`/api/v1/admin/integrations/jira/${id}/test`, {});
}

export async function listJiraMappings(configId: string): Promise<JiraMappingsResponse> {
  return apiGet<JiraMappingsResponse>(`/api/v1/admin/integrations/jira/${configId}/mappings`);
}

export async function createJiraMapping(
  configId: string,
  body: { jira_project_key: string; local_project_id?: string; type_mappings?: Record<string, string> }
): Promise<{ data: unknown; message: string }> {
  return apiPost(`/api/v1/admin/integrations/jira/${configId}/mappings`, body);
}
