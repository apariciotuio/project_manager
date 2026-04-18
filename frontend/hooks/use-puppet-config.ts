'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiPatch } from '@/lib/api-client';
import type {
  PuppetConfig,
  PuppetConfigCreate,
  PuppetConfigUpdate,
  PuppetConfigListResponse,
  PuppetConfigResponse,
} from '@/lib/types/puppet';

interface UsePuppetConfigResult {
  config: PuppetConfig | null;
  isLoading: boolean;
  error: Error | null;
  createConfig: (req: PuppetConfigCreate) => Promise<PuppetConfig>;
  updateConfig: (id: string, req: PuppetConfigUpdate) => Promise<PuppetConfig>;
  runHealthCheck: (id: string) => Promise<PuppetConfig>;
}

export function usePuppetConfig(): UsePuppetConfigResult {
  const [config, setConfig] = useState<PuppetConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<PuppetConfigListResponse>('/api/v1/admin/integrations/puppet');
        if (!cancelled) setConfig(res.data[0] ?? null);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const createConfig = useCallback(async (req: PuppetConfigCreate): Promise<PuppetConfig> => {
    const res = await apiPost<PuppetConfigResponse>('/api/v1/admin/integrations/puppet', req);
    setConfig(res.data);
    return res.data;
  }, []);

  const updateConfig = useCallback(async (id: string, req: PuppetConfigUpdate): Promise<PuppetConfig> => {
    const res = await apiPatch<PuppetConfigResponse>(`/api/v1/admin/integrations/puppet/${id}`, req);
    setConfig(res.data);
    return res.data;
  }, []);

  const runHealthCheck = useCallback(async (id: string): Promise<PuppetConfig> => {
    const res = await apiPost<PuppetConfigResponse>(`/api/v1/admin/puppet/${id}/health-check`, {});
    setConfig(res.data);
    return res.data;
  }, []);

  return { config, isLoading, error, createConfig, updateConfig, runHealthCheck };
}
