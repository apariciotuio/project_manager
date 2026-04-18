'use client';

import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import type { TimelineEventType, ActorType } from '@/lib/types/versions';

const EVENT_TYPES: TimelineEventType[] = [
  'state_transition',
  'comment_added',
  'comment_deleted',
  'version_created',
  'review_submitted',
  'export_triggered',
];

const ACTOR_TYPES: ActorType[] = ['human', 'ai_suggestion', 'system'];

export interface TimelineFiltersValue {
  eventTypes: TimelineEventType[];
  actorTypes: ActorType[];
  dateRange: { from: string | null; to: string | null };
}

interface TimelineFiltersProps extends TimelineFiltersValue {
  onChange: (filters: TimelineFiltersValue) => void;
}

export function TimelineFilters({
  eventTypes,
  actorTypes,
  dateRange,
  onChange,
}: TimelineFiltersProps) {
  const t = useTranslations('workspace.itemDetail.timeline.filters');

  const toggle = <T extends string>(list: T[], value: T): T[] =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  return (
    <div className="flex flex-col gap-3 p-3 border rounded-md bg-muted/40">
      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-xs font-medium text-muted-foreground">
          {t('eventTypeLabel')}
        </legend>
        <div className="flex flex-wrap gap-3">
          {EVENT_TYPES.map((type) => (
            <label key={type} className="inline-flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={eventTypes.includes(type)}
                onChange={() =>
                  onChange({
                    eventTypes: toggle(eventTypes, type),
                    actorTypes,
                    dateRange,
                  })
                }
                aria-label={t(`eventType.${type}`)}
              />
              {t(`eventType.${type}`)}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-xs font-medium text-muted-foreground">
          {t('actorTypeLabel')}
        </legend>
        <div className="flex flex-wrap gap-3">
          {ACTOR_TYPES.map((type) => (
            <label key={type} className="inline-flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={actorTypes.includes(type)}
                onChange={() =>
                  onChange({
                    eventTypes,
                    actorTypes: toggle(actorTypes, type),
                    dateRange,
                  })
                }
                aria-label={t(`actorType.${type}`)}
              />
              {t(`actorType.${type}`)}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-xs font-medium text-muted-foreground">
          {t('dateRangeLabel')}
        </legend>
        <div className="flex flex-wrap gap-3 items-center">
          <label className="inline-flex items-center gap-1.5 text-sm">
            <span>{t('fromLabel')}</span>
            <input
              type="date"
              value={dateRange.from ?? ''}
              onChange={(e) =>
                onChange({
                  eventTypes,
                  actorTypes,
                  dateRange: { from: e.target.value || null, to: dateRange.to },
                })
              }
              aria-label={t('fromLabel')}
              className="border rounded px-2 py-1 text-sm"
            />
          </label>
          <label className="inline-flex items-center gap-1.5 text-sm">
            <span>{t('toLabel')}</span>
            <input
              type="date"
              value={dateRange.to ?? ''}
              onChange={(e) =>
                onChange({
                  eventTypes,
                  actorTypes,
                  dateRange: { from: dateRange.from, to: e.target.value || null },
                })
              }
              aria-label={t('toLabel')}
              className="border rounded px-2 py-1 text-sm"
            />
          </label>
        </div>
      </fieldset>

      <div className="flex justify-end">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            onChange({
              eventTypes: [],
              actorTypes: [],
              dateRange: { from: null, to: null },
            })
          }
        >
          {t('resetLabel')}
        </Button>
      </div>
    </div>
  );
}
