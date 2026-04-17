'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api-client';
import type {
  AuditEvent,
  AuditEventsResponse,
  WorkspaceHealthResponse,
  WorkspaceMember,
  WorkspaceMembersResponse,
  Project,
  ProjectsResponse,
  ProjectResponse,
  ProjectCreateRequest,
  ProjectUpdateRequest,
  IntegrationConfig,
  IntegrationConfigsResponse,
  IntegrationConfigResponse,
  IntegrationConfigCreateRequest,
  Tag,
  TagsResponse,
  TagResponse,
  TagCreateRequest,
} from '@/lib/types/api';

// ─── Members ───────────────────────────────────────────────────────────────────

interface UseWorkspaceMembersResult {
  members: WorkspaceMember[];
  isLoading: boolean;
  error: Error | null;
}

export function useWorkspaceMembers(): UseWorkspaceMembersResult {
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<WorkspaceMembersResponse>('/api/v1/workspaces/members');
        if (!cancelled) setMembers(res.data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return { members, isLoading, error };
}

// ─── Audit ─────────────────────────────────────────────────────────────────────

export interface AuditFilters {
  action?: string;
  category?: string;
  page?: number;
}

interface UseAuditEventsResult {
  events: AuditEvent[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  error: Error | null;
}

export function useAuditEvents(filters: AuditFilters = {}): UseAuditEventsResult {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const { action, category, page: filterPage = 1 } = filters;

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const params = new URLSearchParams();
        params.set('page', String(filterPage));
        if (action) params.set('action', action);
        if (category) params.set('category', category);
        const res = await apiGet<AuditEventsResponse>(
          `/api/v1/admin/audit-events?${params.toString()}`
        );
        if (!cancelled) {
          setEvents(res.data.items);
          setTotal(res.data.total);
          setPage(res.data.page);
          setPageSize(res.data.page_size);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [action, category, filterPage]);

  return { events, total, page, pageSize, isLoading, error };
}

// ─── Health (workspace work item summary) ────────────────────────────────────

interface UseHealthResult {
  health: WorkspaceHealthResponse['data'] | null;
  isLoading: boolean;
  error: Error | null;
}

export function useHealth(): UseHealthResult {
  const [health, setHealth] = useState<WorkspaceHealthResponse['data'] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<WorkspaceHealthResponse>('/api/v1/admin/health');
        if (!cancelled) setHealth(res.data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return { health, isLoading, error };
}

// ─── Projects ──────────────────────────────────────────────────────────────────

interface UseProjectsResult {
  projects: Project[];
  isLoading: boolean;
  error: Error | null;
  createProject: (req: ProjectCreateRequest) => Promise<Project>;
  updateProject: (id: string, req: ProjectUpdateRequest) => Promise<Project>;
  deleteProject: (id: string) => Promise<void>;
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
    return () => { cancelled = true; };
  }, []);

  const createProject = useCallback(async (req: ProjectCreateRequest): Promise<Project> => {
    const res = await apiPost<ProjectResponse>('/api/v1/projects', req);
    setProjects((prev) => [...prev, res.data]);
    return res.data;
  }, []);

  const updateProject = useCallback(
    async (id: string, req: ProjectUpdateRequest): Promise<Project> => {
      const res = await apiPatch<ProjectResponse>(`/api/v1/projects/${id}`, req);
      setProjects((prev) => prev.map((p) => (p.id === id ? res.data : p)));
      return res.data;
    },
    []
  );

  const deleteProject = useCallback(async (id: string): Promise<void> => {
    await apiDelete(`/api/v1/projects/${id}`);
    setProjects((prev) => prev.filter((p) => p.id !== id));
  }, []);

  return { projects, isLoading, error, createProject, updateProject, deleteProject };
}

// ─── Integrations ──────────────────────────────────────────────────────────────

interface UseIntegrationsResult {
  configs: IntegrationConfig[];
  isLoading: boolean;
  error: Error | null;
  createIntegration: (req: IntegrationConfigCreateRequest) => Promise<IntegrationConfig>;
  deleteIntegration: (id: string) => Promise<void>;
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
    return () => { cancelled = true; };
  }, []);

  const createIntegration = useCallback(
    async (req: IntegrationConfigCreateRequest): Promise<IntegrationConfig> => {
      const res = await apiPost<IntegrationConfigResponse>('/api/v1/integrations/configs', req);
      setConfigs((prev) => [...prev, res.data]);
      return res.data;
    },
    []
  );

  const deleteIntegration = useCallback(async (id: string): Promise<void> => {
    await apiDelete(`/api/v1/integrations/configs/${id}`);
    setConfigs((prev) => prev.filter((c) => c.id !== id));
  }, []);

  return { configs, isLoading, error, createIntegration, deleteIntegration };
}

// ─── Tags ──────────────────────────────────────────────────────────────────────

interface UseTagsResult {
  tags: Tag[];
  isLoading: boolean;
  error: Error | null;
  createTag: (req: TagCreateRequest) => Promise<Tag>;
  archiveTag: (id: string) => Promise<void>;
  replaceTag: (updated: Tag) => void;
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
    return () => { cancelled = true; };
  }, []);

  const createTag = useCallback(async (req: TagCreateRequest): Promise<Tag> => {
    const res = await apiPost<TagResponse>('/api/v1/tags', req);
    setTags((prev) => [...prev, res.data]);
    return res.data;
  }, []);

  const archiveTag = useCallback(async (id: string): Promise<void> => {
    await apiDelete(`/api/v1/tags/${id}`);
    setTags((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const replaceTag = useCallback((updated: Tag): void => {
    setTags((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  }, []);

  return { tags, isLoading, error, createTag, archiveTag, replaceTag };
}
