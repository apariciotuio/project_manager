'use client';

import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api-client';
import type { Template, TemplatesResponse } from '@/lib/types/api';

interface UseTemplatesResult {
  templates: Template[];
  isLoading: boolean;
  error: Error | null;
}

export function useTemplates(): UseTemplatesResult {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<TemplatesResponse>('/api/v1/templates');
        if (!cancelled) setTemplates(res.data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { templates, isLoading, error };
}
