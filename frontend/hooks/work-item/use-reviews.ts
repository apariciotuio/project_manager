'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api-client';
import type {
  ReviewResponse,
  ReviewsListResponse,
  RequestReviewRequest,
} from '@/lib/types/work-item-detail';

interface UseReviewsResult {
  reviews: ReviewResponse[];
  isLoading: boolean;
  error: Error | null;
  requestReview: (req: RequestReviewRequest) => Promise<void>;
  refetch: () => void;
}

export function useReviews(workItemId: string): UseReviewsResult {
  const [reviews, setReviews] = useState<ReviewResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiGet<ReviewsListResponse>(
        `/api/v1/work-items/${workItemId}/reviews`
      );
      setReviews(res.data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  const requestReview = useCallback(
    async (req: RequestReviewRequest) => {
      await apiPost<{ data: ReviewResponse }>(
        `/api/v1/work-items/${workItemId}/reviews`,
        req
      );
      await fetch();
    },
    [workItemId, fetch]
  );

  return { reviews, isLoading, error, requestReview, refetch: fetch };
}
