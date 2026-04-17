'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import { Plus, FileText, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/app/providers/auth-provider';
import { isSessionExpired } from '@/lib/types/auth';
import { useWorkItems } from '@/hooks/use-work-items';
import { WorkItemList } from '@/components/work-item/work-item-list';
import { t } from '@/lib/i18n';
import { PageContainer } from '@/components/layout/page-container';
import type { WorkItemState } from '@/lib/types/work-item';

const PAGE_SIZE = 20;

const STATE_OPTIONS: WorkItemState[] = [
  'draft',
  'in_clarification',
  'in_review',
  'changes_requested',
  'partially_validated',
  'ready',
  'exported',
];

interface WorkItemsPageProps {
  params: { slug: string };
}

export default function WorkItemsPage({ params }: WorkItemsPageProps) {
  const { slug } = params;
  const router = useRouter();
  const searchParams = useSearchParams();

  const { user } = useAuth();

  // ─── URL-synced filter + pagination ──────────────────────────────────────────
  const [stateFilter, setStateFilter] = useState<WorkItemState | ''>(() => {
    const s = searchParams.get('state');
    return (s as WorkItemState) ?? '';
  });
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(() => {
    const p = parseInt(searchParams.get('page') ?? '1', 10);
    return isNaN(p) || p < 1 ? 1 : p;
  });

  // Sync state + page → URL
  useEffect(() => {
    const params = new URLSearchParams();
    if (stateFilter) params.set('state', stateFilter);
    params.set('page', String(page));
    router.replace(`?${params.toString()}`);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateFilter, page]);

  // Reset to page 1 when filter changes
  const handleStateFilterChange = (value: WorkItemState | '') => {
    setStateFilter(value);
    setPage(1);
  };

  // Use workspace_id as project_id for now (1-workspace : 1-project assumption)
  const projectId = user?.workspace_id ?? null;

  const { items, total, isLoading, error } = useWorkItems(
    projectId,
    stateFilter ? { state: stateFilter, page, page_size: PAGE_SIZE } : { page, page_size: PAGE_SIZE },
  );

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const filtered = search.trim()
    ? items.filter((item) =>
        item.title.toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  return (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-h2 font-semibold text-foreground">
          {t('workitem.list.title')}
        </h1>
        <Button asChild>
          <Link href={`/workspace/${slug}/items/new`} aria-label="Nuevo elemento">
            <Plus className="mr-2 h-4 w-4" aria-hidden />
            Nuevo elemento
          </Link>
        </Button>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          aria-label="Estado"
          value={stateFilter}
          onChange={(e) => handleStateFilterChange(e.target.value as WorkItemState | '')}
          className="h-9 rounded-md border border-input bg-background px-3 text-body-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">Todos los estados</option>
          {STATE_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {t(`workitem.state.${s}` as Parameters<typeof t>[0])}
            </option>
          ))}
        </select>
        <input
          type="search"
          placeholder={t('common.app.search')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-9 w-64 rounded-md border border-input bg-background px-3 text-body-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Content */}
      <WorkItemList
        items={filtered}
        slug={slug}
        isLoading={isLoading}
        error={error && !isSessionExpired(error) ? error : null}
        emptyState={<EmptyState slug={slug} />}
      />

      {/* Pagination — shown only when there are items */}
      {!isLoading && !error && filtered.length > 0 && (
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      )}
    </PageContainer>
  );
}

// ─── Pagination controls ──────────────────────────────────────────────────────

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

function Pagination({ page, totalPages, onPageChange }: PaginationProps) {
  return (
    <div className="flex items-center justify-center gap-3 py-2">
      <Button
        variant="outline"
        size="sm"
        aria-label="Anterior"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        <ChevronLeft className="h-4 w-4" aria-hidden />
        Anterior
      </Button>
      <span className="text-body-sm text-muted-foreground tabular-nums">
        Página {page} de {totalPages}
      </span>
      <Button
        variant="outline"
        size="sm"
        aria-label="Siguiente"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Siguiente
        <ChevronRight className="h-4 w-4 ml-1" aria-hidden />
      </Button>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function EmptyState({ slug }: { slug: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <FileText className="h-8 w-8 text-muted-foreground" aria-hidden />
      </div>
      <div className="space-y-1">
        <p className="text-body font-medium text-foreground">
          No hay elementos de trabajo
        </p>
        <p className="text-body-sm text-muted-foreground">
          Crea tu primer elemento para empezar a trabajar
        </p>
      </div>
      <Button asChild>
        <Link href={`/workspace/${slug}/items/new`}>
          <Plus className="mr-2 h-4 w-4" aria-hidden />
          Nuevo elemento
        </Link>
      </Button>
    </div>
  );
}
