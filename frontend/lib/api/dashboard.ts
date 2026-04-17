/**
 * EP-09 — Dashboard API client.
 * GET /api/v1/workspaces/dashboard
 */
import { apiGet } from '../api-client';
import type { WorkspaceDashboard } from '../types/work-item';

interface Envelope<T> {
  data: T;
}

export async function getWorkspaceDashboard(): Promise<WorkspaceDashboard> {
  const res = await apiGet<Envelope<WorkspaceDashboard>>('/api/v1/workspaces/dashboard');
  return res.data;
}
