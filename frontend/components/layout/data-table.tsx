'use client';

import { cn } from '@/lib/utils';
import { useState, type ReactNode } from 'react';

export type SortDirection = 'asc' | 'desc';

export interface Column<T> {
  key: keyof T & string;
  header: string;
  sortable?: boolean;
  render?: (value: T[keyof T], row: T) => ReactNode;
}

interface DataTableProps<T extends Record<string, unknown>> {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  loading?: boolean;
  emptyState?: ReactNode;
  onSort?: (key: string, direction: SortDirection) => void;
  className?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  getRowKey,
  loading = false,
  emptyState,
  onSort,
  className,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDirection>('asc');

  function handleHeaderClick(col: Column<T>) {
    if (!col.sortable || !onSort) return;
    let nextDir: SortDirection = 'asc';
    if (sortKey === col.key) {
      nextDir = sortDir === 'asc' ? 'desc' : 'asc';
    }
    setSortKey(col.key);
    setSortDir(nextDir);
    onSort(col.key, nextDir);
  }

  if (loading) {
    return (
      <div data-testid="data-table-loading" className={cn('space-y-2', className)}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
    );
  }

  if (rows.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  return (
    <div
      data-testid="data-table-scroll-container"
      className={cn('overflow-x-auto w-full', className)}
    >
      <table className="w-full min-w-max caption-bottom text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={col.key}
                role="columnheader"
                scope="col"
                onClick={() => handleHeaderClick(col)}
                aria-sort={
                  sortKey === col.key
                    ? sortDir === 'asc'
                      ? 'ascending'
                      : 'descending'
                    : undefined
                }
                className={cn(
                  'px-4 py-3 text-left font-medium text-muted-foreground whitespace-nowrap',
                  col.sortable && onSort && 'cursor-pointer select-none hover:text-foreground',
                )}
              >
                <span className="flex items-center gap-1">
                  {col.header}
                  {col.sortable && onSort && (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      className="h-3 w-3 opacity-50"
                      aria-hidden="true"
                    >
                      <path d="m7 15 5 5 5-5" />
                      <path d="m7 9 5-5 5 5" />
                    </svg>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={getRowKey(row)}
              className="border-b border-border/50 transition-colors hover:bg-muted/50"
            >
              {columns.map((col) => (
                <td key={col.key} className="px-4 py-3 whitespace-nowrap">
                  {col.render
                    ? col.render(row[col.key], row)
                    : String(row[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
