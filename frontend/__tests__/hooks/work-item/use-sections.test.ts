import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useSections } from '@/hooks/work-item/use-sections';
import type { Section } from '@/lib/types/specification';

const SECTION_1: Section = {
  id: 'sec-1',
  work_item_id: 'wi-1',
  section_type: 'summary',
  content: 'Login breaks on mobile',
  display_order: 1,
  is_required: true,
  generation_source: 'llm',
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  created_by: 'user-1',
  updated_by: 'user-1',
};

const SECTION_2: Section = {
  id: 'sec-2',
  work_item_id: 'wi-1',
  section_type: 'acceptance_criteria',
  content: '',
  display_order: 2,
  is_required: true,
  generation_source: 'llm',
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  created_by: 'user-1',
  updated_by: 'user-1',
};

describe('useSections', () => {
  it('returns sections on successful fetch', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/specification', () =>
        HttpResponse.json({ data: { work_item_id: 'wi-1', sections: [SECTION_1, SECTION_2] } })
      )
    );

    const { result } = renderHook(() => useSections('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.sections).toHaveLength(2);
    expect(result.current.sections.at(0)?.section_type).toBe('summary');
    expect(result.current.error).toBeNull();
  });

  it('starts in loading state', () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/specification', async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      })
    );

    const { result } = renderHook(() => useSections('wi-1'));
    expect(result.current.isLoading).toBe(true);
  });

  it('returns error on 404', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-404/specification', () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Not found' } }, { status: 404 })
      )
    );

    const { result } = renderHook(() => useSections('wi-404'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.sections).toHaveLength(0);
    expect(result.current.error).not.toBeNull();
  });

  it('optimistically updates section and rolls back on error', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/specification', () =>
        HttpResponse.json({ data: { work_item_id: 'wi-1', sections: [SECTION_1] } })
      ),
      http.patch('http://localhost/api/v1/work-items/wi-1/sections/sec-1', () =>
        HttpResponse.json({ data: { ...SECTION_1, content: 'Updated', generation_source: 'manual', version: 2 } })
      )
    );

    const { result } = renderHook(() => useSections('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.patchSection('sec-1', { content: 'Updated' });
    });

    expect(result.current.sections.at(0)?.content).toBe('Updated');
    expect(result.current.sections.at(0)?.generation_source).toBe('manual');
    expect(result.current.sections.at(0)?.version).toBe(2);
  });

  it('rolls back optimistic update on PATCH error', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/specification', () =>
        HttpResponse.json({ data: { work_item_id: 'wi-1', sections: [SECTION_1] } })
      ),
      http.patch('http://localhost/api/v1/work-items/wi-1/sections/sec-1', () =>
        HttpResponse.json({ error: { code: 'FORBIDDEN' } }, { status: 403 })
      )
    );

    const { result } = renderHook(() => useSections('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await expect(
        result.current.patchSection('sec-1', { content: 'Bad update' })
      ).rejects.toThrow();
    });

    // After rollback refetch, original content is restored
    await waitFor(() =>
      expect(result.current.sections.at(0)?.content).toBe('Login breaks on mobile')
    );
  });

  it('triggers onPatchSuccess callback after successful patch', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/specification', () =>
        HttpResponse.json({ data: { work_item_id: 'wi-1', sections: [SECTION_1] } })
      ),
      http.patch('http://localhost/api/v1/work-items/wi-1/sections/sec-1', () =>
        HttpResponse.json({ data: { ...SECTION_1, content: 'Done' } })
      )
    );

    let called = false;
    const { result } = renderHook(() =>
      useSections('wi-1', { onPatchSuccess: () => { called = true; } })
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.patchSection('sec-1', { content: 'Done' });
    });

    expect(called).toBe(true);
  });
});
