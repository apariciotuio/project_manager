import { ChevronRight, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { RollupBadge } from './RollupBadge';
import type { WorkItemTreeNode } from '@/lib/types/hierarchy';

interface TreeNodeProps {
  node: WorkItemTreeNode;
  depth: number;
  isExpanded: boolean;
  onToggle: (id: string) => void;
  rollup_percent?: number | null;
  className?: string;
}

export function TreeNode({
  node,
  depth,
  isExpanded,
  onToggle,
  rollup_percent,
  className,
}: TreeNodeProps) {
  const hasChildren = node.children.length > 0;

  return (
    <div
      className={cn('flex items-center gap-2 h-12 px-2 hover:bg-accent/50 rounded', className)}
      style={{ '--depth': depth, paddingLeft: `calc(${depth} * 24px + 8px)` } as React.CSSProperties}
    >
      {/* Expand/collapse toggle */}
      {hasChildren ? (
        <button
          type="button"
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
          onClick={() => onToggle(node.id)}
          className="flex-shrink-0 p-0.5 text-muted-foreground hover:text-foreground"
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
      ) : (
        <span className="flex-shrink-0 w-5" />
      )}

      {/* Type badge */}
      <span className="flex-shrink-0 text-xs rounded px-1.5 py-0.5 bg-muted text-muted-foreground uppercase font-mono">
        {node.type}
      </span>

      {/* Title */}
      <span className="flex-1 truncate text-sm">{node.title}</span>

      {/* State badge */}
      <span className="flex-shrink-0 text-xs text-muted-foreground capitalize">
        {node.state}
      </span>

      {/* Rollup badge */}
      {rollup_percent !== null && rollup_percent !== undefined && (
        <RollupBadge rollup_percent={rollup_percent} className="flex-shrink-0" />
      )}
    </div>
  );
}
