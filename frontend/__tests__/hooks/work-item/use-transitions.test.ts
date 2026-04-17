import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useTransitions } from '@/hooks/work-item/use-transitions';

const ROWS = [
  {
    id: 't1',
    work_item_id: 'wi-1',
    from_state: 'draft',
    to_state: 'in_clarification',
    actor_id: 'user-1',
    triggered_at: '2026-02-01T10:00:00Z',
    transition_reason: 'start',
    is_override: false,
    override_justification: null,
  },
];

describe('useTransitions', () => {
  it('fetches rows and reports not-loading', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/transitions', () =>
        HttpResponse.json({ data: ROWS }),
      ),
    );
    const { result } = renderHook(() => useTransitions('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.transitions).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it('captures error on 500 and returns empty list', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/transitions', () =>
        HttpResponse.json({ error: { code: 'INTERNAL_ERROR', message: 'boom' } }, { status: 500 }),
      ),
    );
    const { result } = renderHook(() => useTransitions('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.transitions).toEqual([]);
    expect(result.current.error).not.toBeNull();
  });
});
