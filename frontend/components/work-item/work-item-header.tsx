'use client';

import { useState, useRef } from 'react';
import Link from 'next/link';
import { StateBadge } from '@/components/domain/state-badge';
import { TypeBadge } from '@/components/domain/type-badge';
import { OwnerAvatar } from '@/components/domain/owner-avatar';
import { TagChip } from '@/components/domain/tag-chip';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { useWorkItemTags } from '@/hooks/work-item/use-work-item-tags';
import { useParentWorkItem } from '@/hooks/work-item/use-parent-work-item';
import type { WorkItemResponse } from '@/lib/types/work-item';
import type { WorkitemState } from '@/components/domain/state-badge';
import type { WorkitemType } from '@/components/domain/type-badge';

// Map backend state to StateBadge state
function toStateBadgeState(state: string): WorkitemState {
  const map: Record<string, WorkitemState> = {
    draft: 'draft',
    in_clarification: 'draft',
    in_review: 'in-review',
    changes_requested: 'blocked',
    partially_validated: 'in-review',
    ready: 'ready',
    exported: 'exported',
  };
  return map[state] ?? 'draft';
}

// Map backend type to TypeBadge type
function toTypeBadgeType(type: string): WorkitemType {
  const map: Record<string, WorkitemType> = {
    idea: 'idea',
    bug: 'bug',
    enhancement: 'change',
    task: 'task',
    initiative: 'epic',
    spike: 'spike',
    business_change: 'change',
    requirement: 'requirement',
    milestone: 'milestone',
    story: 'story',
  };
  return map[type] ?? 'task';
}

interface WorkItemHeaderProps {
  workItem: WorkItemResponse;
  slug?: string;
  onTitleChange?: (title: string) => void;
}

export function WorkItemHeader({ workItem, slug, onTitleChange }: WorkItemHeaderProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(workItem.title);
  const [tagPopoverOpen, setTagPopoverOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { tags, allTags, addTag, removeTag } = useWorkItemTags(workItem.id);
  const { parent } = useParentWorkItem(workItem.parent_work_item_id);

  // Tags not yet attached to this work item
  const attachedIds = new Set(tags.map((t) => t.id));
  const availableTags = allTags.filter((t) => !attachedIds.has(t.id));

  function startEdit() {
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  }

  function commitEdit() {
    setEditing(false);
    if (title.trim() && title !== workItem.title) {
      onTitleChange?.(title.trim());
    } else {
      setTitle(workItem.title);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') commitEdit();
    if (e.key === 'Escape') {
      setTitle(workItem.title);
      setEditing(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 pb-4 border-b border-border">
      {/* Parent link */}
      {parent && slug && (
        <div className="text-sm text-muted-foreground">
          Pertenece a:{' '}
          <Link
            href={`/workspace/${slug}/items/${parent.id}`}
            className="text-primary hover:underline font-medium"
          >
            {parent.title}
          </Link>{' '}
          <span className="opacity-60">({parent.type})</span>
        </div>
      )}

      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          {editing ? (
            <input
              ref={inputRef}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={handleKeyDown}
              aria-label="Título del elemento"
              className="w-full text-2xl font-semibold bg-transparent border-b border-primary outline-none focus:border-primary"
            />
          ) : (
            <button
              onClick={startEdit}
              aria-label="Editar título"
              className="text-left w-full text-2xl font-semibold text-foreground hover:text-primary transition-colors cursor-text truncate"
            >
              {title}
            </button>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0 mt-1">
          <span
            aria-label={`Completitud: ${workItem.completeness_score}%`}
            className="text-sm font-medium text-muted-foreground tabular-nums"
          >
            {workItem.completeness_score}%
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <TypeBadge type={toTypeBadgeType(workItem.type)} size="sm" />
        <StateBadge state={toStateBadgeState(workItem.state)} size="sm" />
        <OwnerAvatar size="xs" />
      </div>

      {/* Tag pills */}
      <div className="flex flex-wrap items-center gap-1.5 mt-1" aria-label="Etiquetas">
        {tags.map((tag) => (
          <TagChip
            key={tag.id}
            tag={tag}
            onRemove={(t) => void removeTag(t.id)}
          />
        ))}

        <Popover open={tagPopoverOpen} onOpenChange={setTagPopoverOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              aria-label="Añadir etiqueta"
              className="inline-flex items-center justify-center h-6 w-6 rounded-full border border-dashed border-muted-foreground text-muted-foreground hover:border-primary hover:text-primary text-sm leading-none transition-colors"
            >
              +
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-56 p-2">
            {availableTags.length === 0 ? (
              <p className="text-xs text-muted-foreground px-2 py-1">
                No hay etiquetas disponibles
              </p>
            ) : (
              <ul className="flex flex-col gap-0.5" role="listbox" aria-label="Etiquetas disponibles">
                {availableTags.map((tag) => (
                  <li key={tag.id} role="option" aria-selected={false}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full justify-start h-7 px-2 text-xs"
                      onClick={() => {
                        void addTag(tag.id);
                        setTagPopoverOpen(false);
                      }}
                    >
                      <span
                        className="inline-block h-2 w-2 rounded-full mr-1.5 shrink-0"
                        style={{ backgroundColor: tag.color }}
                        aria-hidden="true"
                      />
                      {tag.name}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}
