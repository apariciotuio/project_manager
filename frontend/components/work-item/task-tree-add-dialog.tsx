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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useTaskMutations } from '@/hooks/work-item/use-task-mutations';
import type { TaskNode } from '@/lib/types/task';

const NO_PARENT = '__none__';

interface TaskTreeAddDialogProps {
  workItemId: string;
  /** Pre-filled parent node id (from clicking + on a node). null = root task. */
  defaultParentId: string | null;
  /** All current nodes (for parent select options). */
  allNodes: TaskNode[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function TaskTreeAddDialog({
  workItemId,
  defaultParentId,
  allNodes,
  onSuccess,
  onCancel,
}: TaskTreeAddDialogProps) {
  const t = useTranslations('workspace.itemDetail.tasks');
  const [title, setTitle] = useState('');
  const [parentId, setParentId] = useState<string>(defaultParentId ?? NO_PARENT);

  const { createTask, isPending } = useTaskMutations(onSuccess);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    const resolvedParent = parentId === NO_PARENT ? null : parentId;
    await createTask(workItemId, trimmed, resolvedParent);
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('dialogTitle')}</DialogTitle>
        </DialogHeader>

        <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="task-title">{t('dialogTitleLabel')}</Label>
            <Input
              id="task-title"
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t('dialogTitleLabel')}
              disabled={isPending}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="task-parent">{t('dialogParentLabel')}</Label>
            <Select value={parentId} onValueChange={setParentId}>
              <SelectTrigger id="task-parent">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_PARENT}>— {t('dialogParentLabel')} —</SelectItem>
                {allNodes.map((n) => (
                  <SelectItem key={n.id} value={n.id}>
                    {n.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
            <Button
              type="submit"
              disabled={isPending || !title.trim()}
            >
              {t('dialogSubmit')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
