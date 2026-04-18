'use client';

import { useState, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { TaskTreeNode } from '@/components/work-item/task-tree-node';
import { TaskTreeAddDialog } from '@/components/work-item/task-tree-add-dialog';
import { Button } from '@/components/ui/button';
import { useTaskMutations } from '@/hooks/work-item/use-task-mutations';
import type { TaskTree as TaskTreeType, TaskNode } from '@/lib/types/task';

interface TaskTreeProps {
  tree: TaskTreeType;
  workItemId: string;
  onRefetch: () => void;
}

/** Returns true if `ancestorId` is an ancestor of `nodeId` in the tree. */
function isAncestorOf(
  nodeId: string,
  ancestorId: string,
  nodes: TaskNode[],
): boolean {
  const node = nodes.find((n) => n.id === nodeId);
  if (!node) return false;
  if (node.parent_node_id === null) return false;
  if (node.parent_node_id === ancestorId) return true;
  return isAncestorOf(node.parent_node_id, ancestorId, nodes);
}

export function TaskTree({ tree, workItemId, onRefetch }: TaskTreeProps) {
  const t = useTranslations('workspace.itemDetail.tasks');
  const [addingRoot, setAddingRoot] = useState(false);
  const [cycleError, setCycleError] = useState<string | null>(null);
  // Optimistic local node list for rollback
  const [localNodes, setLocalNodes] = useState<TaskNode[] | null>(null);

  const { reparent, isPending } = useTaskMutations(onRefetch);

  const nodes = localNodes ?? tree.nodes;

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
    useSensor(KeyboardSensor),
  );

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const draggedId = String(event.active.id);
      const overId = event.over ? String(event.over.id) : null;

      if (!overId || overId === draggedId) return;

      // Client-side cycle detection: dragged node cannot be dropped onto one
      // of its own descendants (that would make an ancestor into a descendant).
      if (isAncestorOf(overId, draggedId, nodes)) {
        setCycleError(t('dnd.cycleError'));
        return;
      }

      // Optimistic update: update parent_node_id locally before API call
      const snapshot = nodes;
      setLocalNodes(
        nodes.map((n) =>
          n.id === draggedId ? { ...n, parent_node_id: overId } : n,
        ),
      );
      setCycleError(null);

      try {
        await reparent(draggedId, overId);
        setLocalNodes(null); // let tree prop take over after refetch
      } catch (err: unknown) {
        // Roll back optimistic update
        setLocalNodes(snapshot);
        // Check if it's a server-side cycle error
        const maybeCode =
          (err as { responseBody?: { error?: { code?: string } } })
            ?.responseBody?.error?.code;
        if (maybeCode === 'CYCLE_DETECTED' || (err as Error)?.message?.includes('cycle')) {
          setCycleError(t('dnd.cycleError'));
        } else {
          setCycleError(t('dnd.genericError'));
        }
      }
    },
    [nodes, reparent, t],
  );

  const roots = [...nodes]
    .filter((n) => n.parent_node_id === null)
    .sort((a, b) => a.position - b.position);

  if (roots.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-muted-foreground">{t('empty')}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setAddingRoot(true)}
          aria-label={t('addRoot')}
        >
          + {t('addRoot')}
        </Button>
        {addingRoot && (
          <TaskTreeAddDialog
            workItemId={workItemId}
            defaultParentId={null}
            allNodes={tree.nodes}
            onSuccess={() => {
              setAddingRoot(false);
              onRefetch();
            }}
            onCancel={() => setAddingRoot(false)}
          />
        )}
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      onDragEnd={(e) => void handleDragEnd(e)}
    >
      <div className="flex flex-col gap-2">
        {cycleError && (
          <p
            role="alert"
            className="text-sm text-destructive"
            aria-live="assertive"
            data-testid="dnd-cycle-error"
          >
            {cycleError}
          </p>
        )}
        <ul role="list" className="flex flex-col">
          {roots.map((node) => (
            <TaskTreeNode
              key={node.id}
              node={node}
              depth={0}
              childNodes={nodes.filter((n) => n.parent_node_id === node.id)}
              allNodes={nodes}
              edges={tree.edges}
              workItemId={workItemId}
              onRefetch={onRefetch}
              isDragDisabled={isPending}
            />
          ))}
        </ul>
        <div className="pl-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setAddingRoot(true)}
            aria-label={t('addRoot')}
            className="gap-1 text-muted-foreground hover:text-foreground"
          >
            + {t('addRoot')}
          </Button>
        </div>
        {addingRoot && (
          <TaskTreeAddDialog
            workItemId={workItemId}
            defaultParentId={null}
            allNodes={tree.nodes}
            onSuccess={() => {
              setAddingRoot(false);
              onRefetch();
            }}
            onCancel={() => setAddingRoot(false)}
          />
        )}
      </div>
    </DndContext>
  );
}
