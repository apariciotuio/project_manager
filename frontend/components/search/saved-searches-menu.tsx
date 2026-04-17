'use client';

import { useState, useRef, useEffect } from 'react';
import { Bookmark, Trash2, Plus, ChevronDown } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { useSavedSearches } from '@/hooks/use-saved-searches';
import type { SavedSearch } from '@/lib/types/work-item';

interface SavedSearchesMenuProps {
  /** Current filter state as query_params to save. */
  currentFilters: Record<string, unknown>;
  /** Called when a saved search is applied — parent should update filters. */
  onApply: (queryParams: Record<string, unknown>) => void;
}

/**
 * EP-09 — SavedSearchesMenu.
 * Dropdown showing list of saved searches + "Save current filters" input.
 */
export function SavedSearchesMenu({ currentFilters, onApply }: SavedSearchesMenuProps) {
  const tSaved = useTranslations('workspace.savedSearches');
  const { searches, isLoading, error, create, remove } = useSavedSearches();
  const [isOpen, setIsOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
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
    if (!saveName.trim()) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      await create({ name: saveName.trim(), query_params: currentFilters });
      setSaveName('');
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : tSaved('errorSave'));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(search: SavedSearch) {
    setDeletingId(search.id);
    try {
      await remove(search.id);
    } catch {
      // error state handled by hook
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <Button
        variant="outline"
        size="sm"
        aria-label={tSaved('title')}
        aria-expanded={isOpen}
        aria-haspopup="true"
        onClick={() => setIsOpen((o) => !o)}
        className="h-9 gap-1"
      >
        <Bookmark className="h-3.5 w-3.5" aria-hidden />
        {tSaved('title')}
        <ChevronDown className={`h-3 w-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} aria-hidden />
      </Button>

      {isOpen && (
        <div
          role="dialog"
          aria-label={tSaved('title')}
          className="absolute left-0 top-full z-50 mt-1 min-w-64 rounded-md border border-border bg-card shadow-md"
        >
          {/* Save current filters */}
          <div className="border-b border-border p-3">
            <p className="mb-2 text-body-sm font-medium text-foreground">{tSaved('saveButton')}</p>
            <div className="flex gap-2">
              <input
                type="text"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder={tSaved('namePlaceholder')}
                aria-label={tSaved('namePlaceholder')}
                onKeyDown={(e) => e.key === 'Enter' && void handleSave()}
                className="h-8 flex-1 rounded-md border border-input bg-background px-2 text-body-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <Button
                size="sm"
                variant="default"
                onClick={() => void handleSave()}
                disabled={isSaving || !saveName.trim()}
                className="h-8"
              >
                <Plus className="h-3 w-3 mr-1" aria-hidden />
                {tSaved('saveConfirm')}
              </Button>
            </div>
            {saveError && (
              <p role="alert" className="mt-1 text-body-sm text-destructive">{saveError}</p>
            )}
          </div>

          {/* List of saved searches */}
          <div className="max-h-60 overflow-y-auto p-1">
            {isLoading && (
              <p className="p-2 text-body-sm text-muted-foreground">{tSaved('title')}…</p>
            )}
            {error && (
              <p role="alert" className="p-2 text-body-sm text-destructive">{tSaved('errorLoad')}</p>
            )}
            {!isLoading && !error && searches.length === 0 && (
              <p className="p-2 text-body-sm text-muted-foreground">{tSaved('empty')}</p>
            )}
            {searches.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between gap-2 rounded-sm px-2 py-1.5 hover:bg-muted/50"
              >
                <button
                  type="button"
                  aria-label={tSaved('applyAria', { name: s.name })}
                  onClick={() => {
                    onApply(s.query_params);
                    setIsOpen(false);
                  }}
                  className="flex-1 text-left text-body-sm text-foreground truncate"
                >
                  {s.name}
                </button>
                <button
                  type="button"
                  aria-label={tSaved('deleteAria', { name: s.name })}
                  onClick={() => void handleDelete(s)}
                  disabled={deletingId === s.id}
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
