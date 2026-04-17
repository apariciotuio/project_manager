import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useReviews } from '@/hooks/work-item/use-reviews';

const REVIEWS = [
  {
    id: 'rev-1',
    reviewer_id: 'user-2',
    reviewer_name: 'Alice',
    status: 'pending',
    requested_at: '2026-01-01T00:00:00Z',
    responses: [],
  },
];

describe('useReviews', () => {
  it('returns reviews on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/reviews', () =>
        HttpResponse.json({ data: REVIEWS })
      )
    );

    const { result } = renderHook(() => useReviews('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.reviews).toHaveLength(1);
    expect(result.current.reviews.at(0)?.reviewer_name).toBe('Alice');
  });

  it('requests a review and refreshes', async () => {
    const newReview = {
      id: 'rev-2',
      reviewer_id: 'user-3',
      reviewer_name: 'Bob',
      status: 'pending',
      requested_at: '2026-01-02T00:00:00Z',
      responses: [],
    };

    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/reviews', () =>
        HttpResponse.json({ data: REVIEWS })
      ),
      http.post('http://localhost/api/v1/work-items/wi-1/reviews', () =>
        HttpResponse.json({ data: newReview })
      )
    );

    const { result } = renderHook(() => useReviews('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/reviews', () =>
        HttpResponse.json({ data: [...REVIEWS, newReview] })
      )
    );

    await result.current.requestReview({ reviewer_id: 'user-3' });

    await waitFor(() => expect(result.current.reviews).toHaveLength(2));
  });
});
