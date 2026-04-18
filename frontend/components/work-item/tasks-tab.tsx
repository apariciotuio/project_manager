'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useTaskTree } from '@/hooks/work-item/use-task-tree';
import { useTaskMutations } from '@/hooks/work-item/use-task-mutations';
import type { TaskNode, TaskStatus } from '@/lib/types/task';
import { cn } from '@/lib/utils';
import { ChevronRight, ChevronDown, Plus } from 'lucide-react';

const STATUS_LABELS: Record<TaskStatus, string> = {
  draft: 'Borrador',
  in_progress: 'En progreso',
  done: 'Hecho',
};

const STATUS_CLASSES: Record<TaskStatus, string> = {
  draft: 'bg-muted text-muted-foreground',
  in_progress: 'bg-info/10 text-info-foreground',
  done: 'bg-level-ready text-level-ready-foreground',
};

interface AddTaskFormProps {
  parentId: string | null;
  onAdd: (title: string, parentId: string | null) => Promise<void>;
}

function AddTaskForm({ parentId, onAdd }: AddTaskFormProps) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setSubmitting(true);
    try {
      await onAdd(title.trim(), parentId);
      setTitle('');
      setOpen(false);
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) {
    return (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setOpen(true)}
        className="gap-1 text-muted-foreground hover:text-foreground"
        aria-label="Añadir tarea"
      >
        <Plus className="h-3.5 w-3.5" aria-hidden />
        Añadir tarea
      </Button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <Input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Nombre de la tarea…"
        disabled={submitting}
        aria-label="Nombre de la nueva tarea"
        className="h-8 text-sm"
      />
      <Button type="submit" size="sm" disabled={submitting || !title.trim()}>
        Añadir
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => {
          setOpen(false);
          setTitle('');
        }}
      >
        Cancelar
      </Button>
    </form>
  );
}

interface TaskRowProps {
  node: TaskNode;
  depth: number;
  childNodes: TaskNode[];
  allNodes: TaskNode[];
  onAdd: (title: string, parentId: string | null) => Promise<void>;
}

function TaskRow({ node, depth, childNodes, allNodes, onAdd }: TaskRowProps) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = childNodes.length > 0;

  return (
    <li>
      <div
        className={cn('flex items-center gap-2 py-1.5 rounded hover:bg-muted/50 px-2 group')}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
      >
        <button
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? 'Contraer' : 'Expandir'}
          className={cn(
            'p-0.5 rounded text-muted-foreground hover:text-foreground transition-colors',
            !hasChildren && 'invisible'
          )}
        >
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5" aria-hidden />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" aria-hidden />
          )}
        </button>
        <span className="flex-1 text-sm text-foreground truncate">{node.title}</span>
        <span
          className={cn(
            'text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0',
            STATUS_CLASSES[node.status]
          )}
          aria-label={`Estado: ${STATUS_LABELS[node.status]}`}
        >
          {STATUS_LABELS[node.status]}
        </span>
      </div>
      {hasChildren && expanded && (
        <ul role="list">
          {childNodes.map((child) => (
            <TaskRow
              key={child.id}
              node={child}
              depth={depth + 1}
              childNodes={allNodes.filter((n) => n.parent_node_id === child.id)}
              allNodes={allNodes}
              onAdd={onAdd}
            />
          ))}
        </ul>
      )}
      {expanded && (
        <div style={{ paddingLeft: `${(depth + 1) * 20 + 8}px` }} className="py-0.5">
          <AddTaskForm parentId={node.id} onAdd={onAdd} />
        </div>
      )}
    </li>
  );
}

interface TasksTabProps {
  workItemId: string;
}

export function TasksTab({ workItemId }: TasksTabProps) {
  const { tree, isLoading, refetch } = useTaskTree(workItemId);
  const { createTask } = useTaskMutations(refetch);

  const handleAdd = useCallback(
    async (title: string, parentId: string | null) => {
      await createTask(workItemId, title, parentId);
    },
    [createTask, workItemId],
  );

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  const roots = tree.nodes.filter((n) => n.parent_node_id === null);

  return (
    <div className="flex flex-col gap-2">
      <ul role="list" className="flex flex-col">
        {roots.map((node) => (
          <TaskRow
            key={node.id}
            node={node}
            depth={0}
            childNodes={tree.nodes.filter((n) => n.parent_node_id === node.id)}
            allNodes={tree.nodes}
            onAdd={handleAdd}
          />
        ))}
      </ul>
      <div className="pl-2">
        <AddTaskForm parentId={null} onAdd={handleAdd} />
      </div>
    </div>
  );
}
