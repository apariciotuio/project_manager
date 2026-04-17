'use client';

import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { useParentWorkItem } from '@/hooks/work-item/use-parent-work-item';
import type { WorkItemResponse } from '@/lib/types/work-item';

interface ParentBreadcrumbProps {
  workItem: WorkItemResponse;
  slug: string;
}

export function ParentBreadcrumb({ workItem, slug }: ParentBreadcrumbProps) {
  const t = useTranslations('workspace.itemDetail.breadcrumb');
  const { parent } = useParentWorkItem(workItem.parent_work_item_id);

  if (!workItem.parent_work_item_id || !parent) {
    return null;
  }

  return (
    <nav aria-label={t('aria')} className="flex items-center gap-1.5 text-sm text-muted-foreground">
      <Link
        href={`/workspace/${slug}/items/${parent.id}`}
        title={t('parentAria')}
        className="hover:text-foreground hover:underline truncate max-w-[200px]"
      >
        {parent.title}
      </Link>
      <span aria-hidden>{t('separator')}</span>
      <span className="text-foreground truncate max-w-[200px]">{workItem.title}</span>
    </nav>
  );
}
