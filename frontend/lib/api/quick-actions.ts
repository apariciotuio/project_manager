/**
 * EP-03 — Quick action API client functions.
 * Quick actions are in-place section rewrites triggered by user.
 * Phase 7: executeQuickAction / undoQuickAction.
 * Note: backend endpoints are stubs until EP-04 ships the section editor.
 */

import { apiPost } from '../api-client';

interface Envelope<T> {
  data: T;
}

export interface QuickActionResult {
  result: string;
  action_id: string;
}

export type QuickActionType =
  | 'rewrite'
  | 'concretize'
  | 'expand'
  | 'shorten'
  | 'generate_ac';

export async function executeQuickAction(
  workItemId: string,
  section: string,
  action: QuickActionType,
): Promise<QuickActionResult> {
  const res = await apiPost<Envelope<QuickActionResult>>(
    `/api/v1/work-items/${workItemId}/sections/${section}/quick-actions`,
    { action },
  );
  return res.data;
}

export async function undoQuickAction(
  workItemId: string,
  actionId: string,
): Promise<void> {
  await apiPost<void>(
    `/api/v1/work-items/${workItemId}/quick-actions/${actionId}/undo`,
    {},
  );
}
