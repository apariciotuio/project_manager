'use client';

import { useState, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { cn } from '@/lib/utils';
import { TreeNode } from './TreeNode';
import { flattenTree } from '@/lib/flatten-tree';
import type { WorkItemTreeNode, WorkItemSummary, HierarchyPageMeta } from '@/lib/types/hierarchy';

// Fixed row height for virtualizer
const ROW_HEIGHT = 48;

interface TreeViewProps {
  roots: WorkItemTreeNode[];
  unparented: WorkItemSummary[];
  meta: HierarchyPageMeta;
  isLoading: boolean;
  onLoadMore?: () => void;
  className?: string;
}

export function TreeView({
  roots,
  unparented,
  meta,
  isLoading,
  onLoadMore,
  className,
}: TreeViewProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const handleToggle = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (isLoading) {
    return (
      <div data-testid="tree-loading-skeleton" className={cn('space-y-2 p-4', className)}>
        {Array.from({ length: 5 }).map((_, i) => (
          // eslint-disable-next-line react/no-array-index-key
          <div key={i} className="h-10 rounded bg-muted animate-pulse" />
        ))}
      </div>
    );
  }

  if (roots.length === 0 && unparented.length === 0) {
    return (
      <div data-testid="tree-empty-state" className={cn('flex items-center justify-center py-16 text-muted-foreground', className)}>
        No items in this project
      </div>
    );
  }

  const flatRows = flattenTree(roots, expandedIds);

  return (
    <div className={cn('flex flex-col gap-0', className)}>
      <VirtualRows rows={flatRows} expandedIds={expandedIds} onToggle={handleToggle} />

      {unparented.length > 0 && (
        <section className="mt-4">
          <h3 className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Unparented
          </h3>
          {unparented.map((item) => (
            <TreeNode
              key={item.id}
              node={{ ...item, children: [] }}
              depth={0}
              isExpanded={false}
              onToggle={handleToggle}
            />
          ))}
        </section>
      )}

      {meta.truncated && (
        <button
          type="button"
          onClick={onLoadMore}
          className="mt-4 w-full py-2 text-sm text-primary hover:underline"
        >
          Load more
        </button>
      )}
    </div>
  );
}

interface FlatRow {
  node: WorkItemTreeNode;
  depth: number;
}

interface VirtualRowsProps {
  rows: FlatRow[];
  expandedIds: Set<string>;
  onToggle: (id: string) => void;
}

function VirtualRows({ rows, expandedIds, onToggle }: VirtualRowsProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  const items = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();

  return (
    <div
      ref={parentRef}
      data-testid="tree-virtual-container"
      className="overflow-auto"
      style={{ height: Math.min(totalSize || rows.length * ROW_HEIGHT, 600) }}
    >
      <div style={{ height: totalSize || rows.length * ROW_HEIGHT, position: 'relative' }}>
        {/* Fallback for jsdom (no layout): render all rows without transforms */}
        {items.length === 0
          ? rows.map((row) => (
              <TreeNode
                key={row.node.id}
                node={row.node}
                depth={row.depth}
                isExpanded={expandedIds.has(row.node.id)}
                onToggle={onToggle}
              />
            ))
          : items.map((virtualRow) => {
              const row = rows[virtualRow.index]!;
              return (
                <div
                  key={row.node.id}
                  style={{
                    position: 'absolute',
                    top: virtualRow.start,
                    width: '100%',
                    height: ROW_HEIGHT,
                  }}
                >
                  <TreeNode
                    node={row.node}
                    depth={row.depth}
                    isExpanded={expandedIds.has(row.node.id)}
                    onToggle={onToggle}
                  />
                </div>
              );
            })}
      </div>
    </div>
  );
}
