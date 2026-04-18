import { apiGet } from '@/lib/api-client';
import type { AdminDashboardResponse } from '@/lib/types/api';

export async function getAdminDashboard(projectId?: string): Promise<AdminDashboardResponse> {
  const qs = projectId ? `?project_id=${projectId}` : '';
  return apiGet<AdminDashboardResponse>(`/api/v1/admin/dashboard${qs}`);
}
