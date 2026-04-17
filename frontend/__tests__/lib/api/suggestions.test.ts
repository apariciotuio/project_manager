import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import {
  generateSuggestionSet,
  getSuggestionSet,
  applySuggestions,
  updateSuggestionItemStatus,
} from '@/lib/api/suggestions';
import { ApiError } from '@/lib/api-client';
import type { SuggestionSet } from '@/lib/types/suggestion';

const BASE = 'http://localhost';

const mockSet: SuggestionSet = {
  id: 'batch-1',
  work_item_id: 'wi-1',
  status: 'pending',
  created_at: '2026-04-17T10:00:00Z',
  expires_at: '2026-04-18T10:00:00Z',
  items: [
    {
      id: 'item-1',
      section: 'acceptance_criteria',
      current_content: 'Old AC',
      proposed_content: 'New AC',
      rationale: 'More specific',
      status: 'pending',
    },
  ],
};

describe('generateSuggestionSet', () => {
  it('returns set_id on success', async () => {
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/suggestion-sets`, () =>
        HttpResponse.json({ data: { set_id: 'batch-1' } }),
      ),
    );
    const result = await generateSuggestionSet('wi-1');
    expect(result.set_id).toBe('batch-1');
  });
});

describe('getSuggestionSet', () => {
  it('returns a suggestion set', async () => {
    server.use(
      http.get(`${BASE}/api/v1/suggestion-sets/batch-1`, () =>
        HttpResponse.json({ data: mockSet }),
      ),
    );
    const result = await getSuggestionSet('batch-1');
    expect(result.id).toBe('batch-1');
    expect(result.items).toHaveLength(1);
  });
});

describe('applySuggestions', () => {
  it('returns apply result on success', async () => {
    server.use(
      http.post(`${BASE}/api/v1/suggestion-sets/batch-1/apply`, () =>
        HttpResponse.json({ data: { new_version: 2, applied_sections: ['acceptance_criteria'] } }),
      ),
    );
    const result = await applySuggestions('batch-1', ['item-1']);
    expect(result.new_version).toBe(2);
    expect(result.applied_sections).toContain('acceptance_criteria');
  });

  it('throws ApiError(409) on version conflict', async () => {
    server.use(
      http.post(`${BASE}/api/v1/suggestion-sets/batch-1/apply`, () =>
        HttpResponse.json(
          { error: { code: 'CONFLICT', message: 'Version conflict' } },
          { status: 409 },
        ),
      ),
    );
    await expect(applySuggestions('batch-1', ['item-1'])).rejects.toBeInstanceOf(ApiError);
    try {
      await applySuggestions('batch-1', ['item-1']);
    } catch (err) {
      expect((err as ApiError).status).toBe(409);
    }
  });
});

describe('updateSuggestionItemStatus', () => {
  it('calls PATCH without throwing', async () => {
    server.use(
      http.patch(`${BASE}/api/v1/suggestion-items/item-1`, () =>
        new HttpResponse(null, { status: 204 }),
      ),
    );
    await expect(updateSuggestionItemStatus('item-1', 'accepted')).resolves.toBeUndefined();
  });
});
