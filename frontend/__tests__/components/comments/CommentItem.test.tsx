import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CommentItem } from '@/components/comments/CommentItem';
import type { Comment } from '@/lib/types/versions';

vi.mock('@/components/domain/relative-time', () => ({
  RelativeTime: ({ iso }: { iso: string }) => <time dateTime={iso}>{iso}</time>,
}));

const BASE_COMMENT: Comment = {
  id: 'c-1',
  work_item_id: 'wi-1',
  parent_comment_id: null,
  body: 'Hello world',
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

describe('CommentItem', () => {
  it('renders comment body and author', () => {
    render(
      <CommentItem
        comment={BASE_COMMENT}
        currentUserId="user-1"
        authorName="Alice"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.getByText('Hello world')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
  });

  it('shows edit and delete buttons for own human comment', () => {
    render(
      <CommentItem
        comment={BASE_COMMENT}
        currentUserId="user-1"
        authorName="Alice"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.getByRole('button', { name: /editar/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /eliminar/i })).toBeInTheDocument();
  });

  it('hides edit and delete buttons for other user comment', () => {
    render(
      <CommentItem
        comment={BASE_COMMENT}
        currentUserId="user-2"
        authorName="Alice"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.queryByRole('button', { name: /editar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /eliminar/i })).not.toBeInTheDocument();
  });

  it('hides edit button for ai_suggestion comment even if own', () => {
    const aiComment: Comment = { ...BASE_COMMENT, actor_type: 'ai_suggestion' };
    render(
      <CommentItem
        comment={aiComment}
        currentUserId="user-1"
        authorName="AI"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.queryByRole('button', { name: /editar/i })).not.toBeInTheDocument();
    // Delete remains (authorized human can delete AI suggestion)
    expect(screen.getByRole('button', { name: /eliminar/i })).toBeInTheDocument();
  });

  it('renders [deleted] in italic for soft-deleted comment with replies', () => {
    const deleted: Comment = {
      ...BASE_COMMENT,
      deleted_at: '2026-01-02T00:00:00Z',
      replies: [{ ...BASE_COMMENT, id: 'c-2', parent_comment_id: 'c-1' }],
    };
    render(
      <CommentItem
        comment={deleted}
        currentUserId="user-1"
        authorName="Alice"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    const deletedEl = screen.getByText('[deleted]');
    expect(deletedEl).toBeInTheDocument();
    expect(deletedEl).toHaveClass('italic');
  });

  it('renders orphaned anchor warning chip', () => {
    const orphaned: Comment = { ...BASE_COMMENT, anchor_status: 'orphaned', anchor_section_id: 's-1' };
    render(
      <CommentItem
        comment={orphaned}
        currentUserId="user-1"
        authorName="Alice"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    expect(screen.getByText(/anchor text no longer found/i)).toBeInTheDocument();
  });

  it('calls onDelete when delete button clicked', async () => {
    const onDelete = vi.fn();
    render(
      <CommentItem
        comment={BASE_COMMENT}
        currentUserId="user-1"
        authorName="Alice"
        onEdit={vi.fn()}
        onDelete={onDelete}
        onReply={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole('button', { name: /eliminar/i }));
    expect(onDelete).toHaveBeenCalledWith('c-1');
  });

  it('calls onEdit with new body when edit is submitted', async () => {
    const onEdit = vi.fn();
    render(
      <CommentItem
        comment={BASE_COMMENT}
        currentUserId="user-1"
        authorName="Alice"
        onEdit={onEdit}
        onDelete={vi.fn()}
        onReply={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole('button', { name: /editar/i }));
    const textarea = screen.getByRole('textbox');
    await userEvent.clear(textarea);
    await userEvent.type(textarea, 'Updated body');
    await userEvent.click(screen.getByRole('button', { name: /guardar/i }));
    expect(onEdit).toHaveBeenCalledWith('c-1', 'Updated body');
  });
});
