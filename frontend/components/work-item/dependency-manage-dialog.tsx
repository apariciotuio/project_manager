'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { useTaskMutations } from '@/hooks/work-item/use-task-mutations';
import type { TaskEdge, TaskNode } from '@/lib/types/task';

interface DependencyManageDialogProps {
  sourceNode: TaskNode;
  allNodes: TaskNode[];
  edges: TaskEdge[];
  workItemId: string;
  onSuccess: () => void;
  onCancel: () => void;
}

/**
 * Dialog for managing blocking dependencies of a single task node.
 * - Lists current outgoing "blocks" edges with a remove button per edge.
 * - Provides a select to add a new blocks edge to a sibling task.
 */
export function DependencyManageDialog({
  sourceNode,
  allNodes,
  edges,
  workItemId: _workItemId,
  onSuccess,
  onCancel,
}: DependencyManageDialogProps) {
  const t = useTranslations('workspace.itemDetail.tasks');

  // Outgoing blocks edges from the source node
  const outgoing = edges.filter(
    (e) => e.from_node_id === sourceNode.id && e.kind === 'blocks',
  );

  // Candidate targets: all nodes except the source and already-blocked nodes
  const blockedIds = new Set(outgoing.map((e) => e.to_node_id));
  const candidates = allNodes.filter(
    (n) => n.id !== sourceNode.id && !blockedIds.has(n.id),
  );

  const [selectedTarget, setSelectedTarget] = useState<string>('');
  const { createDependency, deleteDependency, isPending } = useTaskMutations(onSuccess);

  async function handleAdd() {
    if (!selectedTarget) return;
    await createDependency(sourceNode.id, selectedTarget, 'blocks');
  }

  async function handleRemove(edgeId: string) {
    await deleteDependency(sourceNode.id, edgeId);
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('dependencyManageTitle')}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          {/* Existing dependencies */}
          <div className="flex flex-col gap-2">
            {outgoing.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('dependencyNone')}</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {outgoing.map((edge) => {
                  const target = allNodes.find((n) => n.id === edge.to_node_id);
                  return (
                    <li
                      key={edge.id}
                      className="flex items-center justify-between gap-2 text-sm"
                    >
                      <span className="truncate">{target?.title ?? edge.to_node_id}</span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={t('dependencyRemove')}
                        disabled={isPending}
                        onClick={() => void handleRemove(edge.id)}
                        className="shrink-0 text-destructive hover:text-destructive"
                      >
                        {t('dependencyRemove')}
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Add new dependency */}
          {candidates.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dep-target">{t('dependencyTargetLabel')}</Label>
              <div className="flex gap-2">
                <select
                  id="dep-target"
                  value={selectedTarget}
                  onChange={(e) => setSelectedTarget(e.target.value)}
                  disabled={isPending}
                  className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={t('dependencyTargetLabel')}
                >
                  <option value="">{t('dependencyTargetPlaceholder')}</option>
                  {candidates.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.title}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  disabled={isPending || !selectedTarget}
                  onClick={() => void handleAdd()}
                  aria-label={t('dependencyAdd')}
                >
                  {t('dependencyAdd')}
                </Button>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            disabled={isPending}
          >
            {t('dialogCancel')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
