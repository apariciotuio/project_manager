/**
 * EP-07 FE Group 6.3 — CommentCountBadge + CommentsProvider.
 *
 * - Badge reads comments.length from context.
 * - Optimistic addComment increments the shared count without page reload
 *   (i.e., CommentsTab's form submission updates the badge that lives
 *   outside TabsContent).
 * - Badge renders nothing when count === 0 (avoids an empty visual chip).
 * - Badge returns null when rendered without a CommentsProvider (dual-mode
 *   safety — CommentsTab's standalone variant must still work in isolation).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import type { Comment } from '@/lib/types/versions';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const BASE = 'http://localhost';

function makeComment(overrides: Partial<Comment> = {}): Comment {
  return {
    id: overrides.id ?? 'c-1',
    work_item_id: 'wi-1',
    parent_comment_id: null,
    actor_type: 'human',
    actor_id: 'user-1',
    body: 'hello',
    anchor: null,
    anchor_status: 'valid',
    deleted_at: null,
    edited_at: null,
    created_at: '2026-04-17T10:00:00Z',
    updated_at: '2026-04-17T10:00:00Z',
    replies: [],
    ...overrides,
  } as Comment;
}

describe('CommentCountBadge', () => {
  it('returns null when rendered without a CommentsProvider (6.3 dual-mode safety)', async () => {
    const { CommentCountBadge } = await import(
      '@/components/work-item/comment-count-badge'
    );
    const { container } = render(<CommentCountBadge />);
    expect(container.firstChild).toBeNull();
  });

  it('shows count from context (6.3 core)', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/comments`, () =>
        HttpResponse.json({
          data: [makeComment({ id: 'c-1' }), makeComment({ id: 'c-2' })],
        }),
      ),
    );

    const { CommentsProvider } = await import(
      '@/components/work-item/comments-context'
    );
    const { CommentCountBadge } = await import(
      '@/components/work-item/comment-count-badge'
    );

    render(
      <CommentsProvider workItemId="wi-1">
        <CommentCountBadge />
      </CommentsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('comment-count-badge')).toHaveTextContent('2');
    });
  });

  it('does not render when count is 0 (empty state hides badge)', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-empty/comments`, () =>
        HttpResponse.json({ data: [] }),
      ),
    );

    const { CommentsProvider } = await import(
      '@/components/work-item/comments-context'
    );
    const { CommentCountBadge } = await import(
      '@/components/work-item/comment-count-badge'
    );

    render(
      <CommentsProvider workItemId="wi-empty">
        <CommentCountBadge />
      </CommentsProvider>,
    );

    await waitFor(() => {
      expect(screen.queryByTestId('comment-count-badge')).not.toBeInTheDocument();
    });
  });

  it('does not count soft-deleted comments (live-count semantics)', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-del/comments`, () =>
        HttpResponse.json({
          data: [
            makeComment({ id: 'c-a' }),
            makeComment({ id: 'c-b', deleted_at: '2026-04-17T11:00:00Z' }),
            makeComment({ id: 'c-c' }),
          ],
        }),
      ),
    );

    const { CommentsProvider } = await import(
      '@/components/work-item/comments-context'
    );
    const { CommentCountBadge } = await import(
      '@/components/work-item/comment-count-badge'
    );

    render(
      <CommentsProvider workItemId="wi-del">
        <CommentCountBadge />
      </CommentsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('comment-count-badge')).toHaveTextContent('2');
    });
  });

  it('updates optimistically when a comment is added in CommentsTab (6.3 acceptance)', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-opt/comments`, () =>
        HttpResponse.json({ data: [makeComment({ id: 'c-x' })] }),
      ),
      http.post(`${BASE}/api/v1/work-items/wi-opt/comments`, async ({ request }) => {
        const body = (await request.json()) as { body: string };
        return HttpResponse.json({
          data: makeComment({ id: 'c-new', body: body.body }),
        });
      }),
    );

    const { CommentsProvider } = await import(
      '@/components/work-item/comments-context'
    );
    const { CommentCountBadge } = await import(
      '@/components/work-item/comment-count-badge'
    );
    const { CommentsTab } = await import(
      '@/components/work-item/comments-tab'
    );

    render(
      <CommentsProvider workItemId="wi-opt">
        <CommentCountBadge />
        <CommentsTab workItemId="wi-opt" />
      </CommentsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('comment-count-badge')).toHaveTextContent('1');
    });

    const textarea = screen.getByLabelText('Comentario');
    fireEvent.change(textarea, { target: { value: 'nuevo comentario optimista' } });

    const submit = screen.getByRole('button', { name: /Comentar/i });
    fireEvent.click(submit);

    await waitFor(() => {
      expect(screen.getByTestId('comment-count-badge')).toHaveTextContent('2');
    });
  });
});
