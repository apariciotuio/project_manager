'use client';

import { useState, useEffect, useCallback } from 'react';
import { listAttachments, deleteAttachment } from '@/lib/api/attachments';
import type { AttachmentResponse } from '@/lib/types/attachment';

interface UseAttachmentsResult {
  attachments: AttachmentResponse[];
  isLoading: boolean;
  error: Error | null;
  deleteOne: (id: string) => Promise<void>;
  refetch: () => void;
}

export function useAttachments(workItemId: string): UseAttachmentsResult {
  const [attachments, setAttachments] = useState<AttachmentResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listAttachments(workItemId);
      setAttachments(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  const deleteOne = useCallback(
    async (id: string) => {
      await deleteAttachment(id);
      setAttachments((prev) => prev.filter((a) => a.id !== id));
    },
    [],
  );

  return { attachments, isLoading, error, deleteOne, refetch: fetch };
}
