'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Plus, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/app/providers/auth-provider';
import { isSessionExpired } from '@/lib/types/auth';
import { useWorkItems } from '@/hooks/use-work-items';
import { StateBadge } from '@/components/domain/state-badge';
import { TypeBadge } from '@/components/domain/type-badge';
import { CompletenessBar } from '@/components/domain/completeness-bar';
import { RelativeTime } from '@/components/domain/relative-time';
import { t } from '@/lib/i18n';
import { PageContainer } from '@/components/layout/page-container';
import type { WorkItemState, WorkItemType } from '@/lib/types/work-item';
import type { CompletenessLevel } from '@/components/domain/level-badge';
import type { WorkitemState } from '@/components/domain/state-badge';
import type { WorkitemType } from '@/components/domain/type-badge';

// Map backend state → StateBadge WorkitemState
const STATE_MAP: Partial<Record<WorkItemState, WorkitemState>> = {
  draft: 'draft',
  in_review: 'in-review',
  changes_requested: 'blocked',
  partially_validated: 'in-review',
  ready: 'ready',
  exported: 'exported',
  in_clarification: 'draft',
};

// Map backend type → TypeBadge WorkitemType
const TYPE_MAP: Partial<Record<WorkItemType, WorkitemType>> = {
  story: 'story',
  milestone: 'milestone',
  bug: 'bug',
  task: 'task',
  spike: 'spike',
  idea: 'idea',
  requirement: 'requirement',
  enhancement: 'change',
  initiative: 'epic',
  business_change: 'change',
};

function scoreToLevel(score: number): CompletenessLevel {
  if (score >= 80) return 'ready';
  if (score >= 60) return 'high';
  if (score >= 30) return 'medium';
  return 'low';
}

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
  const { user } = useAuth();
  const [stateFilter, setStateFilter] = useState<WorkItemState | ''>('');
  const [search, setSearch] = useState('');

  // Use workspace_id as project_id for now (1-workspace : 1-project assumption)
  const projectId = user?.workspace_id ?? null;

  const { items, isLoading, error } = useWorkItems(
    projectId,
    stateFilter ? { state: stateFilter } : {},
  );

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
          onChange={(e) => setStateFilter(e.target.value as WorkItemState | '')}
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
      {isLoading ? (
        <WorkItemsSkeleton />
      ) : error && !isSessionExpired(error) ? (
        <div role="alert" className="text-body-sm text-destructive">
          {t('workitem.list.errorBanner')}: {error.message}
        </div>
      ) : error ? null : filtered.length === 0 ? (
        <EmptyState slug={slug} />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-body-sm">
            <thead className="border-b border-border bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                  {t('workitem.list.columns.title')}
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                  {t('workitem.list.columns.type')}
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                  {t('workitem.list.columns.state')}
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                  {t('workitem.list.columns.completeness')}
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                  {t('workitem.list.columns.updatedAt')}
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const badgeState = STATE_MAP[item.state] ?? 'draft';
                const badgeType = TYPE_MAP[item.type];
                const level = scoreToLevel(item.completeness_score);
                return (
                  <tr
                    key={item.id}
                    tabIndex={0}
                    role="row"
                    aria-label={item.title}
                    onClick={() => router.push(`/workspace/${slug}/items/${item.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        router.push(`/workspace/${slug}/items/${item.id}`);
                      }
                    }}
                    className="cursor-pointer border-b border-border transition-colors last:border-0 hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-inset"
                  >
                    <td className="px-4 py-3 font-medium text-foreground">
                      {item.title}
                    </td>
                    <td className="px-4 py-3">
                      {badgeType ? (
                        <TypeBadge type={badgeType} size="sm" />
                      ) : (
                        <span className="text-muted-foreground">{item.type}</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StateBadge state={badgeState} size="sm" />
                    </td>
                    <td className="px-4 py-3 w-36">
                      <CompletenessBar
                        level={level}
                        percent={item.completeness_score}
                        showLabel
                      />
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      <RelativeTime iso={item.updated_at} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </PageContainer>
  );
}

function WorkItemsSkeleton() {
  return (
    <div data-testid="work-items-skeleton" className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full rounded-md" />
      ))}
    </div>
  );
}

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
