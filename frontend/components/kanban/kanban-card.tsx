'use client';

import { useDraggable } from '@dnd-kit/core';
import { Paperclip } from 'lucide-react';
import type { KanbanCard as KanbanCardData } from '@/lib/api/kanban';

interface KanbanCardProps {
  card: KanbanCardData;
  isMobile: boolean;
  columnKey: string;
  onMobileClick?: (id: string) => void;
  isBouncing?: boolean;
}

export function KanbanCard({ card, isMobile, columnKey, onMobileClick, isBouncing }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: card.id,
    data: { columnKey },
    disabled: isMobile,
  });

  const content = (
    <div
      ref={isMobile ? undefined : setNodeRef}
      data-testid={`kanban-card-${card.id}`}
      className={[
        'rounded-md border border-border bg-card p-3 text-sm select-none',
        isDragging ? 'opacity-40' : '',
        isBouncing ? 'animate-bounce' : '',
        isMobile ? 'cursor-pointer hover:bg-accent/50' : 'cursor-grab active:cursor-grabbing hover:bg-accent/50',
      ]
        .filter(Boolean)
        .join(' ')}
      {...(!isMobile ? { ...attributes, ...listeners } : {})}
      onClick={isMobile && onMobileClick ? () => onMobileClick(card.id) : undefined}
    >
      <div className="font-medium text-foreground truncate">{card.title}</div>
      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
        <span>{card.type}</span>
        {card.attachment_count > 0 && (
          <span data-testid={`attachment-count-${card.id}`} className="flex items-center gap-0.5">
            <Paperclip className="h-3 w-3" aria-hidden />
            {card.attachment_count > 1 && <span>{card.attachment_count}</span>}
          </span>
        )}
        {card.tag_ids.length > 0 && (
          <span className="rounded bg-muted px-1">{card.tag_ids.length} tag{card.tag_ids.length > 1 ? 's' : ''}</span>
        )}
      </div>
    </div>
  );

  if (!isMobile) {
    return content;
  }
  // Mobile: no drag handle rendered
  return <div ref={undefined}>{content}</div>;
}
