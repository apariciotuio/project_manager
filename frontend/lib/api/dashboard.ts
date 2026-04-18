/**
 * EP-09 — Dashboard API client.
 * GET /api/v1/workspaces/dashboard
 * GET /api/v1/dashboards/person/{user_id}
 * GET /api/v1/dashboards/team/{team_id}
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

// ─── Person dashboard ────────────────────────────────────────────────────────

export interface PersonDashboard {
  owned_by_state: Record<string, number>;
  overloaded: boolean;
  pending_reviews_count: number;
  inbox_count: number;
}

export async function getPersonDashboard(userId: string): Promise<PersonDashboard> {
  const res = await apiGet<Envelope<PersonDashboard>>(`/api/v1/dashboards/person/${userId}`);
  return res.data;
}

// ─── Team dashboard ───────────────────────────────────────────────────────────

export interface TeamDashboard {
  owned_by_state: Record<string, number>;
  pending_reviews: number;
  /** Items currently in 'ready' state updated in last 30 days (approx velocity) */
  recent_ready_items: number;
  blocked_count: number;
}

export async function getTeamDashboard(teamId: string): Promise<TeamDashboard> {
  const res = await apiGet<Envelope<TeamDashboard>>(`/api/v1/dashboards/team/${teamId}`);
  return res.data;
}
