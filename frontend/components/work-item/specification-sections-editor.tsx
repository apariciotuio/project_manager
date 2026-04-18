'use client';

import { useState, useRef, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useSections } from '@/hooks/work-item/use-sections';
import { usePendingSuggestion } from '@/hooks/use-pending-suggestion';
import { PendingSuggestionCard } from './pending-suggestion-card';
import type { Section, GenerationSource } from '@/lib/types/specification';

interface SpecificationSectionsEditorProps {
  workItemId: string;
  canEdit: boolean;
  onSectionSaved?: () => void;
}

function getSectionLabel(t: (key: string) => string, sectionType: string): string {
  return t(`sectionLabels.${sectionType}`) ?? sectionType.replace(/_/g, ' ');
}

function GenerationBadge({ source }: { source: GenerationSource }) {
  const t = useTranslations('workspace.itemDetail.specification');
  const label = t(`generationSource.${source}`);
  return (
    <Badge
      variant="outline"
      className="text-xs px-1.5 py-0 font-normal"
      data-testid="generation-badge"
    >
      {label}
    </Badge>
  );
}

const DEBOUNCE_MS = 600;

interface SectionRowProps {
  section: Section;
  canEdit: boolean;
  onSave: (sectionId: string, content: string) => Promise<void>;
}

function SectionRow({ section, canEdit, onSave }: SectionRowProps) {
  const t = useTranslations('workspace.itemDetail.specification');
  const [value, setValue] = useState(section.content);
  const [saving, setSaving] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // EP-22: conflict mode detection — track focus + dirty buffer
  const [isFocused, setIsFocused] = useState(false);
  const isDirty = value !== section.content;
  const isConflict = isFocused || isDirty;

  // EP-22: pending suggestion subscription
  const { suggestion, clear: clearSuggestion } = usePendingSuggestion(section.section_type);

  const triggerSave = useCallback(
    async (content: string) => {
      if (content === section.content) return;
      setSaving(true);
      try {
        await onSave(section.id, content);
      } finally {
        setSaving(false);
      }
    },
    [section.id, section.content, onSave]
  );

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const next = e.target.value;
    setValue(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void triggerSave(next);
    }, DEBOUNCE_MS);
  }

  function handleBlur() {
    setIsFocused(false);
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    void triggerSave(value);
  }

  function handleFocus() {
    setIsFocused(true);
  }

  // EP-22 suggestion handlers
  const handleAccept = useCallback(async () => {
    if (!suggestion) return;
    await onSave(section.id, suggestion.proposed_content);
    clearSuggestion();
  }, [suggestion, onSave, section.id, clearSuggestion]);

  const handleReject = useCallback(() => {
    clearSuggestion();
  }, [clearSuggestion]);

  const handleEdit = useCallback(() => {
    if (!suggestion) return;
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    setValue(suggestion.proposed_content);
    clearSuggestion();
  }, [suggestion, clearSuggestion]);

  const label = getSectionLabel(t, section.section_type);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <label
          htmlFor={`section-${section.id}`}
          className="text-sm font-medium text-foreground"
        >
          {label}
          {section.is_required && (
            <span className="ml-0.5 text-destructive" aria-hidden>
              *
            </span>
          )}
        </label>
        <div className="flex items-center gap-1.5">
          <GenerationBadge source={section.generation_source} />
          <span className="text-xs text-muted-foreground">v{section.version}</span>
        </div>
      </div>

      {/* EP-22: pending suggestion card — only shown when canEdit */}
      {canEdit && suggestion && (
        <PendingSuggestionCard
          currentContent={value}
          proposedContent={suggestion.proposed_content}
          rationale={suggestion.rationale}
          onAccept={handleAccept}
          onReject={handleReject}
          onEdit={handleEdit}
          conflictMode={isConflict}
        />
      )}

      <Textarea
        id={`section-${section.id}`}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        onFocus={handleFocus}
        disabled={!canEdit || saving}
        placeholder={t('placeholder')}
        rows={4}
        className={cn('resize-y font-mono text-sm min-h-[120px]', !canEdit && 'opacity-60 cursor-not-allowed')}
        aria-label={label}
      />
      {saving && (
        <span
          className="text-xs text-muted-foreground"
          aria-live="polite"
          data-testid={`saving-indicator-${section.id}`}
        >
          {t('saving')}
        </span>
      )}
    </div>
  );
}

export function SpecificationSectionsEditor({
  workItemId,
  canEdit,
  onSectionSaved,
}: SpecificationSectionsEditorProps) {
  const { sections, isLoading, patchSection } = useSections(workItemId, {
    onPatchSuccess: onSectionSaved,
  });

  const handleSave = useCallback(
    async (sectionId: string, content: string) => {
      await patchSection(sectionId, { content });
    },
    [patchSection]
  );

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex flex-col gap-1.5">
            <Skeleton className="h-4 w-32" data-testid="section-skeleton" />
            <Skeleton className="h-24 w-full" data-testid="section-skeleton" />
          </div>
        ))}
      </div>
    );
  }

  if (sections.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4">
        No specification sections available.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {sections.map((section) => (
        <SectionRow
          key={section.id}
          section={section}
          canEdit={canEdit}
          onSave={handleSave}
        />
      ))}
    </div>
  );
}
