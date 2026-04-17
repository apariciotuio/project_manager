import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useNextStep } from '@/hooks/work-item/use-next-step';

const NEXT_STEP_RESPONSE = {
  data: {
    next_step: 'fill_blocking_gaps',
    message: 'Fill blocking gaps to proceed.',
    blocking: true,
    gaps_referenced: ['acceptance_criteria'],
    suggested_validators: [
      { role: 'product_owner', reason: 'Required', configured: true },
      { role: 'tech_lead', reason: 'Recommended', configured: false, setup_hint: 'Configure in settings.' },
    ],
  },
};

describe('useNextStep', () => {
  it('returns next step result on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/next-step', () =>
        HttpResponse.json(NEXT_STEP_RESPONSE)
      )
    );

    const { result } = renderHook(() => useNextStep('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.nextStep?.next_step).toBe('fill_blocking_gaps');
    expect(result.current.nextStep?.blocking).toBe(true);
    expect(result.current.nextStep?.suggested_validators).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });

  it('starts in loading state', () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/next-step', async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      })
    );

    const { result } = renderHook(() => useNextStep('wi-1'));
    expect(result.current.isLoading).toBe(true);
  });

  it('returns null next step when terminal state', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-2/next-step', () =>
        HttpResponse.json({
          data: {
            next_step: null,
            message: 'Item has been exported.',
            blocking: false,
            gaps_referenced: [],
            suggested_validators: [],
          },
        })
      )
    );

    const { result } = renderHook(() => useNextStep('wi-2'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.nextStep?.next_step).toBeNull();
    expect(result.current.nextStep?.blocking).toBe(false);
  });

  it('returns error on 404', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-404/next-step', () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND' } }, { status: 404 })
      )
    );

    const { result } = renderHook(() => useNextStep('wi-404'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.nextStep).toBeNull();
    expect(result.current.error).not.toBeNull();
  });
});
