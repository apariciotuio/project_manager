'use client';

import { useTranslations } from 'next-intl';
import type { TaskEdge, TaskNode } from '@/lib/types/task';

interface DependencyBadgeProps {
  nodeId: string;
  edges: TaskEdge[];
  allNodes: TaskNode[];
}

/**
 * Chip showing the count of outgoing "blocks" edges from a task node.
 * Renders nothing when there are no such edges.
 */
export function DependencyBadge({ nodeId, edges, allNodes }: DependencyBadgeProps) {
  const t = useTranslations('workspace.itemDetail.tasks');

  const outgoing = edges.filter(
    (e) => e.from_node_id === nodeId && e.kind === 'blocks',
  );

  if (outgoing.length === 0) return null;

  const blockedTitles = outgoing
    .map((e) => allNodes.find((n) => n.id === e.to_node_id)?.title)
    .filter((title): title is string => title !== undefined);

  const tooltipText = `${t('dependencyTooltipTitle')} ${blockedTitles.join(', ')}`;

  return (
    <span
      title={tooltipText}
      aria-label={t('dependencyBadgeAria').replace('{count}', String(outgoing.length))}
      className="shrink-0 text-xs font-medium text-warning bg-warning/10 px-1.5 py-0.5 rounded-full cursor-default"
    >
      →{outgoing.length}
    </span>
  );
}
