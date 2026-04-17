'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect, useCallback } from 'react';
import { Plus, FileText, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/app/providers/auth-provider';
import { isSessionExpired } from '@/lib/types/auth';
import { useWorkItems } from '@/hooks/use-work-items';
import { WorkItemList } from '@/components/work-item/work-item-list';
import { SearchBar } from '@/components/search/search-bar';
import { SavedSearchesMenu } from '@/components/search/saved-searches-menu';
import { useTranslations } from 'next-intl';
import { PageContainer } from '@/components/layout/page-container';
import type { WorkItemState, WorkItemType, Priority, WorkItemResponse } from '@/lib/types/work-item';

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

const TYPE_OPTIONS: WorkItemType[] = [
  'idea',
  'bug',
  'enhancement',
  'task',
  'initiative',
  'spike',
  'business_change',
  'requirement',
  'milestone',
  'story',
];

const PRIORITY_OPTIONS: Priority[] = ['low', 'medium', 'high', 'critical'];

interface WorkItemsPageProps {
  params: { slug: string };
}

export default function WorkItemsPage({ params }: WorkItemsPageProps) {
  const { slug } = params;
  const router = useRouter();
  const searchParams = useSearchParams();
  const tItems = useTranslations('workspace.items');
  const tFilters = useTranslations('workspace.items.filters');

  const { user } = useAuth();

  // ─── URL-synced filters ───────────────────────────────────────────────────────
  const [stateFilter, setStateFilter] = useState<WorkItemState | ''>(() => {
    const s = searchParams.get('state');
    return (s as WorkItemState) ?? '';
  });
  const [typeFilter, setTypeFilter] = useState<WorkItemType | ''>(() => {
    const t = searchParams.get('type');
    return (t as WorkItemType) ?? '';
  });
  const [priorityFilter, setPriorityFilter] = useState<Priority | ''>(() => {
    const p = searchParams.get('priority');
    return (p as Priority) ?? '';
  });
  const [completenessMin, setCompletenessMin] = useState<number>(() => {
    const c = searchParams.get('completeness_min');
    return c ? parseInt(c, 10) : 0;
  });
  const [updatedAfter, setUpdatedAfter] = useState<string>(() => searchParams.get('updated_after') ?? '');
  const [updatedBefore, setUpdatedBefore] = useState<string>(() => searchParams.get('updated_before') ?? '');
  const [page, setPage] = useState(() => {
    const p = parseInt(searchParams.get('page') ?? '1', 10);
    return isNaN(p) || p < 1 ? 1 : p;
  });

  // ─── Sync state → URL ────────────────────────────────────────────────────────
  const syncUrl = useCallback(() => {
    const p = new URLSearchParams();
    if (stateFilter) p.set('state', stateFilter);
    if (typeFilter) p.set('type', typeFilter);
    if (priorityFilter) p.set('priority', priorityFilter);
    if (completenessMin > 0) p.set('completeness_min', String(completenessMin));
    if (updatedAfter) p.set('updated_after', updatedAfter);
    if (updatedBefore) p.set('updated_before', updatedBefore);
    p.set('page', String(page));
    router.replace(`?${p.toString()}`);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateFilter, typeFilter, priorityFilter, completenessMin, updatedAfter, updatedBefore, page]);

  useEffect(() => {
    syncUrl();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateFilter, typeFilter, priorityFilter, completenessMin, updatedAfter, updatedBefore, page]);

  const resetPage = () => setPage(1);

  const handleStateFilterChange = (value: WorkItemState | '') => {
    setStateFilter(value);
    resetPage();
  };

  const handleTypeFilterChange = (value: WorkItemType | '') => {
    setTypeFilter(value);
    resetPage();
  };

  const handlePriorityFilterChange = (value: Priority | '') => {
    setPriorityFilter(value);
    resetPage();
  };

  const handleCompletenessMin = (value: number) => {
    setCompletenessMin(value);
    resetPage();
  };

  const handleUpdatedAfter = (value: string) => {
    setUpdatedAfter(value);
    resetPage();
  };

  const handleUpdatedBefore = (value: string) => {
    setUpdatedBefore(value);
    resetPage();
  };

  const handleReset = () => {
    setStateFilter('');
    setTypeFilter('');
    setPriorityFilter('');
    setCompletenessMin(0);
    setUpdatedAfter('');
    setUpdatedBefore('');
    setPage(1);
  };

  // ─── Search state ─────────────────────────────────────────────────────────────
  const [searchResults, setSearchResults] = useState<WorkItemResponse[] | null>(null);
  const [isSearchActive, setIsSearchActive] = useState(false);

  const projectId = user?.workspace_id ?? null;

  const { items, total, isLoading, error } = useWorkItems(
    projectId,
    {
      ...(stateFilter ? { state: stateFilter } : {}),
      ...(typeFilter ? { type: typeFilter } : {}),
      ...(priorityFilter ? { priority: priorityFilter } : {}),
      ...(completenessMin > 0 ? { completeness_min: completenessMin } : {}),
      ...(updatedAfter ? { updated_after: updatedAfter } : {}),
      ...(updatedBefore ? { updated_before: updatedBefore } : {}),
      page,
      page_size: PAGE_SIZE,
    },
  );

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // When search is active, display search results instead of filtered list
  const displayItems = isSearchActive ? (searchResults ?? []) : items;

  return (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-h2 font-semibold text-foreground">
          {tItems('title')}
        </h1>
        <Button asChild>
          <Link href={`/workspace/${slug}/items/new`} aria-label={tItems('newButtonAria')}>
            <Plus className="mr-2 h-4 w-4" aria-hidden />
            {tItems('newButton')}
          </Link>
        </Button>
      </div>

      {/* Search bar */}
      <SearchBar
        slug={slug}
        onResults={setSearchResults}
        onSearchActiveChange={setIsSearchActive}
      />

      {/* Filter bar — hidden when search is active */}
      <div className={`flex flex-wrap items-end gap-3 ${isSearchActive ? 'opacity-50 pointer-events-none' : ''}`}>
        {/* State filter */}
        <div className="flex flex-col gap-1">
          <label htmlFor="filter-state" className="text-body-sm text-muted-foreground sr-only">
            {tItems('stateFilterAria')}
          </label>
          <select
            id="filter-state"
            aria-label={tItems('stateFilterAria')}
            value={stateFilter}
            onChange={(e) => handleStateFilterChange(e.target.value as WorkItemState | '')}
            className="h-9 rounded-md border border-input bg-background px-3 text-body-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">{tItems('allStates')}</option>
            {STATE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {tItems(`states.${s}` as Parameters<typeof tItems>[0])}
              </option>
            ))}
          </select>
        </div>

        {/* Type filter */}
        <div className="flex flex-col gap-1">
          <select
            aria-label={tFilters('typeFilterAria')}
            value={typeFilter}
            onChange={(e) => handleTypeFilterChange(e.target.value as WorkItemType | '')}
            className="h-9 rounded-md border border-input bg-background px-3 text-body-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">{tFilters('allTypes')}</option>
            {TYPE_OPTIONS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        {/* Priority filter */}
        <div className="flex flex-col gap-1">
          <select
            aria-label={tFilters('priorityFilterAria')}
            value={priorityFilter}
            onChange={(e) => handlePriorityFilterChange(e.target.value as Priority | '')}
            className="h-9 rounded-md border border-input bg-background px-3 text-body-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">{tFilters('allPriorities')}</option>
            {PRIORITY_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        {/* Completeness min slider */}
        <div className="flex flex-col gap-1">
          <label htmlFor="filter-completeness" className="text-body-sm text-muted-foreground">
            {tFilters('completenessLabel', { value: completenessMin })}
          </label>
          <input
            id="filter-completeness"
            type="range"
            min={0}
            max={100}
            step={10}
            value={completenessMin}
            aria-label={tFilters('completenessAria')}
            onChange={(e) => handleCompletenessMin(parseInt(e.target.value, 10))}
            className="w-32 accent-primary"
          />
        </div>

        {/* Updated after */}
        <div className="flex flex-col gap-1">
          <label htmlFor="filter-date-from" className="text-body-sm text-muted-foreground">
            {tFilters('dateFrom')}
          </label>
          <input
            id="filter-date-from"
            type="date"
            value={updatedAfter}
            onChange={(e) => handleUpdatedAfter(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-body-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {/* Updated before */}
        <div className="flex flex-col gap-1">
          <label htmlFor="filter-date-to" className="text-body-sm text-muted-foreground">
            {tFilters('dateTo')}
          </label>
          <input
            id="filter-date-to"
            type="date"
            value={updatedBefore}
            onChange={(e) => handleUpdatedBefore(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-body-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {/* Reset */}
        <Button
          variant="ghost"
          size="sm"
          aria-label={tFilters('resetAria')}
          onClick={handleReset}
          className="h-9 px-3"
        >
          <RotateCcw className="mr-1 h-3 w-3" aria-hidden />
          {tFilters('reset')}
        </Button>

        {/* Saved searches */}
        <SavedSearchesMenu
          currentFilters={{
            ...(stateFilter ? { state: stateFilter } : {}),
            ...(typeFilter ? { type: typeFilter } : {}),
            ...(priorityFilter ? { priority: priorityFilter } : {}),
            ...(completenessMin > 0 ? { completeness_min: completenessMin } : {}),
            ...(updatedAfter ? { updated_after: updatedAfter } : {}),
            ...(updatedBefore ? { updated_before: updatedBefore } : {}),
          }}
          onApply={(qp) => {
            setStateFilter((qp.state as WorkItemState) ?? '');
            setTypeFilter((qp.type as WorkItemType) ?? '');
            setPriorityFilter((qp.priority as Priority) ?? '');
            setCompletenessMin(typeof qp.completeness_min === 'number' ? qp.completeness_min : 0);
            setUpdatedAfter(typeof qp.updated_after === 'string' ? qp.updated_after : '');
            setUpdatedBefore(typeof qp.updated_before === 'string' ? qp.updated_before : '');
            setPage(1);
          }}
        />
      </div>

      {/* Content */}
      <WorkItemList
        items={displayItems}
        slug={slug}
        isLoading={isLoading && !isSearchActive}
        error={!isSearchActive && error && !isSessionExpired(error) ? error : null}
        emptyState={<EmptyState slug={slug} tItems={tItems} />}
      />

      {/* Pagination — hidden when search active */}
      {!isSearchActive && !isLoading && !error && displayItems.length > 0 && (
        <Pagination
          page={page}
          totalPages={totalPages}
          onPageChange={setPage}
          tItems={tItems}
        />
      )}
    </PageContainer>
  );
}

// ─── Pagination controls ──────────────────────────────────────────────────────

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  tItems: ReturnType<typeof useTranslations>;
}

function Pagination({ page, totalPages, onPageChange, tItems }: PaginationProps) {
  return (
    <div className="flex items-center justify-center gap-3 py-2">
      <Button
        variant="outline"
        size="sm"
        aria-label={tItems('pagination.prev')}
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        <ChevronLeft className="h-4 w-4" aria-hidden />
        {tItems('pagination.prev')}
      </Button>
      <span className="text-body-sm text-muted-foreground tabular-nums">
        {tItems('pagination.pageOf', { page, total: totalPages })}
      </span>
      <Button
        variant="outline"
        size="sm"
        aria-label={tItems('pagination.next')}
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        {tItems('pagination.next')}
        <ChevronRight className="h-4 w-4 ml-1" aria-hidden />
      </Button>
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({ slug, tItems }: { slug: string; tItems: ReturnType<typeof useTranslations> }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <FileText className="h-8 w-8 text-muted-foreground" aria-hidden />
      </div>
      <div className="space-y-1">
        <p className="text-body font-medium text-foreground">
          {tItems('empty.title')}
        </p>
        <p className="text-body-sm text-muted-foreground">
          {tItems('empty.subtitle')}
        </p>
      </div>
      <Button asChild>
        <Link href={`/workspace/${slug}/items/new`}>
          <Plus className="mr-2 h-4 w-4" aria-hidden />
          {tItems('empty.createButton')}
        </Link>
      </Button>
    </div>
  );
}
