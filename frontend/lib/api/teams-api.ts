/**
 * EP-08 — Teams API client.
 *
 * Routes (all under /api/v1):
 *   GET    /teams                           → listTeams
 *   GET    /teams/:id                       → getTeam
 *   POST   /teams                           → createTeam
 *   PATCH  /teams/:id                       → updateTeam
 *   DELETE /teams/:id                       → deleteTeam
 *   POST   /teams/:id/members               → addMember
 *   DELETE /teams/:id/members/:user_id      → removeMember
 *   PATCH  /teams/:id/members/:user_id      → updateMemberRole
 *   POST   /teams/:id/suspend               → suspendTeam
 *   POST   /teams/:id/resume                → resumeTeam
 */

import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api-client';

// ─── DTOs ─────────────────────────────────────────────────────────────────────

export type TeamStatus = 'active' | 'suspended' | 'deleted';
export type TeamRole = 'member' | 'lead';

export interface TeamMember {
  user_id: string;
  display_name: string;
  role: TeamRole;
  joined_at: string;
}

export interface Team {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  status: TeamStatus;
  can_receive_reviews: boolean;
  created_at: string;
  members: TeamMember[];
}

export interface CreateTeamBody {
  name: string;
  description?: string;
  can_receive_reviews?: boolean;
}

export interface UpdateTeamBody {
  name?: string;
  description?: string;
  can_receive_reviews?: boolean;
}

export interface AddMemberBody {
  user_id: string;
  role?: TeamRole;
}

// ─── Envelopes ────────────────────────────────────────────────────────────────

interface TeamEnvelope {
  data: Team;
  message: string;
}

interface TeamsEnvelope {
  data: Team[];
  message: string;
}

interface MemberEnvelope {
  data: TeamMember;
  message: string;
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function listTeams(): Promise<Team[]> {
  const res = await apiGet<TeamsEnvelope>('/api/v1/teams');
  return res.data;
}

export async function getTeam(id: string): Promise<Team> {
  const res = await apiGet<TeamEnvelope>(`/api/v1/teams/${id}`);
  return res.data;
}

export async function createTeam(body: CreateTeamBody): Promise<Team> {
  const res = await apiPost<TeamEnvelope>('/api/v1/teams', body);
  return res.data;
}

export async function updateTeam(id: string, patch: UpdateTeamBody): Promise<Team> {
  const res = await apiPatch<TeamEnvelope>(`/api/v1/teams/${id}`, patch);
  return res.data;
}

export async function deleteTeam(id: string): Promise<void> {
  await apiDelete(`/api/v1/teams/${id}`);
}

export async function addMember(teamId: string, body: AddMemberBody): Promise<TeamMember> {
  const res = await apiPost<MemberEnvelope>(`/api/v1/teams/${teamId}/members`, body);
  return res.data;
}

export async function removeMember(teamId: string, userId: string): Promise<void> {
  await apiDelete(`/api/v1/teams/${teamId}/members/${userId}`);
}

export async function updateMemberRole(
  teamId: string,
  userId: string,
  role: TeamRole,
): Promise<TeamMember> {
  const res = await apiPatch<MemberEnvelope>(`/api/v1/teams/${teamId}/members/${userId}`, { role });
  return res.data;
}

export async function suspendTeam(id: string): Promise<void> {
  await apiPost(`/api/v1/teams/${id}/suspend`, {});
}

export async function resumeTeam(id: string): Promise<void> {
  await apiPost(`/api/v1/teams/${id}/resume`, {});
}
