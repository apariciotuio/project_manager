'use client';

import { useState, useEffect, useCallback } from 'react';
import { getThreads, createThread, getThreadHistory } from '@/lib/api/threads';
import type { ConversationThread, ConversationMessage } from '@/lib/types/conversation';

interface UseThreadResult {
  thread: ConversationThread | null;
  messages: ConversationMessage[];
  isLoading: boolean;
  error: Error | null;
  refetchHistory: () => void;
}

/**
 * Resolves or creates the element thread for a work item,
 * then fetches its message history.
 */
export function useThread(workItemId: string): UseThreadResult {
  const [thread, setThread] = useState<ConversationThread | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchHistory = useCallback(async (t: ConversationThread) => {
    try {
      const history = await getThreadHistory(t.id);
      setMessages(history);
    } catch (err) {
      // History fetch failure is non-fatal; keep thread available
      console.warn('[useThread] history fetch failed', err);
    }
  }, []);

  const init = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const threads = await getThreads(workItemId);
      let t = threads[0] ?? null;
      if (!t) {
        t = await createThread({ work_item_id: workItemId });
      }
      setThread(t);
      await fetchHistory(t);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId, fetchHistory]);

  useEffect(() => {
    void init();
  }, [init]);

  const refetchHistory = useCallback(() => {
    if (thread) void fetchHistory(thread);
  }, [thread, fetchHistory]);

  return { thread, messages, isLoading, error, refetchHistory };
}
