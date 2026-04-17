'use client';

import { useState } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { CompletenessBar } from '@/components/domain/completeness-bar';
import { LevelBadge } from '@/components/domain/level-badge';
import { SeverityBadge } from '@/components/domain/severity-badge';
import { useSpecification } from '@/hooks/work-item/use-specification';
import { useCompleteness } from '@/hooks/work-item/use-completeness';
import { apiGet } from '@/lib/api-client';
import { useEffect } from 'react';
import type { Gap, GapsResponse, SectionLock, LocksResponse } from '@/lib/types/work-item-detail';
import type { CompletenessLevel } from '@/lib/types/work-item-detail';
import { cn } from '@/lib/utils';
import { Lock } from 'lucide-react';

const SECTION_TYPE_LABELS: Record<string, string> = {
  problem_statement: 'Problema',
  acceptance_criteria: 'Criterios de aceptación',
  solution_description: 'Descripción de solución',
  technical_notes: 'Notas técnicas',
  business_justification: 'Justificación de negocio',
  scope: 'Alcance',
  out_of_scope: 'Fuera de alcance',
  dependencies: 'Dependencias',
  risks: 'Riesgos',
  mockups: 'Maquetas',
  definition_of_done: 'Definición de hecho',
};

function getSectionLabel(type: string): string {
  return SECTION_TYPE_LABELS[type] ?? type.replace(/_/g, ' ');
}

interface SectionEditorProps {
  id: string;
  sectionType: string;
  content: string | null;
  isLocked: boolean;
  lockedByName: string | null;
  onSave: (content: string) => Promise<void>;
}

function SectionEditor({
  id,
  sectionType,
  content,
  isLocked,
  lockedByName,
  onSave,
}: SectionEditorProps) {
  const [value, setValue] = useState(content ?? '');
  const [saving, setSaving] = useState(false);

  async function handleBlur() {
    if (value === (content ?? '')) return;
    setSaving(true);
    try {
      await onSave(value);
    } finally {
      setSaving(false);
    }
  }

  async function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (value !== (content ?? '')) {
        setSaving(true);
        try {
          await onSave(value);
        } finally {
          setSaving(false);
        }
      }
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label
          htmlFor={`section-${id}`}
          className="text-sm font-medium text-foreground"
        >
          {getSectionLabel(sectionType)}
        </label>
        {isLocked && (
          <span
            role="status"
            aria-label={`Bloqueado por ${lockedByName ?? 'otro usuario'}`}
            className="flex items-center gap-1 text-xs text-warning-foreground"
          >
            <Lock className="h-3 w-3" aria-hidden />
            {lockedByName ?? 'Otro usuario'}
          </span>
        )}
      </div>
      <Textarea
        id={`section-${id}`}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        disabled={isLocked || saving}
        placeholder={`Escribe aquí el contenido de "${getSectionLabel(sectionType)}"…`}
        rows={4}
        className={cn(
          'resize-y font-mono text-sm',
          isLocked && 'opacity-60 cursor-not-allowed'
        )}
        aria-label={getSectionLabel(sectionType)}
      />
      {saving && (
        <span className="text-xs text-muted-foreground" aria-live="polite">
          Guardando…
        </span>
      )}
    </div>
  );
}

interface SpecificationTabProps {
  workItemId: string;
}

export function SpecificationTab({ workItemId }: SpecificationTabProps) {
  const { sections, isLoading, updateSection } = useSpecification(workItemId);
  const { completeness, isLoading: completenessLoading } = useCompleteness(workItemId);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [locks, setLocks] = useState<SectionLock[]>([]);

  useEffect(() => {
    void apiGet<GapsResponse>(`/api/v1/work-items/${workItemId}/gaps`).then((r) =>
      setGaps(r.data)
    );
    void apiGet<LocksResponse>(`/api/v1/work-items/${workItemId}/locks`).then((r) =>
      setLocks(r.data)
    );
  }, [workItemId]);

  const lockMap = new Map(locks.map((l) => [l.section_id, l]));

  return (
    <div className="flex gap-6">
      {/* Section list */}
      <div className="flex-1 min-w-0 flex flex-col gap-6">
        {isLoading
          ? Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex flex-col gap-1.5">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-24 w-full" />
              </div>
            ))
          : sections.map((section) => {
              const lock = lockMap.get(section.id);
              return (
                <SectionEditor
                  key={section.id}
                  id={section.id}
                  sectionType={section.section_type}
                  content={section.content}
                  isLocked={!!lock}
                  lockedByName={lock?.locked_by_name ?? null}
                  onSave={(content) => updateSection(section.id, content)}
                />
              );
            })}
      </div>

      {/* Completeness sidebar */}
      <aside
        className="w-[300px] shrink-0 flex flex-col gap-4 rounded-lg border border-border p-4 self-start sticky top-4"
        aria-label="Panel de completitud"
      >
        <h3 className="text-sm font-semibold text-foreground">Completitud</h3>

        {completenessLoading ? (
          <>
            <Skeleton className="h-16 w-16 rounded-full self-center" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
          </>
        ) : completeness ? (
          <>
            {/* Score ring */}
            <div className="flex items-center gap-3">
              <div
                role="progressbar"
                aria-valuenow={completeness.score}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Completitud total: ${completeness.score}%`}
                className="relative h-16 w-16 shrink-0"
              >
                <svg className="h-16 w-16 -rotate-90" viewBox="0 0 64 64">
                  <circle cx="32" cy="32" r="28" fill="none" stroke="currentColor" strokeWidth="6" className="text-muted" />
                  <circle
                    cx="32"
                    cy="32"
                    r="28"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="6"
                    strokeDasharray={`${2 * Math.PI * 28}`}
                    strokeDashoffset={`${2 * Math.PI * 28 * (1 - completeness.score / 100)}`}
                    strokeLinecap="round"
                    className="text-primary transition-all duration-500"
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold">
                  {completeness.score}%
                </span>
              </div>
              <LevelBadge level={completeness.level as CompletenessLevel} />
            </div>

            {/* Dimensions */}
            <div className="flex flex-col gap-2">
              {completeness.dimensions.map((dim) => (
                <div key={dim.name} className="flex flex-col gap-0.5">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{dim.label}</span>
                    <span>{dim.score}%</span>
                  </div>
                  <CompletenessBar
                    level={scoreTolevel(dim.score)}
                    percent={dim.score}
                  />
                </div>
              ))}
            </div>
          </>
        ) : null}

        {/* Gap alerts */}
        {gaps.length > 0 && (
          <div className="flex flex-col gap-2 border-t border-border pt-3">
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Brechas
            </h4>
            {gaps.map((gap, i) => (
              <div key={i} className="flex flex-col gap-0.5">
                <SeverityBadge severity={gap.severity} size="sm" />
                <p className="text-xs text-foreground">{gap.message}</p>
              </div>
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}

function scoreTolevel(score: number): CompletenessLevel {
  if (score >= 90) return 'ready';
  if (score >= 60) return 'high';
  if (score >= 30) return 'medium';
  return 'low';
}
