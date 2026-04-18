'use client';

import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { TimelineEventType, TimelineActorType } from '@/lib/types/work-item-detail';

export interface TimelineFilterState {
  eventTypes: TimelineEventType[];
  actorTypes: TimelineActorType[];
  dateRange: { from: string | null; to: string | null };
}

export interface TimelineFiltersProps extends TimelineFilterState {
  onChange: (filters: TimelineFilterState) => void;
}

const ALL_EVENT_TYPES: Array<{ value: TimelineEventType; label: string }> = [
  { value: 'state_transition', label: 'State transition' },
  { value: 'comment_added', label: 'Comment added' },
  { value: 'comment_deleted', label: 'Comment deleted' },
  { value: 'version_created', label: 'Version created' },
  { value: 'review_submitted', label: 'Review submitted' },
  { value: 'export_triggered', label: 'Export triggered' },
  { value: 'owner_changed', label: 'Owner changed' },
  { value: 'section_updated', label: 'Section updated' },
  { value: 'task_added', label: 'Task added' },
  { value: 'task_completed', label: 'Task completed' },
  { value: 'review_requested', label: 'Review requested' },
  { value: 'review_completed', label: 'Review completed' },
  { value: 'tag_added', label: 'Tag added' },
  { value: 'tag_removed', label: 'Tag removed' },
];

const ALL_ACTOR_TYPES: Array<{ value: TimelineActorType; label: string }> = [
  { value: 'human', label: 'Human' },
  { value: 'ai_suggestion', label: 'AI suggestion' },
  { value: 'system', label: 'System' },
];

const EMPTY_FILTERS: TimelineFilterState = {
  eventTypes: [],
  actorTypes: [],
  dateRange: { from: null, to: null },
};

export function TimelineFilters({
  eventTypes,
  actorTypes,
  dateRange,
  onChange,
}: TimelineFiltersProps) {
  function toggleEventType(type: TimelineEventType) {
    const next = eventTypes.includes(type)
      ? eventTypes.filter((t) => t !== type)
      : [...eventTypes, type];
    onChange({ eventTypes: next, actorTypes, dateRange });
  }

  function toggleActorType(type: TimelineActorType) {
    const next = actorTypes.includes(type)
      ? actorTypes.filter((t) => t !== type)
      : [...actorTypes, type];
    onChange({ eventTypes, actorTypes: next, dateRange });
  }

  function handleFromChange(value: string) {
    onChange({ eventTypes, actorTypes, dateRange: { ...dateRange, from: value || null } });
  }

  function handleToChange(value: string) {
    onChange({ eventTypes, actorTypes, dateRange: { ...dateRange, to: value || null } });
  }

  const isDirty =
    eventTypes.length > 0 ||
    actorTypes.length > 0 ||
    dateRange.from !== null ||
    dateRange.to !== null;

  return (
    <div className="flex flex-col gap-4 p-3 border border-border rounded-md bg-muted/30">
      <fieldset>
        <legend className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
          Event type
        </legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {ALL_EVENT_TYPES.map(({ value, label }) => {
            const id = `et-${value}`;
            return (
              <div key={value} className="flex items-center gap-1.5">
                <Checkbox
                  id={id}
                  checked={eventTypes.includes(value)}
                  onCheckedChange={() => toggleEventType(value)}
                  aria-label={label}
                />
                <Label htmlFor={id} className="text-sm cursor-pointer">
                  {label}
                </Label>
              </div>
            );
          })}
        </div>
      </fieldset>

      <fieldset>
        <legend className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
          Actor type
        </legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {ALL_ACTOR_TYPES.map(({ value, label }) => {
            const id = `at-${value}`;
            return (
              <div key={value} className="flex items-center gap-1.5">
                <Checkbox
                  id={id}
                  checked={actorTypes.includes(value)}
                  onCheckedChange={() => toggleActorType(value)}
                  aria-label={label}
                />
                <Label htmlFor={id} className="text-sm cursor-pointer">
                  {label}
                </Label>
              </div>
            );
          })}
        </div>
      </fieldset>

      <div className="flex flex-wrap gap-4 items-end">
        <div className="flex flex-col gap-1">
          <Label htmlFor="tf-from" className="text-xs text-muted-foreground">
            From
          </Label>
          <Input
            id="tf-from"
            type="date"
            value={dateRange.from ?? ''}
            onChange={(e) => handleFromChange(e.target.value)}
            className="w-40 h-8 text-sm"
            aria-label="From"
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="tf-to" className="text-xs text-muted-foreground">
            To
          </Label>
          <Input
            id="tf-to"
            type="date"
            value={dateRange.to ?? ''}
            onChange={(e) => handleToChange(e.target.value)}
            className="w-40 h-8 text-sm"
            aria-label="To"
          />
        </div>

        {isDirty && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange(EMPTY_FILTERS)}
            aria-label="Reset filters"
          >
            Reset filters
          </Button>
        )}
      </div>
    </div>
  );
}
