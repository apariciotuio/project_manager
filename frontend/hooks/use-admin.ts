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
  AdminMember,
  AdminMembersResponse,
  PatchMemberRequest,
  InviteMemberRequest,
  ValidationRule,
  ValidationRulesResponse,
  CreateValidationRuleRequest,
  PatchValidationRuleRequest,
  JiraConfig,
  JiraConfigsResponse,
  JiraConfigResponse,
  CreateJiraConfigRequest,
  JiraTestResult,
  ContextPreset,
  ContextPresetsResponse,
  ContextPresetResponse,
  CreateContextPresetRequest,
  PatchContextPresetRequest,
  AdminDashboard,
  AdminDashboardResponse,
  OrphanedWorkItem,
  PendingInvitation,
  FailedExport,
  ConfigBlockedWorkItem,
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

// ─── Admin Members (full, with capabilities) ─────────────────────────────────

interface UseAdminMembersResult {
  members: AdminMember[];
  pagination: { cursor: string | null; has_next: boolean } | null;
  isLoading: boolean;
  error: Error | null;
  inviteMember: (req: InviteMemberRequest) => Promise<{ invitation_id: string }>;
  updateMember: (id: string, req: PatchMemberRequest) => Promise<{ id: string; state: string }>;
  refetch: () => void;
}

export function useAdminMembers(params?: {
  state?: string;
  teamless?: boolean;
  cursor?: string;
}): UseAdminMembersResult {
  const [members, setMembers] = useState<AdminMember[]>([]);
  const [pagination, setPagination] = useState<{ cursor: string | null; has_next: boolean } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  const { state, teamless, cursor } = params ?? {};

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const qs = new URLSearchParams();
        if (state) qs.set('state', state);
        if (teamless) qs.set('teamless', 'true');
        if (cursor) qs.set('cursor', cursor);
        const query = qs.toString();
        const res = await apiGet<AdminMembersResponse>(
          `/api/v1/admin/members${query ? `?${query}` : ''}`
        );
        if (!cancelled) {
          setMembers(res.data.items);
          setPagination(res.data.pagination);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [state, teamless, cursor, tick]);

  const inviteMember = useCallback(async (req: InviteMemberRequest) => {
    const res = await apiPost<{ data: { invitation_id: string }; message: string }>(
      '/api/v1/admin/members',
      req
    );
    setTick((t) => t + 1);
    return res.data;
  }, []);

  const updateMember = useCallback(async (id: string, req: PatchMemberRequest) => {
    const res = await apiPatch<{ data: { id: string; state: string }; message: string }>(
      `/api/v1/admin/members/${id}`,
      req
    );
    setMembers((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...req, state: req.state ?? m.state } : m))
    );
    return res.data;
  }, []);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  return { members, pagination, isLoading, error, inviteMember, updateMember, refetch };
}

// ─── Validation Rules ─────────────────────────────────────────────────────────

interface UseValidationRulesResult {
  rules: ValidationRule[];
  isLoading: boolean;
  error: Error | null;
  createRule: (req: CreateValidationRuleRequest) => Promise<ValidationRule>;
  updateRule: (id: string, req: PatchValidationRuleRequest) => Promise<ValidationRule>;
  deleteRule: (id: string) => Promise<void>;
}

export function useValidationRules(params?: {
  project_id?: string;
  work_item_type?: string;
}): UseValidationRulesResult {
  const [rules, setRules] = useState<ValidationRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const { project_id, work_item_type } = params ?? {};

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const qs = new URLSearchParams();
        if (project_id) qs.set('project_id', project_id);
        if (work_item_type) qs.set('work_item_type', work_item_type);
        const query = qs.toString();
        const res = await apiGet<ValidationRulesResponse>(
          `/api/v1/admin/rules/validation${query ? `?${query}` : ''}`
        );
        if (!cancelled) setRules(res.data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [project_id, work_item_type]);

  const createRule = useCallback(async (req: CreateValidationRuleRequest): Promise<ValidationRule> => {
    const res = await apiPost<{ data: ValidationRule; message: string }>(
      '/api/v1/admin/rules/validation',
      req
    );
    setRules((prev) => [...prev, res.data]);
    return res.data;
  }, []);

  const updateRule = useCallback(async (id: string, req: PatchValidationRuleRequest): Promise<ValidationRule> => {
    const res = await apiPatch<{ data: ValidationRule; message: string }>(
      `/api/v1/admin/rules/validation/${id}`,
      req
    );
    setRules((prev) => prev.map((r) => (r.id === id ? res.data : r)));
    return res.data;
  }, []);

  const deleteRule = useCallback(async (id: string): Promise<void> => {
    await apiDelete(`/api/v1/admin/rules/validation/${id}`);
    setRules((prev) => prev.filter((r) => r.id !== id));
  }, []);

  return { rules, isLoading, error, createRule, updateRule, deleteRule };
}

// ─── Jira Configs ─────────────────────────────────────────────────────────────

interface UseJiraConfigsResult {
  configs: JiraConfig[];
  isLoading: boolean;
  error: Error | null;
  createConfig: (req: CreateJiraConfigRequest) => Promise<Pick<JiraConfig, 'id' | 'state'>>;
  updateConfig: (id: string, body: { credentials?: Record<string, string>; state?: string }) => Promise<JiraConfig>;
  testConnection: (id: string) => Promise<JiraTestResult>;
}

