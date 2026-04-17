'use client';

import Link from 'next/link';
import { Skeleton } from '@/components/ui/skeleton';
import { TypeBadge } from '@/components/domain/type-badge';
import { StateBadge } from '@/components/domain/state-badge';
import { useChildItems } from '@/hooks/work-item/use-child-items';
import type { WorkItemResponse } from '@/lib/types/work-item';
import type { WorkitemState } from '@/components/domain/state-badge';
import type { WorkitemType } from '@/components/domain/type-badge';

function toStateBadgeState(state: string): WorkitemState {
  const map: Record<string, WorkitemState> = {
    draft: 'draft',
    in_clarification: 'draft',
    in_review: 'in-review',
    changes_requested: 'blocked',
    partially_validated: 'in-review',
    ready: 'ready',
    exported: 'exported',
  };
  return map[state] ?? 'draft';
}

function toTypeBadgeType(type: string): WorkitemType {
  const map: Record<string, WorkitemType> = {
    idea: 'idea',
    bug: 'bug',
    enhancement: 'change',
    task: 'task',
    initiative: 'epic',
    spike: 'spike',
    business_change: 'change',
    requirement: 'requirement',
    milestone: 'milestone',
    story: 'story',
  };
  return map[type] ?? 'task';
}

interface ChildItemRowProps {
  item: WorkItemResponse;
  slug: string;
}

function ChildItemRow({ item, slug }: ChildItemRowProps) {
  return (
    <li className="flex items-center gap-3 py-2 px-1 hover:bg-muted/50 rounded-md transition-colors">
      <TypeBadge type={toTypeBadgeType(item.type)} size="sm" />
      <Link
        href={`/workspace/${slug}/items/${item.id}`}
        className="flex-1 text-sm font-medium text-foreground hover:text-primary hover:underline min-w-0 truncate"
      >
        {item.title}
      </Link>
      <StateBadge state={toStateBadgeState(item.state)} size="sm" />
    </li>
  );
}

interface ChildItemsTabProps {
  workItemId: string;
  slug: string;
}

export function ChildItemsTab({ workItemId, slug }: ChildItemsTabProps) {
  const { children, isLoading } = useChildItems(workItemId);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-h3">Sub-items</h3>
        <Link
          href={`/workspace/${slug}/items/new?parent=${workItemId}`}
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          aria-label="Añadir sub-item"
        >
          + Añadir sub-item
        </Link>
      </div>

      {children.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin sub-items aún</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border" aria-label="Sub-items">
          {children.map((child) => (
            <ChildItemRow key={child.id} item={child} slug={slug} />
          ))}
        </ul>
      )}
    </div>
  );
}
