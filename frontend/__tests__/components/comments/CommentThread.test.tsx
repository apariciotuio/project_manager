import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CommentThread } from '@/components/comments/CommentThread';
import type { Comment } from '@/lib/types/versions';

vi.mock('@/components/domain/relative-time', () => ({
  RelativeTime: ({ iso }: { iso: string }) => <time dateTime={iso}>{iso}</time>,
}));

const PARENT: Comment = {
  id: 'c-1',
  work_item_id: 'wi-1',
  parent_comment_id: null,
  body: 'Parent comment',
  actor_type: 'human',
  actor_id: 'user-1',
  anchor_section_id: null,
  anchor_start_offset: null,
  anchor_end_offset: null,
  anchor_snapshot_text: null,
  anchor_status: 'active',
  is_edited: false,
  deleted_at: null,
  created_at: '2026-01-01T10:00:00Z',
  replies: [],
};

const REPLY: Comment = {
  id: 'c-2',
  work_item_id: 'wi-1',
  parent_comment_id: 'c-1',
  body: 'Child reply',
  actor_type: 'human',
  actor_id: 'user-2',
  anchor_section_id: null,
  anchor_start_offset: null,
  anchor_end_offset: null,
  anchor_snapshot_text: null,
  anchor_status: 'active',
  is_edited: false,
  deleted_at: null,
  created_at: '2026-01-01T11:00:00Z',
  replies: [],
};

describe('CommentThread', () => {
  it('renders parent comment body', () => {
    render(
      <CommentThread
        comment={PARENT}
        currentUserId="user-1"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.getByText('Parent comment')).toBeInTheDocument();
  });

  it('renders nested replies indented', () => {
    const withReply = { ...PARENT, replies: [REPLY] };
    render(
      <CommentThread
        comment={withReply}
        currentUserId="user-1"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.getByText('Child reply')).toBeInTheDocument();
    // Reply container should be indented
    const replyEl = screen.getByText('Child reply').closest('[data-testid="comment-reply"]');
    expect(replyEl).toBeInTheDocument();
  });

  it('shows reply count badge when there are replies', () => {
    const withReply = { ...PARENT, replies: [REPLY] };
    render(
      <CommentThread
        comment={withReply}
        currentUserId="user-1"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('calls onDelete with comment id', async () => {
    const onDelete = vi.fn();
    render(
      <CommentThread
        comment={PARENT}
        currentUserId="user-1"
        onEdit={vi.fn()}
        onDelete={onDelete}
        onReply={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole('button', { name: /eliminar/i }));
    expect(onDelete).toHaveBeenCalledWith('c-1');
  });

  it('calls onEdit with id and new body', async () => {
    const onEdit = vi.fn();
    render(
      <CommentThread
        comment={PARENT}
        currentUserId="user-1"
        onEdit={onEdit}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole('button', { name: /editar/i }));
    const textarea = screen.getByRole('textbox');
    await userEvent.clear(textarea);
    await userEvent.type(textarea, 'Edited text');
    await userEvent.click(screen.getByRole('button', { name: /guardar/i }));
    expect(onEdit).toHaveBeenCalledWith('c-1', 'Edited text');
  });

  it('calls onReply with parentId and body', async () => {
    const onReply = vi.fn();
    render(
      <CommentThread
        comment={PARENT}
        currentUserId="user-2"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={onReply}
      />
    );
    await userEvent.click(screen.getByRole('button', { name: /responder/i }));
    const replyBox = screen.getByRole('textbox');
    await userEvent.type(replyBox, 'My reply');
    await userEvent.click(screen.getByRole('button', { name: /comentar/i }));
    expect(onReply).toHaveBeenCalledWith('c-1', 'My reply');
  });

  it('renders orphaned anchor warning', () => {
    const orphaned: Comment = { ...PARENT, anchor_status: 'orphaned', anchor_section_id: 's-1' };
    render(
      <CommentThread
        comment={orphaned}
        currentUserId="user-1"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.getByText(/anchor text no longer found/i)).toBeInTheDocument();
  });

  it('renders deleted body as [deleted] when replies exist', () => {
    const deleted: Comment = {
      ...PARENT,
      deleted_at: '2026-01-02T00:00:00Z',
      replies: [REPLY],
    };
    render(
      <CommentThread
        comment={deleted}
        currentUserId="user-1"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.getByText('[deleted]')).toBeInTheDocument();
    expect(screen.getByText('Child reply')).toBeInTheDocument();
  });
});
