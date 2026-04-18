'use client';

import type { PipelineItem } from '@/lib/api/pipeline';

interface PipelineCardProps {
  item: PipelineItem;
}

export function PipelineCard({ item }: PipelineCardProps) {
  return (
    <div
      data-testid={`pipeline-card-${item.id}`}
      className="rounded-md border border-border bg-card p-3 text-sm hover:bg-accent/50 cursor-default"
      title="To change state, open the item"
    >
      <div className="font-medium text-foreground truncate">{item.title}</div>
      <div className="mt-1 text-xs text-muted-foreground">{item.type}</div>
    </div>
  );
}
