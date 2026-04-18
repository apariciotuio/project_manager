'use client';

import { useState, useEffect, useRef, useCallback, useId } from 'react';
import { cn } from '@/lib/utils';
import { getValidParentTypes } from '@/lib/hierarchy-rules';
import { apiGet } from '@/lib/api-client';
import type { WorkItemType } from '@/lib/types/work-item';
import type { WorkItemSummary } from '@/lib/types/hierarchy';

interface Envelope<T> {
  data: T;
}

interface SearchPage {
  items: WorkItemSummary[];
  total: number;
  cursor: string | null;
  has_next: boolean;
}

interface ParentPickerProps {
  projectId: string;
  childType: WorkItemType;
  value: WorkItemSummary | null;
  onChange: (item: WorkItemSummary | null) => void;
  label?: string;
  className?: string;
}

// Milestones have no parent — render nothing.
export function ParentPicker({
  projectId,
  childType,
  value,
  onChange,
  label = 'Parent',
  className,
}: ParentPickerProps) {
  const validTypes = getValidParentTypes(childType);
  // empty array = no parent allowed (root types) → don't render
  if (validTypes.length === 0) return null;

  return (
    <ParentPickerInner
      projectId={projectId}
      validTypes={validTypes}
      value={value}
      onChange={onChange}
      label={label}
      className={className}
    />
  );
}

interface InnerProps {
  projectId: string;
  validTypes: WorkItemType[];
  value: WorkItemSummary | null;
  onChange: (item: WorkItemSummary | null) => void;
  label: string;
  className?: string;
}

function ParentPickerInner({ projectId, validTypes, value, onChange, label, className }: InnerProps) {
  const id = useId();
  const listboxId = `${id}-listbox`;
  const [query, setQuery] = useState(value?.title ?? '');
  const [options, setOptions] = useState<WorkItemSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync display value when controlled value changes
  useEffect(() => {
    setQuery(value?.title ?? '');
  }, [value]);

  const search = useCallback(
    async (q: string) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (q) params.set('q', q);
        for (const t of validTypes) params.append('type', t);
        params.set('limit', '20');
        const res = await apiGet<Envelope<SearchPage>>(
          `/api/v1/projects/${projectId}/work-items?${params.toString()}`,
        );
        setOptions(res.data.items);
      } catch {
        setError('Error loading options');
        setOptions([]);
      } finally {
        setLoading(false);
      }
    },
    [projectId, validTypes],
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setQuery(v);
    setOpen(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(v), 300);
  };

  const handleFocus = () => {
    setOpen(true);
    search(query);
  };

  const handleSelect = (item: WorkItemSummary) => {
    onChange(item);
    setQuery(item.title);
    setOpen(false);
    setOptions([]);
  };

  const handleClear = () => {
    onChange(null);
    setQuery('');
    setOptions([]);
    setOpen(false);
    inputRef.current?.focus();
  };

  const handleBlur = () => {
    // Small delay so click on option registers before closing
    setTimeout(() => setOpen(false), 150);
  };

  const showDropdown = open && !loading && !error;
  const showEmpty = showDropdown && options.length === 0 && query.length > 0;

  return (
    <div className={cn('relative w-full', className)}>
      <label htmlFor={`${id}-input`} className="sr-only">
        {label}
      </label>
      <div className="flex items-center border border-input rounded-md bg-background">
        <input
          ref={inputRef}
          id={`${id}-input`}
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          autoComplete="off"
          className="flex-1 px-3 py-2 text-sm bg-transparent outline-none"
          placeholder={label}
          value={query}
          onChange={handleInputChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
        />
        {value && (
          <button
            type="button"
            aria-label="Clear selection"
            className="px-2 text-muted-foreground hover:text-foreground"
            onMouseDown={(e) => e.preventDefault()}
            onClick={handleClear}
          >
            ✕
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-1 text-xs text-destructive">
          {error}
        </p>
      )}

      {(showDropdown || showEmpty) && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md max-h-60 overflow-auto"
        >
          {showEmpty ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              No valid parents found
            </li>
          ) : (
            options.map((opt) => (
              <li
                key={opt.id}
                role="option"
                aria-selected={value?.id === opt.id}
                className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-accent"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleSelect(opt)}
              >
                <span className="text-xs rounded px-1 bg-muted text-muted-foreground uppercase">
                  {opt.type}
                </span>
                {opt.title}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
