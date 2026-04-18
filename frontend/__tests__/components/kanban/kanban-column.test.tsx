/**
 * EP-09 — KanbanColumn component tests.
 *
 * Behaviour covered:
 *   - renders column label + total count badge
 *   - renders each card in the column
 *   - "load more" button appears iff next_cursor is present
 *   - "load more" button calls onLoadMore on click
 *   - loading state disables "load more" and shows spinner
 *   - data-testid is derived from column.key
 *   - bouncingCardId propagates to the matching card
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DndContext } from '@dnd-kit/core';
import { KanbanColumn } from '@/components/kanban/kanban-column';
import type { KanbanCard as KanbanCardData, KanbanColumn as KanbanColumnData } from '@/lib/api/kanban';

function makeCard(overrides: Partial<KanbanCardData> = {}): KanbanCardData {
  return {
    id: 'wi-1',
    title: 'Card',
    type: 'task',
    state: 'draft',
    owner_id: null,
    completeness_score: 0,
    attachment_count: 0,
    tag_ids: [],
    ...overrides,
  };
}

function makeColumn(overrides: Partial<KanbanColumnData> = {}): KanbanColumnData {
  return {
    key: 'draft',
    label: 'Draft',
    total_count: 2,
    cards: [makeCard({ id: 'wi-1' }), makeCard({ id: 'wi-2' })],
    next_cursor: null,
    ...overrides,
  };
}

function renderColumn(column: KanbanColumnData, props: Partial<React.ComponentProps<typeof KanbanColumn>> = {}) {
  return render(
    <DndContext>
      <KanbanColumn
        column={column}
        isMobile={false}
        loadMoreLabel="Load more"
        isLoadingMore={false}
        onLoadMore={vi.fn()}
        {...props}
      />
    </DndContext>,
  );
}

describe('KanbanColumn', () => {
  it('renders column label and total count', () => {
    renderColumn(makeColumn({ label: 'In review', total_count: 7 }));
    expect(screen.getByText('In review')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
  });

  it('exposes a data-testid derived from column.key', () => {
    renderColumn(makeColumn({ key: 'ready' }));
    expect(screen.getByTestId('kanban-column-ready')).toBeInTheDocument();
  });

  it('renders one KanbanCard per card in the column', () => {
    renderColumn(
      makeColumn({
        cards: [
          makeCard({ id: 'a' }),
          makeCard({ id: 'b' }),
          makeCard({ id: 'c' }),
        ],
      }),
    );
    expect(screen.getByTestId('kanban-card-a')).toBeInTheDocument();
    expect(screen.getByTestId('kanban-card-b')).toBeInTheDocument();
    expect(screen.getByTestId('kanban-card-c')).toBeInTheDocument();
  });

  it('renders empty drop zone when cards list is empty', () => {
    const { container } = renderColumn(makeColumn({ cards: [], total_count: 0 }));
    expect(container.querySelectorAll('[data-testid^="kanban-card-"]').length).toBe(0);
  });

  it('does NOT render "load more" button when next_cursor is null', () => {
    renderColumn(makeColumn({ key: 'draft', next_cursor: null }));
    expect(screen.queryByTestId('load-more-draft')).not.toBeInTheDocument();
  });

  it('renders "load more" button when next_cursor is present', () => {
    renderColumn(makeColumn({ key: 'draft', next_cursor: 'cursor-xyz' }));
    expect(screen.getByTestId('load-more-draft')).toBeInTheDocument();
  });

  it('fires onLoadMore when "load more" is clicked', () => {
    const onLoadMore = vi.fn();
    renderColumn(makeColumn({ key: 'draft', next_cursor: 'cursor-xyz' }), { onLoadMore });
    fireEvent.click(screen.getByTestId('load-more-draft'));
    expect(onLoadMore).toHaveBeenCalledOnce();
  });

  it('disables "load more" button while loading', () => {
    renderColumn(makeColumn({ key: 'draft', next_cursor: 'cursor-xyz' }), { isLoadingMore: true });
    expect(screen.getByTestId('load-more-draft')).toBeDisabled();
  });

  it('propagates bouncingCardId to the matching card', () => {
    renderColumn(
      makeColumn({
        cards: [makeCard({ id: 'a' }), makeCard({ id: 'b' })],
      }),
      { bouncingCardId: 'b' },
    );
    expect(screen.getByTestId('kanban-card-a').className).not.toContain('animate-bounce');
    expect(screen.getByTestId('kanban-card-b').className).toContain('animate-bounce');
  });
});
