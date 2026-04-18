/**
 * EP-07 FE Group 7 — skeleton components + diff error retry.
 *
 * - 7.1 VersionDiffViewerSkeleton renders section placeholders (at least 3,
 *   mimicking the shape of a changed section: header line + body lines).
 * - 7.3 CommentFeedSkeleton renders 3 comment placeholders.
 * - 7.6 DiffContent error state shows a retry button; clicking it clears the
 *   error and re-requests the diff.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const BASE = 'http://localhost';

describe('EP-07 Group 7 — skeletons', () => {
  it('VersionDiffViewerSkeleton renders section placeholders (7.1)', async () => {
    const { VersionDiffViewerSkeleton } = await import(
      '@/components/work-item/skeletons'
    );
    const { container } = render(<VersionDiffViewerSkeleton />);

    const placeholders = container.querySelectorAll('.animate-pulse');
    expect(placeholders.length).toBeGreaterThanOrEqual(3);
  });

  it('CommentFeedSkeleton renders 3 comment placeholders (7.3)', async () => {
    const { CommentFeedSkeleton } = await import(
      '@/components/work-item/skeletons'
    );
    const { container } = render(<CommentFeedSkeleton />);

    const commentBlocks = container.querySelectorAll('[data-testid="comment-skeleton-item"]');
    expect(commentBlocks.length).toBe(3);
  });
});

describe('EP-07 Group 7.6 — DiffContent error retry', () => {
  it('renders retry button on error and re-requests on click', async () => {
    let attempts = 0;
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-err/versions/2/diff`, () => {
        attempts += 1;
        if (attempts === 1) {
          return HttpResponse.json(
            { error: { code: 'INTERNAL', message: 'boom' } },
            { status: 500 },
          );
        }
        return HttpResponse.json({
          data: {
            from_version: 1,
            to_version: 2,
            sections_added: [],
            sections_removed: [],
            sections_changed: [
              {
                section_type: 'summary',
                from: 'Old',
                to: 'New after retry',
                diff_lines: ['-Old', '+New after retry'],
              },
            ],
            work_item_changed: false,
            task_nodes_changed: false,
          },
        });
      }),
    );

    const { DiffContent } = await import('@/components/work-item/diff-viewer');
    render(<DiffContent workItemId="wi-err" versionNumber={2} active />);

    const retry = await screen.findByRole('button', { name: /retry|reintentar|diffRetry/i });
    expect(retry).toBeInTheDocument();

    fireEvent.click(retry);

    await waitFor(() => {
      expect(screen.getByText(/New after retry/)).toBeInTheDocument();
    });
    expect(attempts).toBe(2);
  });
});
