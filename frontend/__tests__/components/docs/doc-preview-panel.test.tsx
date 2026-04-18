import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { DocPreviewPanel } from '@/components/docs/doc-preview-panel';
import type { DocContent } from '@/lib/types/search';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const BASE = 'http://localhost';

const mockContent: DocContent = {
  doc_id: 'doc-1',
  title: 'Architecture Overview',
  content_html: '<h1>Architecture</h1><p>System design details.</p>',
  url: 'https://wiki.example.com/arch',
  source_name: 'Confluence',
  last_indexed_at: '2026-04-17T12:00:00Z',
  content_truncated: false,
};

function stubDocContent(docId: string, content: DocContent = mockContent) {
  server.use(
    http.get(`${BASE}/api/v1/docs/${docId}/content`, () =>
      HttpResponse.json({ data: content }),
    ),
  );
}

describe('DocPreviewPanel', () => {
  it('is not visible when isOpen is false', () => {
    render(<DocPreviewPanel docId="doc-1" isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('becomes visible when isOpen is true', async () => {
    stubDocContent('doc-1');
    render(<DocPreviewPanel docId="doc-1" isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('fetches and renders doc content when opened', async () => {
    stubDocContent('doc-1');
    render(<DocPreviewPanel docId="doc-1" isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByText('Architecture Overview')).toBeInTheDocument());
    expect(screen.getByText('Confluence')).toBeInTheDocument();
  });

  it('renders content_html inside the panel', async () => {
    stubDocContent('doc-1');
    render(<DocPreviewPanel docId="doc-1" isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByTestId('doc-content-body')).toBeInTheDocument());
    expect(screen.getByTestId('doc-content-body').innerHTML).toContain('Architecture');
  });

  it('Open in new tab link has correct href and target', async () => {
    stubDocContent('doc-1');
    render(<DocPreviewPanel docId="doc-1" isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByText('Architecture Overview')).toBeInTheDocument());
    const link = screen.getByRole('link', { name: /openInNewTab/i });
    expect(link).toHaveAttribute('href', 'https://wiki.example.com/arch');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('close button calls onClose', async () => {
    stubDocContent('doc-1');
    const onClose = vi.fn();
    render(<DocPreviewPanel docId="doc-1" isOpen={true} onClose={onClose} />);

    await userEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows content_truncated notice when flag is true', async () => {
    const truncated: DocContent = { ...mockContent, content_truncated: true };
    stubDocContent('doc-trunc', truncated);
    render(<DocPreviewPanel docId="doc-trunc" isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByTestId('content-truncated-notice')).toBeInTheDocument());
  });

  it('does not render doc content when docId is null', () => {
    render(<DocPreviewPanel docId={null} isOpen={true} onClose={vi.fn()} />);
    expect(screen.queryByTestId('doc-content-body')).not.toBeInTheDocument();
  });
});
