'use client';

/**
 * EP-09 — Kanban board.
 * Route: /workspace/{slug}/kanban
 * Consumes GET /api/v1/work-items/kanban with column cursor pagination.
 * DnD → PATCH state transition (reuses existing transitionState endpoint).
 */
import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { DndContext, PointerSensor, KeyboardSensor, useSensor, useSensors } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { PageContainer } from '@/components/layout/page-container';
import { SkeletonLoader } from '@/components/layout/skeleton-loader';
import { InlineError } from '@/components/layout/inline-error';
import { KanbanColumn } from '@/components/kanban/kanban-column';
import { useKanbanBoard } from '@/hooks/use-kanban';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { transitionState } from '@/lib/api/work-items';
import type { KanbanGroupBy } from '@/lib/api/kanban';
import type { WorkItemState } from '@/lib/types/work-item';

interface KanbanPageProps {
  params: { slug: string };
}

export default function KanbanPage({ params }: KanbanPageProps) {
  const { slug } = params;
  const t = useTranslations('workspace.kanban');
  const router = useRouter();
  const isMobile = useIsMobile();

  const [groupBy] = useState<KanbanGroupBy>('state');
  const [bouncingCardId, setBouncingCardId] = useState<string | null>(null);

  const { data, isLoading, error, refetch, loadMoreColumn, loadingMoreColumns } = useKanbanBoard({
    group_by: groupBy,
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor),
  );

  const [localColumns, setLocalColumns] = useState<typeof data>(null);
  const displayData = localColumns ?? data;

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      if (groupBy !== 'state') return;
      const { active, over } = event;
      if (!over) return;
      const cardId = String(active.id);
      const targetColumnKey = String(over.id);
      const sourceColumnKey = active.data.current?.columnKey as string | undefined;
      if (!sourceColumnKey || sourceColumnKey === targetColumnKey) return;
      if (!displayData) return;

      // Optimistic update
      const prev = displayData;
      const nextColumns = displayData.columns.map((col) => {
        if (col.key === sourceColumnKey) {
          return { ...col, cards: col.cards.filter((c) => c.id !== cardId) };
        }
        if (col.key === targetColumnKey) {
          const card = prev.columns.find((c) => c.key === sourceColumnKey)?.cards.find((c) => c.id === cardId);
          if (!card) return col;
          return { ...col, cards: [...col.cards, { ...card, state: targetColumnKey }] };
        }
        return col;
      });
      setLocalColumns({ ...displayData, columns: nextColumns });

      try {
        await transitionState(cardId, { target_state: targetColumnKey as WorkItemState });
        refetch();
        // Clear after refetch is scheduled; localColumns stays until new data arrives in next render
        setLocalColumns(null);
      } catch {
        // Revert optimistic update
        setLocalColumns(null);
        // Bounce the card back
        setBouncingCardId(cardId);
        setTimeout(() => setBouncingCardId(null), 600);
      }
    },
    [groupBy, displayData, refetch],
  );

  const handleMobileCardClick = useCallback(
    (id: string) => {
      router.push(`/workspace/${slug}/items/${id}`);
    },
    [router, slug],
  );

  return (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      <h1 className="text-h2 font-semibold text-foreground">{t('title')}</h1>

      {isLoading && (
        <div data-testid="kanban-skeleton">
          <SkeletonLoader variant="card" count={4} />
        </div>
      )}

      {!isLoading && error && (
        <div data-testid="kanban-error">
          <InlineError message={t('error')} onRetry={refetch} />
        </div>
      )}

      {!isLoading && !error && displayData && (
        <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
          <div
            className={[
              isMobile
                ? 'flex overflow-x-auto gap-4 pb-4 scroll-smooth'
                : 'flex flex-row gap-4 overflow-x-auto pb-4',
            ].join(' ')}
            style={isMobile ? { scrollSnapType: 'x mandatory' } : undefined}
          >
            {displayData.columns.map((col) => (
              <KanbanColumn
                key={col.key}
                column={col}
                isMobile={isMobile}
                loadMoreLabel={t('loadMore')}
                isLoadingMore={loadingMoreColumns.has(col.key)}
                onLoadMore={() => loadMoreColumn(col.key)}
                onMobileCardClick={handleMobileCardClick}
                bouncingCardId={bouncingCardId}
              />
            ))}
          </div>
        </DndContext>
      )}
    </PageContainer>
  );
}
