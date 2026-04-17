import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { getGapReport, triggerAiReview } from '@/lib/api/gaps';

const BASE = 'http://localhost';

describe('getGapReport', () => {
  it('returns gap report on success', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/gaps`, () =>
        HttpResponse.json({
          data: {
            work_item_id: 'wi-1',
            findings: [
              { dimension: 'acceptance_criteria', severity: 'blocking', message: 'AC missing', source: 'rule' },
            ],
            score: 0.6,
          },
        }),
      ),
    );
    const report = await getGapReport('wi-1');
    expect(report.findings).toHaveLength(1);
    expect(report.score).toBe(0.6);
  });

  it('returns empty stub when endpoint is not found (EP-04 not shipped)', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/gaps`, () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Not found' } }, { status: 404 }),
      ),
    );
    const report = await getGapReport('wi-1');
    expect(report.findings).toEqual([]);
    expect(report.score).toBe(1.0);
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
