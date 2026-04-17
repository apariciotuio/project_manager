'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { TaskTreeNode } from '@/components/work-item/task-tree-node';
import { TaskTreeAddDialog } from '@/components/work-item/task-tree-add-dialog';
import { Button } from '@/components/ui/button';
import type { TaskTree as TaskTreeType } from '@/lib/types/task';

interface TaskTreeProps {
  tree: TaskTreeType;
  workItemId: string;
  onRefetch: () => void;
}

export function TaskTree({ tree, workItemId, onRefetch }: TaskTreeProps) {
  const t = useTranslations('workspace.itemDetail.tasks');
  const [addingRoot, setAddingRoot] = useState(false);

  const roots = [...tree.nodes]
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
    <div className="flex flex-col gap-2">
      <ul role="list" className="flex flex-col">
        {roots.map((node) => (
          <TaskTreeNode
            key={node.id}
            node={node}
            depth={0}
            children={tree.nodes.filter((n) => n.parent_node_id === node.id)}
            allNodes={tree.nodes}
            edges={tree.edges}
            workItemId={workItemId}
            onRefetch={onRefetch}
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
  );
}
