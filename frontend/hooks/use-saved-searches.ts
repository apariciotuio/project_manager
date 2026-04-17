'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  listSavedSearches,
  createSavedSearch,
  updateSavedSearch,
  deleteSavedSearch,
} from '@/lib/api/saved-searches';
import type { SavedSearch } from '@/lib/types/work-item';
import type { CreateSavedSearchRequest, UpdateSavedSearchRequest } from '@/lib/api/saved-searches';

interface UseSavedSearchesResult {
  searches: SavedSearch[];
  isLoading: boolean;
  error: Error | null;
  create: (data: CreateSavedSearchRequest) => Promise<SavedSearch>;
  update: (id: string, data: UpdateSavedSearchRequest) => Promise<SavedSearch>;
  remove: (id: string) => Promise<void>;
}

/**
 * EP-09 — Hook for managing saved searches.
 * Optimistic updates: add/remove from local state before server confirmation.
 */
export function useSavedSearches(): UseSavedSearchesResult {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const data = await listSavedSearches();
        if (!cancelled) setSearches(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const create = useCallback(async (data: CreateSavedSearchRequest): Promise<SavedSearch> => {
    const created = await createSavedSearch(data);
    setSearches((prev) => [...prev, created]);
    return created;
  }, []);

  const update = useCallback(async (id: string, data: UpdateSavedSearchRequest): Promise<SavedSearch> => {
    const updated = await updateSavedSearch(id, data);
    setSearches((prev) => prev.map((s) => (s.id === id ? updated : s)));
    return updated;
  }, []);

  const remove = useCallback(async (id: string): Promise<void> => {
    // Optimistic remove
    setSearches((prev) => prev.filter((s) => s.id !== id));
    try {
      await deleteSavedSearch(id);
    } catch (err) {
      // Revert on failure
      const reverted = await listSavedSearches().catch(() => []);
      setSearches(reverted);
      throw err;
    }
  }, []);

  return { searches, isLoading, error, create, update, remove };
}
