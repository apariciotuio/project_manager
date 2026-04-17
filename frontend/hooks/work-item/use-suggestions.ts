'use client';

import { useState, useCallback } from 'react';
import {
  generateSuggestionSet,
  getSuggestionSet,
  applySuggestions,
  updateSuggestionItemStatus,
} from '@/lib/api/suggestions';
import { ApiError } from '@/lib/api-client';
import type { SuggestionSet, SuggestionItemStatus, ApplySuggestionsResult } from '@/lib/types/suggestion';

type GenerateStatus = 'idle' | 'pending' | 'ready' | 'timeout' | 'error';

interface UseSuggestionsResult {
  suggestionSet: SuggestionSet | null;
  generateStatus: GenerateStatus;
  isApplying: boolean;
  applyError: string | null;
  isVersionConflict: boolean;
  generate: () => Promise<void>;
  applySelected: (acceptedItemIds: string[]) => Promise<ApplySuggestionsResult | null>;
  patchItemStatus: (itemId: string, status: SuggestionItemStatus) => Promise<void>;
}

const POLL_INTERVAL_MS = 2000;
const SOFT_TIMEOUT_MS = 20_000;
const HARD_TIMEOUT_MS = 45_000;

export function useSuggestions(workItemId: string): UseSuggestionsResult {
  const [suggestionSet, setSuggestionSet] = useState<SuggestionSet | null>(null);
  const [generateStatus, setGenerateStatus] = useState<GenerateStatus>('idle');
  const [isApplying, setIsApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [isVersionConflict, setIsVersionConflict] = useState(false);

  const generate = useCallback(async () => {
    setGenerateStatus('pending');
    setApplyError(null);
    setIsVersionConflict(false);

    try {
      const { set_id } = await generateSuggestionSet(workItemId);

      const startedAt = Date.now();
      let done = false;

      while (!done) {
        const elapsed = Date.now() - startedAt;
        if (elapsed >= HARD_TIMEOUT_MS) {
          setGenerateStatus('timeout');
          return;
        }

        await new Promise<void>((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));

        const set = await getSuggestionSet(set_id);
        if (set.status !== 'pending') {
          setSuggestionSet(set);
          setGenerateStatus('ready');
          done = true;
        }
      }
    } catch (err) {
      setGenerateStatus('error');
      setApplyError(err instanceof Error ? err.message : 'Generation failed');
    }
  }, [workItemId]);

  const applySelected = useCallback(
    async (acceptedItemIds: string[]): Promise<ApplySuggestionsResult | null> => {
      if (!suggestionSet) return null;
      setIsApplying(true);
      setApplyError(null);
      setIsVersionConflict(false);
      try {
        const result = await applySuggestions(suggestionSet.id, acceptedItemIds);
        return result;
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          setIsVersionConflict(true);
        } else {
          setApplyError(err instanceof Error ? err.message : 'Apply failed');
        }
        return null;
      } finally {
        setIsApplying(false);
      }
    },
    [suggestionSet],
  );

  const patchItemStatus = useCallback(
    async (itemId: string, status: SuggestionItemStatus) => {
      await updateSuggestionItemStatus(itemId, status);
    },
    [],
  );

  return {
    suggestionSet,
    generateStatus,
    isApplying,
    applyError,
    isVersionConflict,
    generate,
    applySelected,
    patchItemStatus,
  };
}

export { SOFT_TIMEOUT_MS, HARD_TIMEOUT_MS };
