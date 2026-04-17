'use client';

import { useState, useCallback, useRef } from 'react';
import { apiGet, apiPost, apiDelete } from '@/lib/api-client';
import type { WorkItemType } from '@/lib/types/work-item';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DraftData {
  title?: string;
  type?: WorkItemType;
  description?: string;
  project_id?: string;
  parent_work_item_id?: string;
  tags?: string[];
}

interface WorkItemDraft {
  id: string;
  user_id: string;
  workspace_id: string;
  data: DraftData;
  local_version: number;
  server_version: number;
  updated_at: string;
}

interface DraftGetResponse {
  data: WorkItemDraft | null;
}

interface DraftSaveResponse {
  data: {
    draft_id: string;
    local_version: number;
  };
}

interface DraftConflictDetails {
  server_version: number;
  server_data: DraftData;
}

export interface UsePreCreationDraftResult {
  draftId: string | null;
  conflictError: DraftConflictDetails | null;
  save: (data: DraftData, localVersion: number) => void;
  discard: () => Promise<void>;
  resolveConflict: (data: DraftData) => void;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function usePreCreationDraft(
  workspaceId: string,
  onHydrate: (data: DraftData, draftId: string, serverVersion: number) => void,
): UsePreCreationDraftResult {
  const [draftId, setDraftId] = useState<string | null>(null);
  const [conflictError, setConflictError] = useState<DraftConflictDetails | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const localVersionRef = useRef<number>(0);
  const pendingDataRef = useRef<DraftData | null>(null);

  // Fetch on mount — caller is responsible for calling this once
  const fetchOnMount = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await apiGet<DraftGetResponse>(
        `/api/v1/work-item-drafts?workspace_id=${workspaceId}`,
      );
      if (res.data) {
        setDraftId(res.data.id);
        localVersionRef.current = res.data.local_version;
        onHydrate(res.data.data, res.data.id, res.data.server_version);
      }
    } catch {
      // Non-blocking — draft fetch failure should not prevent form use
    }
  }, [workspaceId, onHydrate]);

  // Trigger mount fetch exactly once via ref guard
  const mountedRef = useRef(false);
  if (!mountedRef.current && workspaceId) {
    mountedRef.current = true;
    void fetchOnMount();
  }

  const doSave = useCallback(
    async (data: DraftData, version: number) => {
      try {
        const res = await apiPost<DraftSaveResponse>('/api/v1/work-item-drafts', {
          workspace_id: workspaceId,
          data,
          local_version: version,
        });
        setDraftId(res.data.draft_id);
        localVersionRef.current = res.data.local_version;
        setConflictError(null);
      } catch (err: unknown) {
        const apiErr = err as { status?: number; details?: DraftConflictDetails };
        if (apiErr?.status === 409) {
          setConflictError(apiErr.details ?? null);
        }
        // Other errors: silent — next debounce will retry
      }
    },
    [workspaceId],
  );

  const save = useCallback(
    (data: DraftData, localVersion: number) => {
      pendingDataRef.current = data;
      localVersionRef.current = localVersion;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        void doSave(data, localVersion);
      }, 2000);
    },
    [doSave],
  );

  const discard = useCallback(async () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!draftId) return;
    try {
      await apiDelete<void>(`/api/v1/work-item-drafts/${draftId}`);
    } catch {
      // Discard failure is non-fatal — item was created successfully
    }
    setDraftId(null);
    setConflictError(null);
  }, [draftId]);

  const resolveConflict = useCallback(
    (data: DraftData) => {
      if (!conflictError) return;
      const bumpedVersion = conflictError.server_version + 1;
      localVersionRef.current = bumpedVersion;
      setConflictError(null);
      void doSave(data, bumpedVersion);
    },
    [conflictError, doSave],
  );

  return { draftId, conflictError, save, discard, resolveConflict };
}
