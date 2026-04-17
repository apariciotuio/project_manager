'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  listReviewRequests,
  createReviewRequest,
  cancelReviewRequest,
  submitReviewResponse,
} from '@/lib/api/reviews';
import type {
  ReviewRequestWithResponses,
  CreateReviewRequestBody,
  RespondReviewBody,
} from '@/lib/api/reviews';

interface UseReviewRequestsResult {
  requests: ReviewRequestWithResponses[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  create: (body: CreateReviewRequestBody) => Promise<void>;
  cancel: (requestId: string) => Promise<void>;
  respond: (requestId: string, body: RespondReviewBody) => Promise<void>;
}

export function useReviewRequests(workItemId: string): UseReviewRequestsResult {
  const [requests, setRequests] = useState<ReviewRequestWithResponses[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listReviewRequests(workItemId);
      setRequests(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const create = useCallback(
    async (body: CreateReviewRequestBody) => {
      await createReviewRequest(workItemId, body);
      await refetch();
    },
    [workItemId, refetch],
  );

  const cancel = useCallback(
    async (requestId: string) => {
      await cancelReviewRequest(requestId);
      await refetch();
    },
    [refetch],
  );

  const respond = useCallback(
    async (requestId: string, body: RespondReviewBody) => {
      await submitReviewResponse(requestId, body);
      await refetch();
    },
    [refetch],
  );

  return { requests, isLoading, error, refetch, create, cancel, respond };
}
