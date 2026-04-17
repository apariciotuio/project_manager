import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useReviewRequests } from '@/hooks/work-item/use-review-requests';

const BASE = 'http://localhost';
const WI_ID = 'wi-1';

const REVIEW: import('@/lib/api/reviews').ReviewRequestWithResponses = {
  id: 'rr-1',
  work_item_id: WI_ID,
  version_id: 'v-1',
  reviewer_type: 'user',
  reviewer_id: 'user-2',
  team_id: null,
  validation_rule_id: null,
  status: 'pending',
  requested_by: 'user-1',
  requested_at: '2026-01-01T00:00:00Z',
  cancelled_at: null,
  responses: [],
};

describe('useReviewRequests', () => {
  it('fetches list on mount', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/${WI_ID}/review-requests`, () =>
        HttpResponse.json({ data: [REVIEW] })
      )
    );

    const { result } = renderHook(() => useReviewRequests(WI_ID));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.requests).toHaveLength(1);
    expect(result.current.requests[0]?.id).toBe('rr-1');
    expect(result.current.error).toBeNull();
  });

  it('returns error on fetch failure', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/${WI_ID}/review-requests`, () =>
        HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'Forbidden' } }, { status: 403 })
      )
    );

    const { result } = renderHook(() => useReviewRequests(WI_ID));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).not.toBeNull();
  });

  it('create calls POST and refetches', async () => {
    let postCalled = false;
    server.use(
      http.get(`${BASE}/api/v1/work-items/${WI_ID}/review-requests`, () =>
        HttpResponse.json({ data: postCalled ? [REVIEW] : [] })
      ),
      http.post(`${BASE}/api/v1/work-items/${WI_ID}/review-requests`, () => {
        postCalled = true;
        return HttpResponse.json({ data: REVIEW }, { status: 201 });
      })
    );

    const { result } = renderHook(() => useReviewRequests(WI_ID));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.create({ reviewer_id: 'user-2', version_id: 'v-1' });
    });

    expect(postCalled).toBe(true);
    expect(result.current.requests).toHaveLength(1);
  });

  it('cancel calls DELETE and refetches', async () => {
    let deleteCalled = false;
    server.use(
      http.get(`${BASE}/api/v1/work-items/${WI_ID}/review-requests`, () =>
        HttpResponse.json({ data: deleteCalled ? [] : [REVIEW] })
      ),
      http.delete(`${BASE}/api/v1/review-requests/rr-1`, () => {
        deleteCalled = true;
        return HttpResponse.json({ data: { status: 'cancelled' } });
      })
    );

    const { result } = renderHook(() => useReviewRequests(WI_ID));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.cancel('rr-1');
    });

    expect(deleteCalled).toBe(true);
    expect(result.current.requests).toHaveLength(0);
  });

  it('respond calls POST to response endpoint and refetches', async () => {
    let respondCalled = false;
    server.use(
      http.get(`${BASE}/api/v1/work-items/${WI_ID}/review-requests`, () =>
        HttpResponse.json({ data: [{ ...REVIEW, status: respondCalled ? 'closed' : 'pending' }] })
      ),
      http.post(`${BASE}/api/v1/review-requests/rr-1/response`, () => {
        respondCalled = true;
        return HttpResponse.json({ data: { ...REVIEW, status: 'closed', responses: [{ id: 'resp-1', review_request_id: 'rr-1', responder_id: 'user-2', decision: 'approved', content: null, responded_at: '2026-01-02T00:00:00Z' }] } });
      })
    );

    const { result } = renderHook(() => useReviewRequests(WI_ID));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.respond('rr-1', { decision: 'approved' });
    });

    expect(respondCalled).toBe(true);
    expect(result.current.requests[0]?.status).toBe('closed');
  });
});
