import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { SpecificationSectionsEditor } from '@/components/work-item/specification-sections-editor';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

const BASE = 'http://localhost';

const SECTION_SUMMARY = {
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

const SECTION_AC = {
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

function setupSpecHandler(sections = [SECTION_SUMMARY, SECTION_AC]) {
  server.use(
    http.get(`${BASE}/api/v1/work-items/wi-1/specification`, () =>
      HttpResponse.json({ data: { work_item_id: 'wi-1', sections } })
    )
  );
}

describe('SpecificationSectionsEditor', () => {
  it('renders skeleton while loading', () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/specification`, async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      })
    );
    render(<SpecificationSectionsEditor workItemId="wi-1" canEdit={true} />);
    expect(document.querySelectorAll('[data-testid="section-skeleton"]').length).toBeGreaterThan(0);
  });

  it('renders all sections after load', async () => {
    setupSpecHandler();
    render(<SpecificationSectionsEditor workItemId="wi-1" canEdit={true} />);

    await waitFor(() => expect(screen.getByDisplayValue('Login breaks on mobile')).toBeInTheDocument());
    // Two textareas rendered
    expect(screen.getAllByRole('textbox')).toHaveLength(2);
  });

  it('textareas are read-only when canEdit is false', async () => {
    setupSpecHandler();
    render(<SpecificationSectionsEditor workItemId="wi-1" canEdit={false} />);

    await waitFor(() => expect(screen.getByDisplayValue('Login breaks on mobile')).toBeInTheDocument());
    const textareas = screen.getAllByRole('textbox') as HTMLTextAreaElement[];
    textareas.forEach((ta) => expect(ta.disabled).toBe(true));
  });

  it('shows saving indicator while patch is in-flight', async () => {
    setupSpecHandler();
    server.use(
      http.patch(`${BASE}/api/v1/work-items/wi-1/sections/sec-1`, async () => {
        await new Promise((r) => setTimeout(r, 200));
        return HttpResponse.json({ data: { ...SECTION_SUMMARY, content: 'New content', generation_source: 'manual', version: 2 } });
      })
    );

    render(<SpecificationSectionsEditor workItemId="wi-1" canEdit={true} />);
    await waitFor(() => expect(screen.getByDisplayValue('Login breaks on mobile')).toBeInTheDocument());

    // Trigger save via blur (no debounce in tests)
    const ta = screen.getByDisplayValue('Login breaks on mobile') as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: 'New content' } });
    fireEvent.blur(ta);

    await waitFor(() =>
      expect(screen.getByTestId('saving-indicator-sec-1')).toBeInTheDocument()
    );
  });

  it('shows generation_source badge per section', async () => {
    setupSpecHandler();
    render(<SpecificationSectionsEditor workItemId="wi-1" canEdit={true} />);

    await waitFor(() => expect(screen.getByDisplayValue('Login breaks on mobile')).toBeInTheDocument());
    // Both sections have generation_source: 'llm'
    expect(screen.getAllByTestId('generation-badge').length).toBeGreaterThan(0);
  });

  it('shows section label', async () => {
    setupSpecHandler();
    render(<SpecificationSectionsEditor workItemId="wi-1" canEdit={true} />);

    await waitFor(() =>
      expect(screen.getByText('workspace.itemDetail.specification.sectionLabels.summary')).toBeInTheDocument()
    );
  });
});
