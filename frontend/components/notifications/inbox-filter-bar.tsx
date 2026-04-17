'use client';

import { useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { cn } from '@/lib/utils';

export type InboxFilter = 'all' | 'unread' | 'mentions' | 'reviews';

const FILTER_OPTIONS: InboxFilter[] = ['all', 'unread', 'mentions', 'reviews'];

// ─── Props ────────────────────────────────────────────────────────────────────

export interface InboxFilterBarProps {
  activeFilter: InboxFilter;
  onFilterChange: (filter: InboxFilter) => void;
  search: string;
  onSearchChange: (value: string) => void;
}

// ─── Pure component (no URL sync) ────────────────────────────────────────────

export function InboxFilterBar({
  activeFilter,
  onFilterChange,
  search,
  onSearchChange,
}: InboxFilterBarProps) {
  const t = useTranslations('workspace.inbox');

  return (
    <div className="flex flex-col gap-3">
      {/* Filter tabs */}
      <div role="tablist" aria-label="Notification filters" className="flex gap-1 border-b">
        {FILTER_OPTIONS.map((filter) => (
          <button
            key={filter}
            role="tab"
            aria-selected={activeFilter === filter}
            onClick={() => onFilterChange(filter)}
            className={cn(
              'px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px',
              activeFilter === filter
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground',
            )}
          >
            {t(`filter.${filter}` as Parameters<typeof t>[0])}
          </button>
        ))}
      </div>

      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        <Input
          role="searchbox"
          type="search"
          placeholder={t('searchPlaceholder')}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-8"
        />
      </div>
    </div>
  );
}

// ─── URL-synced wrapper ───────────────────────────────────────────────────────

export function InboxFilterBarWithUrlSync() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeFilter = (searchParams.get('filter') ?? 'all') as InboxFilter;
  const search = searchParams.get('search') ?? '';

  const handleFilterChange = useCallback(
    (filter: InboxFilter) => {
      const params = new URLSearchParams(searchParams.toString());
      if (filter === 'all') {
        params.delete('filter');
      } else {
        params.set('filter', filter);
      }
      params.delete('page'); // reset pagination on filter change
      router.replace(`?${params.toString()}`);
    },
    [router, searchParams],
  );

  const handleSearchChange = useCallback(
    (value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) {
        params.set('search', value);
      } else {
        params.delete('search');
      }
      params.delete('page');
      router.replace(`?${params.toString()}`);
    },
    [router, searchParams],
  );

  return (
    <InboxFilterBar
      activeFilter={activeFilter}
      onFilterChange={handleFilterChange}
      search={search}
      onSearchChange={handleSearchChange}
    />
  );
}
