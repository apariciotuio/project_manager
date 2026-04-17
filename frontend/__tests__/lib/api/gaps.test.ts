import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { getGapReport, triggerAiReview } from '@/lib/api/gaps';

const BASE = 'http://localhost';

describe('getGapReport', () => {
  it('returns gap report on success (EP-04 array format)', async () => {
    // EP-04 endpoint returns { data: GapItem[] } — array directly in data
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/gaps`, () =>
        HttpResponse.json({
          data: [
            { dimension: 'acceptance_criteria', severity: 'blocking', message: 'AC missing' },
          ],
        }),
      ),
    );
    const report = await getGapReport('wi-1');
    expect(report.findings).toHaveLength(1);
    expect(report.findings[0]!.dimension).toBe('acceptance_criteria');
    expect(report.findings[0]!.severity).toBe('blocking');
  });

  it('returns empty findings when no gaps', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-2/gaps`, () =>
        HttpResponse.json({ data: [] }),
      ),
    );
    const report = await getGapReport('wi-2');
    expect(report.findings).toEqual([]);
    expect(report.score).toBe(1.0);
  });

  it('throws on network error (EP-04 endpoint live — no stub)', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-err/gaps`, () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Not found' } }, { status: 404 }),
      ),
    );
    await expect(getGapReport('wi-err')).rejects.toThrow();
  });
});

describe('triggerAiReview', () => {
  it('returns job_id on success', async () => {
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/gaps/ai-review`, () =>
        HttpResponse.json({ data: { job_id: 'job-1' } }),
      ),
    );
    const result = await triggerAiReview('wi-1');
    expect(result.job_id).toBe('job-1');
  });
});
