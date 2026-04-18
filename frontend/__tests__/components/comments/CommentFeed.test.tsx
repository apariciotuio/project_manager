import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { CommentFeed } from '@/components/comments/CommentFeed';

vi.mock('@/components/domain/relative-time', () => ({
  RelativeTime: ({ iso }: { iso: string }) => <time dateTime={iso}>{iso}</time>,
}));

const COMMENT = {
  id: 'c-1',
  work_item_id: 'wi-1',
  parent_comment_id: null,
  body: 'First comment',
  actor_type: 'human' as const,
  actor_id: 'user-1',
  anchor_section_id: null,
  anchor_start_offset: null,
  anchor_end_offset: null,
  anchor_snapshot_text: null,
  anchor_status: 'active' as const,
  is_edited: false,
  deleted_at: null,
  created_at: '2026-01-01T10:00:00Z',
  replies: [],
};

function mockComments(comments: unknown[]) {
  server.use(
    http.get('http://localhost/api/v1/work-items/wi-1/comments', () =>
      HttpResponse.json({ data: comments })
    )
  );
}

describe('CommentFeed', () => {
  it('shows loading skeleton initially', () => {
    mockComments([]);
    render(<CommentFeed workItemId="wi-1" currentUserId="user-1" />);
    // Skeleton elements present before data loads
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders empty state when no comments', async () => {
    mockComments([]);
    render(<CommentFeed workItemId="wi-1" currentUserId="user-1" />);
    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
    expect(screen.getByText(/no comments yet/i)).toBeInTheDocument();
  });

  it('renders CommentThread for each top-level comment', async () => {
    mockComments([COMMENT, { ...COMMENT, id: 'c-2', body: 'Second comment' }]);
    render(<CommentFeed workItemId="wi-1" currentUserId="user-1" />);
    await waitFor(() => {
      expect(screen.getByText('First comment')).toBeInTheDocument();
      expect(screen.getByText('Second comment')).toBeInTheDocument();
    });
  });

  it('renders CommentInput at the top', async () => {
    mockComments([]);
    render(<CommentFeed workItemId="wi-1" currentUserId="user-1" />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /comentar/i })).toBeInTheDocument();
    });
  });

  it('adds comment via input form', async () => {
    mockComments([]);
    let postedBody = '';
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/comments', async ({ request }) => {
        const body = await request.json() as { body: string };
        postedBody = body.body;
        return HttpResponse.json({ data: { ...COMMENT, body: postedBody } });
      })
    );
    render(<CommentFeed workItemId="wi-1" currentUserId="user-1" />);
    await waitFor(() => screen.getByRole('textbox'));
    await userEvent.type(screen.getByRole('textbox'), 'New comment');
    await userEvent.click(screen.getByRole('button', { name: /comentar/i }));
    await waitFor(() => expect(postedBody).toBe('New comment'));
  });
});
