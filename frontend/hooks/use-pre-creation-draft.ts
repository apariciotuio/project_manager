'use client';

import { useState, useCallback, useRef } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api-client';
import type { WorkItemType } from '@/lib/types/work-item';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DraftData {
  title?: string;
  type?: WorkItemType;
  description?: string;
  project_id?: string;
  parent_work_item_id?: string;
  tags?: string[];
  /** ISO string — server timestamp, forwarded from WorkItemDraft.updated_at */
  updated_at?: string;
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
  /** Draft fetched from server on mount — not yet applied to the form. Null after a choice is made. */
  pendingServerDraft: DraftData | null;
  save: (data: DraftData, localVersion: number) => void;
  discard: () => Promise<void>;
  resolveConflict: (data: DraftData) => void;
  keepMine: (data: DraftData) => void;
  /** Apply pendingServerDraft to the form (caller provides the hydrate callback). */
  applyPendingDraft: () => void;
  /** Delete server draft and clear pending state — user chose to start blank. */
  discardPendingDraft: () => Promise<void>;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function usePreCreationDraft(
  workspaceId: string,
  onHydrate: (data: DraftData, draftId: string, serverVersion: number) => void,
): UsePreCreationDraftResult {
  const [draftId, setDraftId] = useState<string | null>(null);
  const [conflictError, setConflictError] = useState<DraftConflictDetails | null>(null);
  const [pendingServerDraft, setPendingServerDraft] = useState<DraftData | null>(null);
  const pendingServerDraftIdRef = useRef<string | null>(null);
  const pendingServerVersionRef = useRef<number>(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const localVersionRef = useRef<number>(0);
  const pendingDataRef = useRef<DraftData | null>(null);

  // Fetch on mount — holds draft in pendingServerDraft instead of auto-hydrating
  const fetchOnMount = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await apiGet<DraftGetResponse>(
        `/api/v1/work-item-drafts?workspace_id=${workspaceId}`,
      );
      if (res.data) {
        pendingServerDraftIdRef.current = res.data.id;
        pendingServerVersionRef.current = res.data.server_version;
        // Expose draft timestamp so the banner can show relative time
        setPendingServerDraft({ ...res.data.data, updated_at: res.data.updated_at });
      }
    } catch {
      // Non-blocking — draft fetch failure should not prevent form use
    }
  }, [workspaceId]);

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
      }, 3000);
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

  /** Client-wins conflict resolution: bumps version and re-saves local data. */
  const keepMine = useCallback(
    (data: DraftData) => {
      if (!conflictError) return;
      const bumpedVersion = conflictError.server_version + 1;
      localVersionRef.current = bumpedVersion;
      setConflictError(null);
      void doSave(data, bumpedVersion);
    },
    [conflictError, doSave],
  );

  /** User chose "Resume": hydrate form with pending draft data. */
  const applyPendingDraft = useCallback(() => {
    if (!pendingServerDraft || !pendingServerDraftIdRef.current) return;
    setDraftId(pendingServerDraftIdRef.current);
    localVersionRef.current = pendingServerVersionRef.current;
    onHydrate(pendingServerDraft, pendingServerDraftIdRef.current, pendingServerVersionRef.current);
    setPendingServerDraft(null);
  }, [pendingServerDraft, onHydrate]);

  /** User chose "Discard": delete server draft and start blank. */
  const discardPendingDraft = useCallback(async () => {
    const id = pendingServerDraftIdRef.current;
    setPendingServerDraft(null);
    pendingServerDraftIdRef.current = null;
    if (!id) return;
    try {
      await apiDelete<void>(`/api/v1/work-item-drafts/${id}`);
    } catch {
      // Non-fatal — user wanted to start blank regardless
    }
  }, []);

  return {
    draftId,
    conflictError,
    pendingServerDraft,
    save,
    discard,
    resolveConflict,
    keepMine,
    applyPendingDraft,
    discardPendingDraft,
  };
}
