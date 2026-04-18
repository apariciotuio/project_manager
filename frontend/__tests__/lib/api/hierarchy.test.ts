/**
 * FE-14-01 — Hierarchy API client tests.
 * RED phase: all tests fail until hierarchy-api.ts is implemented.
 */
import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import {
  getProjectHierarchy,
  getWorkItemChildren,
  getWorkItemAncestors,
  getWorkItemRollup,
} from '@/lib/api/hierarchy';
import type {
  HierarchyPage,
  WorkItemSummary,
  AncestorChain,
  RollupResult,
} from '@/lib/types/hierarchy';

const BASE = 'http://localhost';

// --- types ------------------------------------------------------------------

describe('hierarchy types', () => {
  it('HierarchyPage has roots, unparented and meta fields', () => {
    const page: HierarchyPage = {
      roots: [],
      unparented: [],
      meta: { truncated: false, next_cursor: null },
    };
    expect(page.roots).toEqual([]);
    expect(page.meta.truncated).toBe(false);
  });

  it('WorkItemSummary has id, title, type, state and parent_work_item_id', () => {
    const s: WorkItemSummary = {
      id: 'abc',
      title: 'Test',
      type: 'story',
      state: 'draft',
      parent_work_item_id: null,
      materialized_path: '',
    };
    expect(s.type).toBe('story');
    expect(s.materialized_path).toBe('');
  });

  it('AncestorChain is an array of WorkItemSummary', () => {
    const chain: AncestorChain = [
      { id: 'm1', title: 'Milestone', type: 'milestone', state: 'ready', parent_work_item_id: null, materialized_path: '' },
      { id: 'e1', title: 'Epic', type: 'initiative', state: 'draft', parent_work_item_id: 'm1', materialized_path: 'm1' },
    ];
    expect(chain).toHaveLength(2);
    expect(chain[0]!.type).toBe('milestone');
  });

  it('RollupResult has percent (number | null) and stale flag', () => {
    const r: RollupResult = { percent: 67, stale: false };
    expect(r.percent).toBe(67);
    const nullRollup: RollupResult = { percent: null, stale: false };
    expect(nullRollup.percent).toBeNull();
  });
});

// --- getProjectHierarchy ----------------------------------------------------

describe('getProjectHierarchy', () => {
  it('returns HierarchyPage on success', async () => {
    server.use(
      http.get(`${BASE}/api/v1/projects/proj-1/hierarchy`, () =>
        HttpResponse.json({
          data: {
            roots: [
              {
                id: 'm1', title: 'M1', type: 'milestone', state: 'draft',
                parent_work_item_id: null, materialized_path: '',
                children: [],
              },
            ],
            unparented: [],
            meta: { truncated: false, next_cursor: null },
          },
        }),
      ),
    );
    const page = await getProjectHierarchy('proj-1');
    expect(page.roots).toHaveLength(1);
    expect(page.roots[0]!.type).toBe('milestone');
    expect(page.meta.truncated).toBe(false);
  });

  it('passes cursor as query param when provided', async () => {
    let receivedCursor: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/projects/proj-2/hierarchy`, ({ request }) => {
        const url = new URL(request.url);
        receivedCursor = url.searchParams.get('cursor');
        return HttpResponse.json({
          data: { roots: [], unparented: [], meta: { truncated: false, next_cursor: null } },
        });
      }),
    );
    await getProjectHierarchy('proj-2', 'cursor-abc');
    expect(receivedCursor).toBe('cursor-abc');
  });

  it('throws on 404', async () => {
    server.use(
      http.get(`${BASE}/api/v1/projects/missing/hierarchy`, () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Not found' } }, { status: 404 }),
      ),
    );
    await expect(getProjectHierarchy('missing')).rejects.toThrow();
  });
});

// --- getWorkItemChildren -----------------------------------------------------

describe('getWorkItemChildren', () => {
  it('returns paged children on success', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/children`, () =>
        HttpResponse.json({
          data: {
            items: [
              { id: 'c1', title: 'Child', type: 'story', state: 'draft', parent_work_item_id: 'wi-1', materialized_path: 'wi-1' },
            ],
            total: 1,
            cursor: null,
            has_next: false,
          },
        }),
      ),
    );
    const result = await getWorkItemChildren('wi-1');
    expect(result.items).toHaveLength(1);
    expect(result.items[0]!.type).toBe('story');
    expect(result.has_next).toBe(false);
  });

  it('passes pagination params', async () => {
    let receivedParams: Record<string, string> = {};
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-2/children`, ({ request }) => {
        const url = new URL(request.url);
        receivedParams = Object.fromEntries(url.searchParams.entries());
        return HttpResponse.json({ data: { items: [], total: 0, cursor: null, has_next: false } });
      }),
    );
    await getWorkItemChildren('wi-2', { cursor: 'c99', limit: 20 });
    expect(receivedParams['cursor']).toBe('c99');
    expect(receivedParams['limit']).toBe('20');
  });
});

// --- getWorkItemAncestors ----------------------------------------------------

describe('getWorkItemAncestors', () => {
  it('returns AncestorChain on success', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-3/ancestors`, () =>
        HttpResponse.json({
          data: [
            { id: 'm1', title: 'M1', type: 'milestone', state: 'ready', parent_work_item_id: null, materialized_path: '' },
          ],
        }),
      ),
    );
    const chain = await getWorkItemAncestors('wi-3');
    expect(chain).toHaveLength(1);
    expect(chain[0]!.id).toBe('m1');
  });

  it('returns empty array when no ancestors', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-root/ancestors`, () =>
        HttpResponse.json({ data: [] }),
      ),
    );
    const chain = await getWorkItemAncestors('wi-root');
    expect(chain).toEqual([]);
  });
});

// --- getWorkItemRollup -------------------------------------------------------

describe('getWorkItemRollup', () => {
  it('returns RollupResult with percent when available', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-4/rollup`, () =>
        HttpResponse.json({ data: { percent: 67, stale: false } }),
      ),
    );
    const result = await getWorkItemRollup('wi-4');
    expect(result.percent).toBe(67);
    expect(result.stale).toBe(false);
  });

  it('returns null percent for leaf nodes', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-leaf/rollup`, () =>
        HttpResponse.json({ data: { percent: null, stale: false } }),
      ),
    );
    const result = await getWorkItemRollup('wi-leaf');
    expect(result.percent).toBeNull();
  });

  it('returns stale=true when rollup cache is stale', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-stale/rollup`, () =>
        HttpResponse.json({ data: { percent: 50, stale: true } }),
      ),
    );
    const result = await getWorkItemRollup('wi-stale');
    expect(result.stale).toBe(true);
  });
});
