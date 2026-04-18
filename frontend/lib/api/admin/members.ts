import { apiGet, apiPost, apiPatch } from '@/lib/api-client';
import type {
  AdminMembersResponse,
  PatchMemberRequest,
  InviteMemberRequest,
} from '@/lib/types/api';

export async function listAdminMembers(params?: {
  state?: string;
  teamless?: boolean;
  cursor?: string;
  limit?: number;
}): Promise<AdminMembersResponse> {
  const qs = new URLSearchParams();
  if (params?.state) qs.set('state', params.state);
  if (params?.teamless) qs.set('teamless', 'true');
  if (params?.cursor) qs.set('cursor', params.cursor);
  if (params?.limit) qs.set('limit', String(params.limit));
  const query = qs.toString();
  return apiGet<AdminMembersResponse>(`/api/v1/admin/members${query ? `?${query}` : ''}`);
}

export async function inviteMember(body: InviteMemberRequest): Promise<{ data: { invitation_id: string }; message: string }> {
  return apiPost('/api/v1/admin/members', body);
}

export async function updateMember(
  id: string,
  body: PatchMemberRequest
): Promise<{ data: { id: string; state: string }; message: string }> {
  return apiPatch(`/api/v1/admin/members/${id}`, body);
}

export async function resendInvitation(
  invitationId: string
): Promise<{ data: Record<string, never>; message: string }> {
  return apiPost(`/api/v1/admin/members/invitations/${invitationId}/resend`, {});
}
