import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useComments } from '@/hooks/work-item/use-comments';

const COMMENTS = [
  {
    id: 'cmt-1',
    author_id: 'user-1',
    author_name: 'Alice',
    author_avatar_url: null,
    body: 'First comment',
    parent_id: null,
    created_at: '2026-01-01T00:00:00Z',
    replies: [],
  },
];

describe('useComments', () => {
  it('returns comments on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/comments', () =>
        HttpResponse.json({ data: COMMENTS })
      )
    );

    const { result } = renderHook(() => useComments('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.comments).toHaveLength(1);
    expect(result.current.comments.at(0)?.body).toBe('First comment');
  });

  it('adds a comment and refreshes', async () => {
    const newComment = {
      id: 'cmt-2',
      author_id: 'user-2',
      author_name: 'Bob',
      author_avatar_url: null,
      body: 'Second comment',
      parent_id: null,
      created_at: '2026-01-02T00:00:00Z',
      replies: [],
    };

    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/comments', () =>
        HttpResponse.json({ data: COMMENTS })
      ),
      http.post('http://localhost/api/v1/work-items/wi-1/comments', () =>
        HttpResponse.json({ data: newComment })
      )
    );

    const { result } = renderHook(() => useComments('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/comments', () =>
        HttpResponse.json({ data: [...COMMENTS, newComment] })
      )
    );

    await result.current.addComment({ body: 'Second comment' });

    await waitFor(() => expect(result.current.comments).toHaveLength(2));
  });
});
