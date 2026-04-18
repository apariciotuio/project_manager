import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { CommentsTab } from '@/components/work-item/comments-tab';

vi.mock('@/components/domain/relative-time', () => ({
  RelativeTime: ({ iso }: { iso: string }) => <time dateTime={iso}>{iso}</time>,
}));

const C1 = {
  id: 'c-1',
  work_item_id: 'wi-1',
  parent_comment_id: null,
  body: 'Top-level comment',
  actor_type: 'human' as const,
  actor_id: 'user-alice',
  anchor_section_id: null,
  anchor_start_offset: null,
  anchor_end_offset: null,
  anchor_snapshot_text: null,
  anchor_status: 'active' as const,
  is_edited: false,
  deleted_at: null,
  created_at: '2026-04-15T10:00:00Z',
  replies: [],
};

describe('CommentsTab — post-cf06aec schema alignment', () => {
  it('renders comments with the new versions.ts shape (actor_type/actor_id, no author_name)', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/comments', () =>
        HttpResponse.json({ data: [C1] }),
      ),
    );

    render(<CommentsTab workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('Top-level comment')).toBeInTheDocument());
    // Author display falls back to actor_id when no name lookup is wired.
    expect(screen.getByText(/user-alice/)).toBeInTheDocument();
  });

  it('submits new comments with parent_comment_id (not legacy parent_id) so extra=forbid stays happy', async () => {
    let capturedBody: unknown = null;
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/comments', () =>
        HttpResponse.json({ data: [] }),
      ),
      http.post('http://localhost/api/v1/work-items/wi-1/comments', async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({
          data: { ...C1, body: (capturedBody as { body: string }).body },
        });
      }),
    );

    render(<CommentsTab workItemId="wi-1" />);

    await waitFor(() =>
      expect(screen.getByText('Sin comentarios todavía.')).toBeInTheDocument(),
    );

    const textarea = screen.getByLabelText(/comentario/i);
    await userEvent.type(textarea, 'Hello from test');
    await userEvent.click(screen.getByRole('button', { name: /comentar/i }));

    await waitFor(() => expect(capturedBody).not.toBeNull());
    expect(capturedBody).toEqual({
      body: 'Hello from test',
      parent_comment_id: null,
    });
    // Negative assertion — old key must not leak through.
    expect(capturedBody as Record<string, unknown>).not.toHaveProperty('parent_id');
  });
});
