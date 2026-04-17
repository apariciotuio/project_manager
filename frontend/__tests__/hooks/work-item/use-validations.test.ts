import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useValidations } from '@/hooks/work-item/use-validations';

const BASE = 'http://localhost';
const WI_ID = 'wi-1';

const CHECKLIST = {
  required: [
    { rule_id: 'spec_review', label: 'Spec Review', required: true, status: 'pending', passed_at: null, passed_by_review_request_id: null, waived_at: null, waived_by: null },
  ],
  recommended: [
    { rule_id: 'tech_review', label: 'Tech Review', required: false, status: 'pending', passed_at: null, passed_by_review_request_id: null, waived_at: null, waived_by: null },
  ],
};

describe('useValidations', () => {
  it('fetches checklist on mount', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/${WI_ID}/validations`, () =>
        HttpResponse.json({ data: CHECKLIST })
      )
    );

    const { result } = renderHook(() => useValidations(WI_ID));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.checklist?.required).toHaveLength(1);
    expect(result.current.checklist?.recommended).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it('returns error on fetch failure', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/${WI_ID}/validations`, () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'not found' } }, { status: 404 })
      )
    );

    const { result } = renderHook(() => useValidations(WI_ID));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).not.toBeNull();
  });

  it('waive applies optimistic update then refetches', async () => {
    let waiveCalled = false;
    server.use(
      http.get(`${BASE}/api/v1/work-items/${WI_ID}/validations`, () =>
        HttpResponse.json({
          data: {
            required: CHECKLIST.required,
            recommended: [
              { ...CHECKLIST.recommended[0], status: waiveCalled ? 'waived' : 'pending' },
            ],
          },
        })
      ),
      http.post(`${BASE}/api/v1/work-items/${WI_ID}/validations/tech_review/waive`, () => {
        waiveCalled = true;
        return HttpResponse.json({ data: { rule_id: 'tech_review', status: 'waived', waived_at: '2026-01-02T00:00:00Z', waived_by: 'user-1' } });
      })
    );

    const { result } = renderHook(() => useValidations(WI_ID));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.waive('tech_review');
    });

    expect(waiveCalled).toBe(true);
    expect(result.current.checklist?.recommended[0]?.status).toBe('waived');
  });
});
