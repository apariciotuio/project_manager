'use client';

import { useState, useEffect, useCallback } from 'react';
import { getProjectHierarchy } from '@/lib/api/hierarchy';
import { TreeView } from './TreeView';
import type { HierarchyPage } from '@/lib/types/hierarchy';

interface HierarchyPageViewProps {
  projectId: string;
  projectName: string;
}

type Status = 'idle' | 'loading' | 'error' | 'success';

export function HierarchyPageView({ projectId, projectName }: HierarchyPageViewProps) {
  const [status, setStatus] = useState<Status>('loading');
  const [data, setData] = useState<HierarchyPage | null>(null);
  const [cursor, setCursor] = useState<string | undefined>(undefined);

  const load = useCallback(
    async (nextCursor?: string) => {
      setStatus('loading');
      try {
        const page = await getProjectHierarchy(projectId, nextCursor);
        setData((prev) => {
          if (!prev || !nextCursor) return page;
          // Append roots on load-more
          return {
            ...page,
            roots: [...prev.roots, ...page.roots],
            unparented: [...prev.unparented, ...page.unparented],
          };
        });
        setStatus('success');
      } catch {
        setStatus('error');
      }
    },
    [projectId],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const handleLoadMore = () => {
    if (data?.meta.next_cursor) {
      setCursor(data.meta.next_cursor);
      void load(data.meta.next_cursor);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">{projectName}</h1>

      {status === 'error' && (
        <div className="flex flex-col items-center gap-2 py-8 text-destructive">
          <p>Failed to load hierarchy</p>
          <button
            type="button"
            onClick={() => void load(cursor)}
            className="text-sm underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      <TreeView
        roots={data?.roots ?? []}
        unparented={data?.unparented ?? []}
        meta={data?.meta ?? { truncated: false, next_cursor: null }}
        isLoading={status === 'loading'}
        onLoadMore={handleLoadMore}
      />
    </div>
  );
}
