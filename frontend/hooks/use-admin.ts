'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiPatch } from '@/lib/api-client';
import type {
  AuditEvent,
  AuditEventsResponse,
  HealthResponse,
  Project,
  ProjectsResponse,
  ProjectResponse,
  ProjectCreateRequest,
  IntegrationConfig,
  IntegrationConfigsResponse,
  Tag,
  TagsResponse,
  TagResponse,
  TagCreateRequest,
} from '@/lib/types/api';

// ─── Audit ─────────────────────────────────────────────────────────────────────

interface UseAuditEventsResult {
  events: AuditEvent[];
  total: number;
  isLoading: boolean;
  error: Error | null;
}

export function useAuditEvents(): UseAuditEventsResult {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<AuditEventsResponse>('/api/v1/admin/audit-events');
        if (!cancelled) {
          setEvents(res.data);
          setTotal(res.total);
        }
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

  return { events, total, isLoading, error };
}

// ─── Health ────────────────────────────────────────────────────────────────────

interface UseHealthResult {
  health: HealthResponse | null;
  isLoading: boolean;
  error: Error | null;
}

export function useHealth(): UseHealthResult {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<HealthResponse>('/api/v1/admin/health');
        if (!cancelled) setHealth(res);
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

  return { health, isLoading, error };
}

// ─── Projects ──────────────────────────────────────────────────────────────────

interface UseProjectsResult {
  projects: Project[];
  isLoading: boolean;
  error: Error | null;
  createProject: (req: ProjectCreateRequest) => Promise<Project>;
}

export function useProjects(): UseProjectsResult {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<ProjectsResponse>('/api/v1/projects');
        if (!cancelled) setProjects(res.data);
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

  const createProject = useCallback(async (req: ProjectCreateRequest): Promise<Project> => {
    const res = await apiPost<ProjectResponse>('/api/v1/projects', req);
    setProjects((prev) => [...prev, res.data]);
    return res.data;
  }, []);

  return { projects, isLoading, error, createProject };
}

// ─── Integrations ──────────────────────────────────────────────────────────────

interface UseIntegrationsResult {
  configs: IntegrationConfig[];
  isLoading: boolean;
  error: Error | null;
}

export function useIntegrations(): UseIntegrationsResult {
  const [configs, setConfigs] = useState<IntegrationConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<IntegrationConfigsResponse>('/api/v1/integrations/configs');
        if (!cancelled) setConfigs(res.data);
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

  return { configs, isLoading, error };
}

// ─── Tags ──────────────────────────────────────────────────────────────────────

interface UseTagsResult {
  tags: Tag[];
  isLoading: boolean;
  error: Error | null;
  createTag: (req: TagCreateRequest) => Promise<Tag>;
  archiveTag: (id: string) => Promise<void>;
}

export function useTags(): UseTagsResult {
  const [tags, setTags] = useState<Tag[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<TagsResponse>('/api/v1/tags');
        if (!cancelled) setTags(res.data);
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

  const createTag = useCallback(async (req: TagCreateRequest): Promise<Tag> => {
    const res = await apiPost<TagResponse>('/api/v1/tags', req);
    setTags((prev) => [...prev, res.data]);
    return res.data;
  }, []);

  const archiveTag = useCallback(async (id: string): Promise<void> => {
    await apiPatch(`/api/v1/tags/${id}`, { archived: true });
    setTags((prev) => prev.map((t) => (t.id === id ? { ...t, archived: true } : t)));
  }, []);

  return { tags, isLoading, error, createTag, archiveTag };
}
