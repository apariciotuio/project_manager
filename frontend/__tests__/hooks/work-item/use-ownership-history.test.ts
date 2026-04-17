import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useOwnershipHistory } from '@/hooks/work-item/use-ownership-history';

const ROWS = [
  {
    id: 'o1',
    work_item_id: 'wi-1',
    previous_owner_id: 'user-1',
    new_owner_id: 'user-2',
    changed_by: 'user-1',
    changed_at: '2026-02-02T10:00:00Z',
    reason: 'On leave',
  },
];

describe('useOwnershipHistory', () => {
  it('fetches rows and reports not-loading', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/ownership-history', () =>
        HttpResponse.json({ data: ROWS }),
      ),
    );
    const { result } = renderHook(() => useOwnershipHistory('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.history).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it('captures error on 500', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/ownership-history', () =>
        HttpResponse.json({ error: { code: 'INTERNAL_ERROR', message: 'boom' } }, { status: 500 }),
      ),
    );
    const { result } = renderHook(() => useOwnershipHistory('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.history).toEqual([]);
    expect(result.current.error).not.toBeNull();
  });
});
