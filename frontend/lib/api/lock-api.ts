/**
 * EP-17 — Section lock API client.
 *
 * Routes (all under /api/v1):
 *   POST   /sections/{sectionId}/lock            → acquire
 *   POST   /sections/{sectionId}/lock/heartbeat  → heartbeat
 *   DELETE /sections/{sectionId}/lock            → release
 *   POST   /sections/{sectionId}/lock/force-release → force-release (admin)
 *   GET    /work-items/{workItemId}/locks        → list active locks
 */

import { apiDelete, apiGet, apiPost } from '@/lib/api-client';
import type {
  LockEnvelope,
  LockReleaseEnvelope,
  LocksListEnvelope,
  RespondToRequestBody,
  SectionLockDTO,
  SectionLockSummary,
  UnlockRequestDTO,
  UnlockRequestEnvelope,
} from '@/lib/types/lock';

export async function acquireSectionLock(sectionId: string): Promise<SectionLockDTO> {
  const res = await apiPost<LockEnvelope>(`/api/v1/sections/${sectionId}/lock`, {});
  return res.data;
}

export async function heartbeatSectionLock(sectionId: string): Promise<SectionLockDTO> {
  const res = await apiPost<LockEnvelope>(`/api/v1/sections/${sectionId}/lock/heartbeat`, {});
  return res.data;
}

export async function releaseSectionLock(sectionId: string): Promise<void> {
  await apiDelete<LockReleaseEnvelope>(`/api/v1/sections/${sectionId}/lock`);
}

export async function forceReleaseSectionLock(sectionId: string): Promise<void> {
  await apiPost<LockReleaseEnvelope>(`/api/v1/sections/${sectionId}/lock/force-release`, {});
}

export async function listWorkItemLocks(workItemId: string): Promise<SectionLockSummary[]> {
  const res = await apiGet<LocksListEnvelope>(`/api/v1/work-items/${workItemId}/locks`);
  return res.data;
}

export async function requestSectionUnlock(
  sectionId: string,
  reason: string,
): Promise<UnlockRequestDTO> {
  const res = await apiPost<UnlockRequestEnvelope>(
    `/api/v1/sections/${sectionId}/lock/unlock-request`,
    { reason },
  );
  return res.data;
}

export async function respondToUnlockRequest(
  sectionId: string,
  body: RespondToRequestBody,
): Promise<UnlockRequestDTO> {
  const res = await apiPost<UnlockRequestEnvelope>(
    `/api/v1/sections/${sectionId}/lock/respond`,
    body,
  );
  return res.data;
}
