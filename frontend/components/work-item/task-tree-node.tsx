'use client';

import { useState, useRef, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTaskMutations } from '@/hooks/work-item/use-task-mutations';
import { TaskTreeAddDialog } from '@/components/work-item/task-tree-add-dialog';
import { DependencyBadge } from '@/components/work-item/dependency-badge';
import type { TaskNode, TaskEdge, TaskStatus } from '@/lib/types/task';

const STATUS_CYCLE: Record<TaskStatus, TaskStatus> = {
  draft: 'in_progress',
  in_progress: 'done',
  done: 'draft',
};

const DEPTH_PX = 24;

interface TaskTreeNodeProps {
  node: TaskNode;
  depth: number;
  /** Direct children of this node (pre-filtered by caller) */
  children: TaskNode[];
  /** All nodes in the tree (for recursive child resolution) */
  allNodes: TaskNode[];
  /** All edges in the tree (for dependency badge) */
  edges: TaskEdge[];
  workItemId: string;
  onRefetch: () => void;
}

export function TaskTreeNode({
  node,
  depth,
  children,
  allNodes,
  edges,
  workItemId,
  onRefetch,
}: TaskTreeNodeProps) {
  const t = useTranslations('workspace.itemDetail.tasks');
  const [expanded, setExpanded] = useState(true);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(node.title);
  const [addingChild, setAddingChild] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { renameTask, setStatus } = useTaskMutations(onRefetch);

  const hasChildren = children.length > 0;

  const handleToggle = useCallback(() => {
    setExpanded((v) => !v);
  }, []);

  const handleTitleClick = useCallback(() => {
    setRenaming(true);
    setRenameValue(node.title);
    // Focus input on next tick
    setTimeout(() => inputRef.current?.focus(), 0);
  }, [node.title]);

  const handleRenameBlur = useCallback(async () => {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== node.title) {
      try {
        await renameTask(node.id, trimmed);
      } catch {
        // error handled by hook — revert to original
      }
    }
    setRenaming(false);
  }, [renameValue, node.title, node.id, renameTask]);

  const handleRenameKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        void handleRenameBlur();
      } else if (e.key === 'Escape') {
        setRenaming(false);
        setRenameValue(node.title);
      }
    },
    [handleRenameBlur, node.title],
  );

  const handleStatusToggle = useCallback(async () => {
    const nextStatus = STATUS_CYCLE[node.status];
    try {
      await setStatus(node.id, nextStatus);
    } catch {
      // error handled by hook
    }
  }, [node.id, node.status, setStatus]);

  return (
    <li>
      <div
        className="flex items-center gap-2 py-1.5 rounded hover:bg-muted/50 px-2 group"
        style={{ paddingLeft: `${depth * DEPTH_PX + 8}px` }}
      >
        {/* Expand/collapse toggle */}
        <button
          onClick={handleToggle}
          aria-label={expanded ? t('collapse') : t('expand')}
          className={cn(
            'p-0.5 rounded text-muted-foreground hover:text-foreground transition-colors shrink-0',
            !hasChildren && 'invisible',
          )}
          type="button"
        >
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5" aria-hidden />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" aria-hidden />
          )}
        </button>

        {/* Status checkbox */}
        <input
          type="checkbox"
          checked={node.status === 'done'}
          onChange={() => void handleStatusToggle()}
          aria-label={`Status: ${node.status}`}
          className="h-3.5 w-3.5 shrink-0 accent-primary cursor-pointer"
        />

        {/* Title or rename input */}
        {renaming ? (
          <input
            ref={inputRef}
            type="text"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={() => void handleRenameBlur()}
            onKeyDown={handleRenameKeyDown}
            className="flex-1 text-sm bg-transparent border-b border-primary outline-none"
            aria-label={t('rename')}
          />
        ) : (
          <button
            type="button"
            onClick={handleTitleClick}
            className={cn(
              'flex-1 text-sm text-left text-foreground hover:text-primary truncate min-w-0',
              node.status === 'done' && 'line-through text-muted-foreground',
            )}
          >
            {node.title}
          </button>
        )}

        {/* Dependency badge */}
        <DependencyBadge nodeId={node.id} edges={edges} allNodes={allNodes} />

        {/* Add child button */}
        <button
          type="button"
          onClick={() => setAddingChild(true)}
          aria-label={t('addChild')}
          className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded text-muted-foreground hover:text-foreground text-xs"
        >
          +
        </button>
      </div>

      {/* Recursive children */}
      {hasChildren && expanded && (
        <ul role="list">
          {[...children]
            .sort((a, b) => a.position - b.position)
            .map((child) => (
              <TaskTreeNode
                key={child.id}
                node={child}
                depth={depth + 1}
                children={allNodes.filter((n) => n.parent_node_id === child.id)}
                allNodes={allNodes}
                edges={edges}
                workItemId={workItemId}
                onRefetch={onRefetch}
              />
            ))}
        </ul>
      )}

      {/* Add child dialog */}
      {addingChild && (
        <TaskTreeAddDialog
          workItemId={workItemId}
          defaultParentId={node.id}
          allNodes={allNodes}
          onSuccess={() => {
            setAddingChild(false);
            onRefetch();
          }}
          onCancel={() => setAddingChild(false)}
        />
      )}
    </li>
  );
}
