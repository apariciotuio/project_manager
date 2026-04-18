import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { RelatedDocsWidget } from '@/components/docs/related-docs-widget';
import type { RelatedDoc } from '@/lib/types/search';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const BASE = 'http://localhost';

const mockDocs: RelatedDoc[] = [
  {
    doc_id: 'doc-1',
    title: 'Auth Flow',
    source_name: 'Confluence',
    snippet: 'How authentication works.',
    url: 'https://wiki.example.com/auth',
    score: 0.95,
  },
  {
    doc_id: 'doc-2',
    title: 'DB Schema',
    source_name: 'Notion',
    snippet: 'Database schema overview.',
    url: 'https://notion.example.com/db',
    score: 0.87,
  },
];

function stubRelatedDocs(workItemId: string, docs: RelatedDoc[] = mockDocs, status = 200) {
  server.use(
    http.get(`${BASE}/api/v1/work-items/${workItemId}/related-docs`, () =>
      status === 200
        ? HttpResponse.json({ data: docs })
        : HttpResponse.json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Puppet down' } }, { status }),
    ),
  );
}

describe('RelatedDocsWidget', () => {
  it('renders the widget section heading', async () => {
    stubRelatedDocs('wi-1');
    render(<RelatedDocsWidget workItemId="wi-1" onDocPreview={vi.fn()} />);
    expect(screen.getByRole('heading', { name: /title/i })).toBeInTheDocument();
  });

  it('fetches and renders related docs after mount', async () => {
    stubRelatedDocs('wi-1');
    render(<RelatedDocsWidget workItemId="wi-1" onDocPreview={vi.fn()} />);

    await waitFor(() => expect(screen.getByText('Auth Flow')).toBeInTheDocument());
    expect(screen.getByText('DB Schema')).toBeInTheDocument();
  });

  it('renders no more than 5 docs', async () => {
    const manyDocs: RelatedDoc[] = Array.from({ length: 7 }, (_, i) => ({
      doc_id: `doc-${i}`,
      title: `Doc ${i}`,
      source_name: 'Confluence',
      snippet: `Snippet ${i}`,
      url: `https://wiki.example.com/doc-${i}`,
      score: 0.9,
    }));
    stubRelatedDocs('wi-2', manyDocs);
    render(<RelatedDocsWidget workItemId="wi-2" onDocPreview={vi.fn()} />);

    await waitFor(() => expect(screen.getAllByRole('button')).toHaveLength(5));
  });

  it('shows empty message on empty response', async () => {
    stubRelatedDocs('wi-3', []);
    render(<RelatedDocsWidget workItemId="wi-3" onDocPreview={vi.fn()} />);

    await waitFor(() => expect(screen.getByTestId('no-related-docs')).toBeInTheDocument());
  });

  it('shows empty message on error — no error state visible', async () => {
    stubRelatedDocs('wi-err', mockDocs, 503);
    render(<RelatedDocsWidget workItemId="wi-err" onDocPreview={vi.fn()} />);

    await waitFor(() => expect(screen.getByTestId('no-related-docs')).toBeInTheDocument());
    // Error state should NOT be shown — silent degradation
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('clicking a doc calls onDocPreview with correct docId', async () => {
    stubRelatedDocs('wi-click');
    const onDocPreview = vi.fn();
    render(<RelatedDocsWidget workItemId="wi-click" onDocPreview={onDocPreview} />);

    await waitFor(() => expect(screen.getByText('Auth Flow')).toBeInTheDocument());
    await userEvent.click(screen.getAllByRole('button')[0]!);
    expect(onDocPreview).toHaveBeenCalledWith('doc-1');
  });
});
