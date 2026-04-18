'use client';

import { useRouter, usePathname, useSearchParams } from 'next/navigation';

export interface SortOption {
  value: string;
  label: string;
}

export const SORT_OPTIONS: SortOption[] = [
  { value: 'updated_desc', label: 'Updated (newest)' },
  { value: 'updated_asc', label: 'Updated (oldest)' },
  { value: 'created_desc', label: 'Created (newest)' },
  { value: 'title_asc', label: 'Title (A–Z)' },
  { value: 'completeness_desc', label: 'Completeness (high)' },
];

export function SortControl() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const current = searchParams.get('sort') ?? '';

  function handleChange(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set('sort', value);
    } else {
      params.delete('sort');
    }
    router.replace(`${pathname}?${params.toString()}`);
  }

  return (
    <select
      aria-label="Sort items"
      value={current}
      onChange={(e) => handleChange(e.target.value)}
      className="h-9 rounded-md border border-input bg-background px-3 text-body-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
    >
      <option value="">Sort by…</option>
      {SORT_OPTIONS.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
