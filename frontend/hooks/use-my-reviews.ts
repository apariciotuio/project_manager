'use client';

import { useState, useEffect, useCallback } from 'react';
import { listMyPendingReviews } from '@/lib/api/reviews';
import type { ReviewRequest } from '@/lib/api/reviews';

interface UseMyReviewsResult {
  reviews: ReviewRequest[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useMyReviews(): UseMyReviewsResult {
  const [reviews, setReviews] = useState<ReviewRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listMyPendingReviews();
      setReviews(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { reviews, isLoading, error, refetch };
}
