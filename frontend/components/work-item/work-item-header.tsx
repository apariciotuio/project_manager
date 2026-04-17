'use client';

import { useState, useRef } from 'react';
import { StateBadge } from '@/components/domain/state-badge';
import { TypeBadge } from '@/components/domain/type-badge';
import { OwnerAvatar } from '@/components/domain/owner-avatar';
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
  onTitleChange?: (title: string) => void;
}

export function WorkItemHeader({ workItem, onTitleChange }: WorkItemHeaderProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(workItem.title);
  const inputRef = useRef<HTMLInputElement>(null);

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
    </div>
  );
}
