'use client';

import { useDroppable } from '@dnd-kit/core';
import { Loader2 } from 'lucide-react';
import { KanbanCard } from './kanban-card';
import type { KanbanColumn as KanbanColumnData } from '@/lib/api/kanban';

interface KanbanColumnProps {
  column: KanbanColumnData;
  isMobile: boolean;
  loadMoreLabel: string;
  isLoadingMore: boolean;
  onLoadMore: () => void;
  onMobileCardClick?: (id: string) => void;
  bouncingCardId?: string | null;
}

export function KanbanColumn({
  column,
  isMobile,
  loadMoreLabel,
  isLoadingMore,
  onLoadMore,
  onMobileCardClick,
  bouncingCardId,
}: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: column.key });

  return (
    <div
      data-testid={`kanban-column-${column.key}`}
      className={[
        'flex flex-col',
        isMobile
          ? 'min-w-[85vw] scroll-snap-align-start'
          : 'min-w-[220px] max-w-[280px] flex-1',
      ].join(' ')}
    >
      {/* Column header */}
      <div className="flex items-center justify-between gap-2 mb-3 pb-2 border-b border-border">
        <span className="text-sm font-medium text-foreground truncate">{column.label}</span>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
          {column.total_count}
        </span>
      </div>

      {/* Drop zone */}
      <div
        ref={setNodeRef}
        className={[
          'flex flex-col gap-2 min-h-[120px] rounded-md p-1 transition-colors',
          isOver ? 'bg-accent/20' : '',
        ].join(' ')}
      >
        {column.cards.map((card) => (
          <KanbanCard
            key={card.id}
            card={card}
            isMobile={isMobile}
            columnKey={column.key}
            onMobileClick={onMobileCardClick}
            isBouncing={bouncingCardId === card.id}
          />
        ))}
      </div>

      {/* Load more */}
      {column.next_cursor && (
        <button
          data-testid={`load-more-${column.key}`}
          type="button"
          onClick={onLoadMore}
          disabled={isLoadingMore}
          className="mt-2 flex items-center justify-center gap-1 rounded-md border border-border py-1.5 text-xs text-muted-foreground hover:bg-accent disabled:opacity-50"
        >
          {isLoadingMore ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
          {loadMoreLabel}
        </button>
      )}
    </div>
  );
}
