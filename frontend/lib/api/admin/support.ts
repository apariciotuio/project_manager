import { apiGet, apiPost } from '@/lib/api-client';
import type {
  OrphanedWorkItem,
  PendingInvitation,
  FailedExport,
  ConfigBlockedWorkItem,
} from '@/lib/types/api';

export async function getOrphanedWorkItems(
  workspaceId?: string
): Promise<{ data: OrphanedWorkItem[]; message: string }> {
  const qs = workspaceId ? `?workspace_id=${workspaceId}` : '';
  return apiGet(`/api/v1/admin/support/orphaned-work-items${qs}`);
}

export async function getPendingInvitations(expiringSoon?: boolean): Promise<{ data: PendingInvitation[]; message: string }> {
  const qs = expiringSoon ? '?expiring_soon=true' : '';
  return apiGet(`/api/v1/admin/support/pending-invitations${qs}`);
}

export async function getFailedExports(): Promise<{ data: FailedExport[]; message: string }> {
  return apiGet('/api/v1/admin/support/failed-exports');
}

export async function getConfigBlockedWorkItems(): Promise<{ data: ConfigBlockedWorkItem[]; message: string }> {
  return apiGet('/api/v1/admin/support/config-blocked-work-items');
}

export async function reassignOwner(
  workItemId: string,
  newOwnerId: string
): Promise<{ data: Record<string, never>; message: string }> {
  return apiPost('/api/v1/admin/support/reassign-owner', {
    work_item_id: workItemId,
    new_owner_id: newOwnerId,
  });
}

export async function retryAllFailedExports(): Promise<{ data: unknown; message: string }> {
  return apiPost('/api/v1/admin/support/failed-exports/retry-all', {});
}