export function useJiraConfigs(): UseJiraConfigsResult {
  const [configs, setConfigs] = useState<JiraConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<JiraConfigsResponse>('/api/v1/admin/integrations/jira');
        if (!cancelled) setConfigs(res.data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const createConfig = useCallback(async (req: CreateJiraConfigRequest) => {
    const res = await apiPost<{ data: Pick<JiraConfig, 'id' | 'state'>; message: string }>(
      '/api/v1/admin/integrations/jira',
      req
    );
    return res.data;
  }, []);

  const updateConfig = useCallback(async (id: string, body: { credentials?: Record<string, string>; state?: string }) => {
    const res = await apiPatch<JiraConfigResponse>(`/api/v1/admin/integrations/jira/${id}`, body);
    setConfigs((prev) => prev.map((c) => (c.id === id ? res.data : c)));
    return res.data;
  }, []);

  const testConnection = useCallback(async (id: string): Promise<JiraTestResult> => {
    const res = await apiPost<{ data: JiraTestResult; message: string }>(
      `/api/v1/admin/integrations/jira/${id}/test`,
      {}
    );
    return res.data;
  }, []);

  return { configs, isLoading, error, createConfig, updateConfig, testConnection };
}

// ─── Context Presets ──────────────────────────────────────────────────────────

interface UseContextPresetsResult {
  presets: ContextPreset[];
  isLoading: boolean;
  error: Error | null;
  createPreset: (req: CreateContextPresetRequest) => Promise<ContextPreset>;
  updatePreset: (id: string, req: PatchContextPresetRequest) => Promise<ContextPreset>;
  deletePreset: (id: string) => Promise<void>;
}

export function useContextPresets(): UseContextPresetsResult {
  const [presets, setPresets] = useState<ContextPreset[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<ContextPresetsResponse>('/api/v1/admin/context-presets');
        if (!cancelled) setPresets(res.data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const createPreset = useCallback(async (req: CreateContextPresetRequest): Promise<ContextPreset> => {
    const res = await apiPost<ContextPresetResponse>('/api/v1/admin/context-presets', req);
    setPresets((prev) => [...prev, res.data]);
    return res.data;
  }, []);

  const updatePreset = useCallback(async (id: string, req: PatchContextPresetRequest): Promise<ContextPreset> => {
    const res = await apiPatch<ContextPresetResponse>(`/api/v1/admin/context-presets/${id}`, req);
    setPresets((prev) => prev.map((p) => (p.id === id ? res.data : p)));
    return res.data;
  }, []);

  const deletePreset = useCallback(async (id: string): Promise<void> => {
    await apiDelete(`/api/v1/admin/context-presets/${id}`);
    setPresets((prev) => prev.filter((p) => p.id !== id));
  }, []);

  return { presets, isLoading, error, createPreset, updatePreset, deletePreset };
}

// ─── Admin Dashboard ──────────────────────────────────────────────────────────

interface UseAdminDashboardResult {
  dashboard: AdminDashboard | null;
  isLoading: boolean;
  error: Error | null;
}

export function useAdminDashboard(projectId?: string): UseAdminDashboardResult {
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const qs = projectId ? `?project_id=${projectId}` : '';
        const res = await apiGet<AdminDashboardResponse>(`/api/v1/admin/dashboard${qs}`);
        if (!cancelled) setDashboard(res.data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  return { dashboard, isLoading, error };
}

// ─── Support Tools ────────────────────────────────────────────────────────────

interface UseSupportToolsResult {
  orphanedItems: OrphanedWorkItem[];
  pendingInvitations: PendingInvitation[];
  failedExports: FailedExport[];
  configBlockedItems: ConfigBlockedWorkItem[];
  isLoading: boolean;
  error: Error | null;
  reassignOwner: (workItemId: string, newOwnerId: string) => Promise<void>;
  retryAllExports: () => Promise<void>;
}

export function useSupportTools(): UseSupportToolsResult {
  const [orphanedItems, setOrphanedItems] = useState<OrphanedWorkItem[]>([]);
  const [pendingInvitations, setPendingInvitations] = useState<PendingInvitation[]>([]);
  const [failedExports, setFailedExports] = useState<FailedExport[]>([]);
  const [configBlockedItems, setConfigBlockedItems] = useState<ConfigBlockedWorkItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const [orphaned, pending, failed, blocked] = await Promise.all([
          apiGet<{ data: OrphanedWorkItem[] }>('/api/v1/admin/support/orphaned-work-items'),
          apiGet<{ data: PendingInvitation[] }>('/api/v1/admin/support/pending-invitations'),
          apiGet<{ data: FailedExport[] }>('/api/v1/admin/support/failed-exports'),
          apiGet<{ data: ConfigBlockedWorkItem[] }>('/api/v1/admin/support/config-blocked-work-items'),
        ]);
        if (!cancelled) {
          setOrphanedItems(orphaned.data);
          setPendingInvitations(pending.data);
          setFailedExports(failed.data);
          setConfigBlockedItems(blocked.data);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const reassignOwner = useCallback(async (workItemId: string, newOwnerId: string): Promise<void> => {
    await apiPost('/api/v1/admin/support/reassign-owner', {
      work_item_id: workItemId,
      new_owner_id: newOwnerId,
    });
    setOrphanedItems((prev) => prev.filter((i) => i.id !== workItemId));
  }, []);

  const retryAllExports = useCallback(async (): Promise<void> => {
    await apiPost('/api/v1/admin/support/failed-exports/retry-all', {});
  }, []);

  return {
    orphanedItems, pendingInvitations, failedExports, configBlockedItems,
    isLoading, error, reassignOwner, retryAllExports,
  };
}
