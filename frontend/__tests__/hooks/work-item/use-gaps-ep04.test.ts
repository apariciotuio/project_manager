/**
 * EP-04 — tests for the updated useGaps hook against the real endpoint.
 * The old stub (getGapReport returning { findings: [], score: 1.0 }) is replaced.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useGaps } from '@/hooks/work-item/use-gaps';

const GAPS_RESPONSE = {
  data: [
    { dimension: 'acceptance_criteria', message: 'Define at least 2 ACs.', severity: 'blocking' },
    { dimension: 'solution_description', message: 'Add a solution description.', severity: 'warning' },
  ],
};

describe('useGaps (EP-04 real endpoint)', () => {
  it('returns gap items on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/gaps', () =>
        HttpResponse.json(GAPS_RESPONSE)
      )
    );

    const { result } = renderHook(() => useGaps('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.gapReport?.findings).toHaveLength(2);
    expect(result.current.gapReport?.findings.at(0)?.severity).toBe('blocking');
    expect(result.current.gapReport?.findings.at(0)?.dimension).toBe('acceptance_criteria');
    expect(result.current.error).toBeNull();
  });

  it('returns empty findings when no gaps', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-2/gaps', () =>
        HttpResponse.json({ data: [] })
      )
    );

    const { result } = renderHook(() => useGaps('wi-2'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.gapReport?.findings).toHaveLength(0);
  });

  it('returns error on network failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-err/gaps', () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND' } }, { status: 404 })
      )
    );

    const { result } = renderHook(() => useGaps('wi-err'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.gapReport).toBeNull();
    expect(result.current.error).not.toBeNull();
  });
});
