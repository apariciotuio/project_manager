import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useSpecification } from '@/hooks/work-item/use-specification';
import type { Section } from '@/lib/types/work-item-detail';

const SECTIONS: Section[] = [
  {
    id: 'sec-1',
    section_type: 'problem_statement',
    content: 'The login fails on mobile',
    order: 0,
    is_required: true,
    last_updated_at: '2026-01-01T00:00:00Z',
    last_updated_by: 'user-1',
  },
  {
    id: 'sec-2',
    section_type: 'acceptance_criteria',
    content: null,
    order: 1,
    is_required: true,
    last_updated_at: null,
    last_updated_by: null,
  },
];

describe('useSpecification', () => {
  it('returns sections on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/specification', () =>
        HttpResponse.json({ data: { sections: SECTIONS } })
      )
    );

    const { result } = renderHook(() => useSpecification('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.sections).toHaveLength(2);
    expect(result.current.sections.at(0)?.section_type).toBe('problem_statement');
  });

  it('optimistically updates section content', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/specification', () =>
        HttpResponse.json({ data: { sections: SECTIONS } })
      ),
      http.patch('http://localhost/api/v1/work-items/wi-1/sections/sec-1', () =>
        HttpResponse.json({ data: { ...SECTIONS[0], content: 'Updated content' } })
      )
    );

    const { result } = renderHook(() => useSpecification('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await result.current.updateSection('sec-1', 'Updated content');

    await waitFor(() =>
      expect(result.current.sections.at(0)?.content).toBe('Updated content')
    );
  });
});
