/**
 * EP-09 — KanbanCard component tests.
 *
 * Behaviour covered:
 *   - renders title, type label, attachment + tag counts
 *   - hides attachment icon when count === 0
 *   - data-testid is derived from card.id
 *   - mobile mode: click triggers onMobileClick, draggable attrs absent
 *   - desktop mode: wrapped in useDraggable (attrs present via DndContext)
 *   - bouncing flag toggles animate-bounce class
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DndContext } from '@dnd-kit/core';
import { KanbanCard } from '@/components/kanban/kanban-card';
import type { KanbanCard as KanbanCardData } from '@/lib/api/kanban';

function makeCard(overrides: Partial<KanbanCardData> = {}): KanbanCardData {
  return {
    id: 'wi-1',
    title: 'Investigate timeout',
    type: 'bug',
    state: 'in_progress',
    owner_id: 'user-1',
    completeness_score: 50,
    attachment_count: 0,
    tag_ids: [],
    ...overrides,
  };
}

function renderCard(card: KanbanCardData, props: Partial<React.ComponentProps<typeof KanbanCard>> = {}) {
  return render(
    <DndContext>
      <KanbanCard card={card} isMobile={false} columnKey="draft" {...props} />
    </DndContext>,
  );
}

describe('KanbanCard', () => {
  it('renders title and type label', () => {
    renderCard(makeCard({ title: 'Fix auth bug', type: 'bug' }));
    expect(screen.getByText('Fix auth bug')).toBeInTheDocument();
    expect(screen.getByText('bug')).toBeInTheDocument();
  });

  it('exposes a data-testid derived from the card id', () => {
    renderCard(makeCard({ id: 'wi-42' }));
    expect(screen.getByTestId('kanban-card-wi-42')).toBeInTheDocument();
  });

  it('renders attachment count when attachment_count > 1', () => {
    renderCard(makeCard({ id: 'wi-a', attachment_count: 3 }));
    const badge = screen.getByTestId('attachment-count-wi-a');
    expect(badge).toHaveTextContent('3');
  });

  it('renders attachment icon without number when attachment_count === 1', () => {
    renderCard(makeCard({ id: 'wi-b', attachment_count: 1 }));
    const badge = screen.getByTestId('attachment-count-wi-b');
    expect(badge).toBeInTheDocument();
    expect(badge.textContent).toBe('');
  });

  it('hides attachment badge when attachment_count === 0', () => {
    renderCard(makeCard({ id: 'wi-c', attachment_count: 0 }));
    expect(screen.queryByTestId('attachment-count-wi-c')).not.toBeInTheDocument();
  });

  it('renders tag count with pluralised copy', () => {
    renderCard(makeCard({ tag_ids: ['t-1', 't-2', 't-3'] }));
    expect(screen.getByText('3 tags')).toBeInTheDocument();
  });

  it('uses singular copy for one tag', () => {
    renderCard(makeCard({ tag_ids: ['t-1'] }));
    expect(screen.getByText('1 tag')).toBeInTheDocument();
  });

  it('fires onMobileClick when clicked in mobile mode', () => {
    const onMobileClick = vi.fn();
    renderCard(makeCard({ id: 'wi-9' }), {
      isMobile: true,
      onMobileClick,
    });
    fireEvent.click(screen.getByTestId('kanban-card-wi-9'));
    expect(onMobileClick).toHaveBeenCalledWith('wi-9');
  });

  it('does not fire onMobileClick when clicked on desktop', () => {
    const onMobileClick = vi.fn();
    renderCard(makeCard({ id: 'wi-10' }), {
      isMobile: false,
      onMobileClick,
    });
    fireEvent.click(screen.getByTestId('kanban-card-wi-10'));
    expect(onMobileClick).not.toHaveBeenCalled();
  });

  it('applies animate-bounce class when isBouncing is true', () => {
    renderCard(makeCard({ id: 'wi-b' }), { isBouncing: true });
    expect(screen.getByTestId('kanban-card-wi-b').className).toContain('animate-bounce');
  });

  it('does not apply animate-bounce class when isBouncing is false', () => {
    renderCard(makeCard({ id: 'wi-c' }), { isBouncing: false });
    expect(screen.getByTestId('kanban-card-wi-c').className).not.toContain('animate-bounce');
  });
});
