'use client';

/**
 * EP-09 — SavedFilterPresets
 * Filter-bar component for saving/applying/deleting saved filter combinations.
 * Uses /api/v1/saved-searches endpoint (saved-filters endpoint not built; same purpose).
 */
import { useState, useRef, useEffect } from 'react';
import { Bookmark, Trash2, ChevronDown } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useSavedSearches } from '@/hooks/use-saved-searches';

interface SavedFilterPresetsProps {
  currentFilters: Record<string, unknown>;
  onApply: (queryParams: Record<string, unknown>) => void;
}

export function SavedFilterPresets({ currentFilters, onApply }: SavedFilterPresetsProps) {
  const t = useTranslations('workspace.savedSearches');
  const { searches, isLoading, create, remove } = useSavedSearches();
  const [isOpen, setIsOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, [isOpen]);

  async function handleSave() {
    if (!saveName.trim() || isSaving) return;
    setIsSaving(true);
    try {
      await create({ name: saveName.trim(), query_params: currentFilters });
      setSaveName('');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (deletingId) return;
    setDeletingId(id);
    try {
      await remove(id);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        data-testid="saved-filter-presets-toggle"
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-md border border-input bg-background px-3 h-9 text-sm text-foreground hover:bg-accent"
        aria-expanded={isOpen}
      >
        <Bookmark className="h-3.5 w-3.5" aria-hidden />
        {t('title')}
        <ChevronDown className={`h-3 w-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} aria-hidden />
      </button>

      {isOpen && (
        <div className="absolute left-0 top-full z-50 mt-1 w-64 rounded-md border border-border bg-popover shadow-md">
          {/* Save current filters */}
          <div className="flex gap-1 p-2 border-b border-border">
            <input
              data-testid="saved-filter-presets-name-input"
              type="text"
              placeholder={t('savePlaceholder')}
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void handleSave()}
              className="flex-1 rounded-md border border-input bg-background px-2 py-1 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <button
              data-testid="saved-filter-presets-save-btn"
              type="button"
              onClick={() => void handleSave()}
              disabled={!saveName.trim() || isSaving}
              className="rounded-md bg-primary px-2 py-1 text-xs text-primary-foreground disabled:opacity-50"
            >
              {t('save')}
            </button>
          </div>

          {/* Saved presets list */}
          <div className="max-h-52 overflow-y-auto p-1">
            {isLoading && (
              <p className="px-2 py-1.5 text-xs text-muted-foreground">{t('loading')}</p>
            )}
            {!isLoading && searches.length === 0 && (
              <p data-testid="saved-filter-presets-empty" className="px-2 py-1.5 text-xs text-muted-foreground italic">
                {t('empty')}
              </p>
            )}
            {searches.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-accent group"
              >
                <button
                  type="button"
                  onClick={() => { onApply(s.query_params as Record<string, unknown>); setIsOpen(false); }}
                  className="flex-1 text-left text-xs text-foreground truncate"
                >
                  {s.name}
                </button>
                <button
                  data-testid={`delete-preset-${s.id}`}
                  type="button"
                  onClick={() => void handleDelete(s.id)}
                  disabled={deletingId === s.id}
                  aria-label={t('delete')}
                  className="ml-1 rounded p-0.5 text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive disabled:opacity-50"
                >
                  <Trash2 className="h-3 w-3" aria-hidden />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
