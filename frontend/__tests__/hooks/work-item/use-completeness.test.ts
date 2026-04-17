import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useCompleteness } from '@/hooks/work-item/use-completeness';

describe('useCompleteness', () => {
  it('returns score and dimensions on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/completeness', () =>
        HttpResponse.json({
          data: {
            score: 65,
            level: 'medium',
            dimensions: [
              { name: 'problem', score: 80, weight: 0.3, label: 'Problema' },
              { name: 'solution', score: 50, weight: 0.3, label: 'Solución' },
            ],
          },
        })
      )
    );

    const { result } = renderHook(() => useCompleteness('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.completeness?.score).toBe(65);
    expect(result.current.completeness?.level).toBe('medium');
    expect(result.current.completeness?.dimensions).toHaveLength(2);
  });

  it('returns null on error', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-404/completeness', () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Not found' } }, { status: 404 })
      )
    );

    const { result } = renderHook(() => useCompleteness('wi-404'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.completeness).toBeNull();
    expect(result.current.error).not.toBeNull();
  });
});
