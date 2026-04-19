'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useAuth } from '@/app/providers/auth-provider';
import {
  useWorkspaceMembers,
  useAuditEvents,
  useHealth,
  useProjects,
  useIntegrations,
  useTags,
  type AuditFilters,
} from '@/hooks/use-admin';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { RelativeTime } from '@/components/domain/relative-time';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Plus, Archive, Pencil, Trash2 } from 'lucide-react';
import { PuppetConfigForm } from '@/components/admin/puppet-config-form';
import { DocSourcesTable } from '@/components/admin/doc-sources-table';
import { AddDocSourceModal } from '@/components/admin/add-doc-source-modal';
import { MembersTabEnhanced } from '@/components/admin/members-tab-enhanced';
import { ValidationRulesTab } from '@/components/admin/validation-rules-tab';
import { AdminDashboardTab } from '@/components/admin/admin-dashboard-tab';
import { JiraConfigTab } from '@/components/admin/jira-config-tab';
import { ContextPresetsTab } from '@/components/admin/context-presets-tab';
import { SupportTab } from '@/components/admin/support-tab';
import { usePuppetConfig } from '@/hooks/use-puppet-config';
import { useDocSources } from '@/hooks/use-doc-sources';
import type { PuppetConfig } from '@/lib/types/puppet';
import type {
  ProjectCreateRequest,
  ProjectUpdateRequest,
  TagCreateRequest,
  IntegrationConfigCreateRequest,
  Tag,
  Project,
  IntegrationConfig,
} from '@/lib/types/api';
import { isSessionExpired } from '@/lib/types/auth';
import { PageContainer } from '@/components/layout/page-container';
import { useFormErrors } from '@/lib/errors/use-form-errors';
import { TagEditModal } from '@/components/admin/tag-edit-modal';

interface AdminPageProps {
  params: { slug: string };
}

// ─── Shared primitives ────────────────────────────────────────────────────────

function TabSkeleton({ testId }: { testId: string }) {
  return (
    <div data-testid={testId} className="space-y-3 animate-pulse">
      {[1, 2, 3].map((n) => (
        <div key={n} className="h-12 rounded-md bg-muted" />
      ))}
    </div>
  );
}

function TabError({ testId, message }: { testId: string; message: string }) {
  return (
    <div
      data-testid={testId}
      role="alert"
      className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-body-sm text-destructive"
    >
      {message}
    </div>
  );
}

function TabEmpty({ testId, message }: { testId: string; message: string }) {
  return (
    <p data-testid={testId} className="py-8 text-center text-muted-foreground">
      {message}
    </p>
  );
}

// ─── Members Tab ──────────────────────────────────────────────────────────────

function MembersTab() {
  const { members, isLoading, error } = useWorkspaceMembers();

  if (isLoading) return <TabSkeleton testId="members-skeleton" />;
  if (error) {
    if (isSessionExpired(error)) return null;
    return <TabError testId="members-error" message={`No se pudo cargar los miembros: ${error.message}`} />;
  }

  if (members.length === 0) {
    return <TabEmpty testId="members-empty" message="No hay miembros en este workspace." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-body-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="pb-2 pr-4 font-medium">Nombre</th>
            <th className="pb-2 pr-4 font-medium">Email</th>
            <th className="pb-2 font-medium">Rol</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.id} className="border-b last:border-0">
              <td className="py-2 pr-4 font-medium">{m.full_name}</td>
              <td className="py-2 pr-4 text-muted-foreground">{m.email}</td>
              <td className="py-2">
                <Badge variant="secondary">{m.role}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Audit Tab ────────────────────────────────────────────────────────────────

const AUDIT_ACTIONS = ['create', 'update', 'delete', 'archive', 'comment', 'assign'];

function AuditTab() {
  const [filters, setFilters] = useState<AuditFilters>({});
  const { events, total, isLoading, error } = useAuditEvents(filters);

  if (isLoading) return <TabSkeleton testId="audit-skeleton" />;
  if (error) {
    if (isSessionExpired(error)) return null;
    return <TabError testId="audit-error" message={`No se pudo cargar la auditoría: ${error.message}`} />;
  }

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="audit-action">Acción</Label>
          <select
            id="audit-action"
            data-testid="audit-action-filter"
            value={filters.action ?? ''}
            onChange={(e) =>
              setFilters((f) => ({ ...f, action: e.target.value || undefined }))
            }
            className="rounded-md border bg-background px-3 py-1.5 text-body-sm"
          >
            <option value="">Todas</option>
            {AUDIT_ACTIONS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="audit-category">Categoría</Label>
          <Input
            id="audit-category"
            placeholder="Ej. work_item"
            value={filters.category ?? ''}
            onChange={(e) =>
              setFilters((f) => ({ ...f, category: e.target.value || undefined }))
            }
            className="h-9 w-40"
          />
        </div>
      </div>

      <p className="text-body-sm text-muted-foreground">{total} eventos</p>

      <div className="overflow-x-auto">
        <table className="w-full text-body-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 pr-4 font-medium">Actor</th>
              <th className="pb-2 pr-4 font-medium">Acción</th>
              <th className="pb-2 pr-4 font-medium">Recurso</th>
              <th className="pb-2 font-medium">Fecha</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-b last:border-0">
                <td className="py-2 pr-4">{e.actor_display ?? '—'}</td>
                <td className="py-2 pr-4 font-mono text-xs">{e.action}</td>
                <td className="py-2 pr-4 text-muted-foreground">
                  {e.entity_type ?? '—'}
                  {e.entity_id ? ` / ${e.entity_id.slice(0, 8)}` : ''}
                </td>
                <td className="py-2">
                  <RelativeTime iso={e.created_at} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {events.length === 0 && (
          <TabEmpty testId="audit-empty" message="No hay eventos de auditoría." />
        )}
      </div>
    </div>
  );
}

// ─── Health Tab ───────────────────────────────────────────────────────────────

const STATE_COLORS: Record<string, string> = {
  draft: 'bg-slate-400',
  in_review: 'bg-amber-400',
  ready: 'bg-blue-500',
  in_progress: 'bg-indigo-500',
  done: 'bg-green-500',
  archived: 'bg-gray-300',
  blocked: 'bg-red-500',
};

function stateColor(state: string): string {
  return STATE_COLORS[state] ?? 'bg-muted-foreground';
}

function HealthTab() {
  const { health, isLoading, error } = useHealth();

  if (isLoading) return <TabSkeleton testId="health-skeleton" />;
  if (error) {
    if (isSessionExpired(error)) return null;
    return <TabError testId="health-error" message={`No se pudo cargar el resumen: ${error.message}`} />;
  }
  if (!health) return null;

  const states = Object.entries(health.work_items_by_state);
  const total = health.total_active;

  return (
    <div className="space-y-6">
      <div className="flex items-baseline gap-2">
        <span className="text-h2 font-semibold text-foreground">{total}</span>
        <span className="text-muted-foreground">activos</span>
      </div>

      {states.length === 0 ? (
        <TabEmpty testId="health-empty" message="Aún no hay elementos de trabajo." />
      ) : (
        <>
          {/* Divided bar */}
          <div className="flex h-4 w-full overflow-hidden rounded-full">
            {states.map(([state, count]) => {
              const pct = total > 0 ? (count / total) * 100 : 0;
              return (
                <div
                  key={state}
                  data-testid={`health-bar-segment-${state}`}
                  className={`${stateColor(state)} transition-all`}
                  style={{ width: `${pct}%` }}
                  title={`${state}: ${count}`}
                />
              );
            })}
          </div>

          {/* Legend */}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {states.map(([state, count]) => (
              <div key={state} className="flex items-center gap-2">
                <span className={`h-3 w-3 rounded-full ${stateColor(state)}`} />
                <span className="text-body-sm capitalize text-muted-foreground">
                  {state.replace(/_/g, ' ')}
                </span>
                <span className="ml-auto font-semibold">{count}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Projects Tab ─────────────────────────────────────────────────────────────

interface ProjectFormState {
  name: string;
  description: string;
}

function ProjectsTab() {
  const t = useTranslations('workspace.admin');
  const { projects, isLoading, error, createProject, updateProject, deleteProject } =
    useProjects();

  const [createOpen, setCreateOpen] = useState(false);
  const [editProject, setEditProject] = useState<Project | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);

  const [form, setForm] = useState<ProjectFormState>({ name: '', description: '' });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const { fieldErrors, handleApiError, clearErrors } = useFormErrors();

  function openCreate() {
    setForm({ name: '', description: '' });
    clearErrors();
    setCreateOpen(true);
  }

  function openEdit(p: Project) {
    setForm({ name: p.name, description: p.description ?? '' });
    clearErrors();
    setEditProject(p);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    clearErrors();
    try {
      const req: ProjectCreateRequest = { name: form.name.trim() };
      if (form.description.trim()) req.description = form.description.trim();
      await createProject(req);
      setCreateOpen(false);
    } catch (err) {
      handleApiError(err);
    } finally {
      setSaving(false);
    }
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editProject || !form.name.trim()) return;
    setSaving(true);
    clearErrors();
    try {
      const req: ProjectUpdateRequest = { name: form.name.trim() };
      if (form.description.trim()) req.description = form.description.trim();
      await updateProject(editProject.id, req);
      setEditProject(null);
    } catch (err) {
      handleApiError(err);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteProject(deleteTarget.id);
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  }

  if (isLoading) return <TabSkeleton testId="projects-skeleton" />;
  if (error) {
    if (isSessionExpired(error)) return null;
    return <TabError testId="projects-error" message={`No se pudieron cargar los proyectos: ${error.message}`} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={openCreate}>
          <Plus className="mr-1.5 h-4 w-4" />
          Nuevo proyecto
        </Button>
      </div>

      {projects.length === 0 ? (
        <TabEmpty testId="projects-empty" message="No hay proyectos." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {projects.map((p) => (
            <Card key={p.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-body">{p.name}</CardTitle>
                  <div className="flex shrink-0 gap-1">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      aria-label={`Editar ${p.name}`}
                      onClick={() => openEdit(p)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      aria-label={`Eliminar ${p.name}`}
                      onClick={() => setDeleteTarget(p)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              {p.description && (
                <CardContent className="pt-0">
                  <p className="text-body-sm text-muted-foreground">{p.description}</p>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={(v) => { setCreateOpen(v); if (!v) clearErrors(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nuevo proyecto</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => void handleCreate(e)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="proj-name">Nombre *</Label>
              <Input
                id="proj-name"
                placeholder="Nombre del proyecto"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
                aria-invalid={!!fieldErrors['name']}
                aria-describedby={fieldErrors['name'] ? 'proj-name-error' : undefined}
              />
              {fieldErrors['name'] && (
                <p id="proj-name-error" role="alert" className="text-body-sm text-destructive">
                  {fieldErrors['name']}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="proj-desc">Descripción</Label>
              <Textarea
                id="proj-desc"
                placeholder={t('projects.dialog.descPlaceholder')}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={3}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={!form.name.trim() || saving}>
                {saving ? 'Creando...' : 'Crear'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={!!editProject} onOpenChange={(v) => { if (!v) { setEditProject(null); clearErrors(); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar proyecto</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => void handleEdit(e)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="edit-proj-name">Nombre *</Label>
              <Input
                id="edit-proj-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
                aria-invalid={!!fieldErrors['name']}
              />
              {fieldErrors['name'] && (
                <p role="alert" className="text-body-sm text-destructive">
                  {fieldErrors['name']}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-proj-desc">Descripción</Label>
              <Textarea
                id="edit-proj-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={3}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditProject(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={!form.name.trim() || saving}>
                {saving ? 'Guardando...' : 'Guardar'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(v) => { if (!v) setDeleteTarget(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar proyecto</DialogTitle>
            <DialogDescription>
              ¿Seguro que quieres eliminar &ldquo;{deleteTarget?.name}&rdquo;? Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={deleting}
              onClick={() => void handleDelete()}
            >
              {deleting ? 'Eliminando...' : 'Eliminar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Integrations Tab ─────────────────────────────────────────────────────────

interface IntegrationFormState {
  project_id: string;
  base_url: string;
  email: string;
  api_token: string;
  mapping_json: string;
  show_mapping: boolean;
}

const EMPTY_INTEGRATION_FORM: IntegrationFormState = {
  project_id: '',
  base_url: '',
  email: '',
  api_token: '',
  mapping_json: '',
  show_mapping: false,
};

function IntegrationsTab() {
  const { configs, isLoading, error, createIntegration, deleteIntegration } = useIntegrations();
  const { projects } = useProjects();

  const [open, setOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<IntegrationConfig | null>(null);
  const [form, setForm] = useState<IntegrationFormState>(EMPTY_INTEGRATION_FORM);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.base_url.trim()) return;
    setSaving(true);
    setFormError(null);
    try {
      const creds = {
        base_url: form.base_url.trim(),
        email: form.email.trim(),
        api_token: form.api_token,
      };
      const req: IntegrationConfigCreateRequest = {
        integration_type: 'jira',
        encrypted_credentials: JSON.stringify(creds),
        ...(form.project_id ? { project_id: form.project_id } : {}),
        ...(form.mapping_json.trim()
          ? { mapping: JSON.parse(form.mapping_json) as Record<string, unknown> }
          : {}),
      };
      await createIntegration(req);
      setOpen(false);
      setForm(EMPTY_INTEGRATION_FORM);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteIntegration(deleteTarget.id);
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  }

  if (isLoading) return <TabSkeleton testId="integrations-skeleton" />;
  if (error) {
    if (isSessionExpired(error)) return null;
    return <TabError testId="integrations-error" message={`No se pudieron cargar las integraciones: ${error.message}`} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => { setOpen(true); setFormError(null); }}>
          <Plus className="mr-1.5 h-4 w-4" />
          Nueva integración
        </Button>
      </div>

      {configs.length === 0 ? (
        <TabEmpty
          testId="integrations-empty"
          message="No hay integraciones configuradas. Crea una para exportar items a Jira u otros sistemas."
        />
      ) : (
        <div className="space-y-3">
          {configs.map((c) => {
            const project = projects.find((p) => p.id === c.project_id);
            return (
              <Card key={c.id}>
                <CardContent className="flex items-center gap-3 p-4">
                  <div className="flex-1">
                    <p className="font-medium capitalize">{c.integration_type}</p>
                    <p className="text-body-sm text-muted-foreground">
                      {project ? project.name : 'Todos los proyectos'}
                    </p>
                    <p
                      data-testid={`integration-credentials-masked-${c.id}`}
                      className="mt-1 font-mono text-xs text-muted-foreground"
                    >
                      ••••••••
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="text-right">
                      <Badge variant={c.is_active ? 'default' : 'secondary'}>
                        {c.is_active ? 'Activa' : 'Inactiva'}
                      </Badge>
                      <p className="mt-1 text-xs text-muted-foreground">
                        <RelativeTime iso={c.created_at} />
                      </p>
                    </div>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      aria-label={`Eliminar integración ${c.integration_type}`}
                      onClick={() => setDeleteTarget(c)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) setFormError(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nueva integración</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => void handleCreate(e)} className="space-y-4">
            {formError && (
              <div className="rounded-md bg-destructive/10 px-4 py-2 text-body-sm text-destructive">
                {formError}
              </div>
            )}

            <div className="space-y-1.5">
              <Label>Proveedor</Label>
              <p className="rounded-md border bg-muted px-3 py-2 text-body-sm">Jira</p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="int-project">Proyecto (opcional)</Label>
              <Select
                value={form.project_id}
                onValueChange={(v) =>
                  setForm((f) => ({ ...f, project_id: v === '__none__' ? '' : v }))
                }
              >
                <SelectTrigger id="int-project">
                  <SelectValue placeholder="Todos los proyectos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Todos los proyectos</SelectItem>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="int-base-url">URL base de Jira *</Label>
              <Input
                id="int-base-url"
                placeholder="https://yourcompany.atlassian.net"
                value={form.base_url}
                onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="int-email">Email</Label>
              <Input
                id="int-email"
                type="email"
                placeholder="you@company.com"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="int-api-token">API Token</Label>
              <Input
                id="int-api-token"
                type="password"
                placeholder="Token de Jira"
                value={form.api_token}
                onChange={(e) => setForm((f) => ({ ...f, api_token: e.target.value }))}
              />
            </div>

            <div className="space-y-1.5">
              <p className="text-body-sm text-muted-foreground">
                Pega las credenciales cifradas como JSON en el campo de configuración avanzada.
              </p>
              <button
                type="button"
                className="text-body-sm text-muted-foreground underline underline-offset-2"
                onClick={() => setForm((f) => ({ ...f, show_mapping: !f.show_mapping }))}
              >
                {form.show_mapping ? 'Ocultar mapping avanzado' : 'Mostrar mapping avanzado'}
              </button>
              {form.show_mapping && (
                <Textarea
                  id="int-mapping"
                  placeholder='{"jira_project_key": "ABC"}'
                  value={form.mapping_json}
                  onChange={(e) => setForm((f) => ({ ...f, mapping_json: e.target.value }))}
                  rows={4}
                  className="font-mono text-xs"
                />
              )}
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={!form.base_url.trim() || saving}>
                {saving ? 'Creando...' : 'Crear'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(v) => { if (!v) setDeleteTarget(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar integración</DialogTitle>
            <DialogDescription>
              ¿Seguro que quieres eliminar la integración &ldquo;{deleteTarget?.integration_type}&rdquo;? Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={deleting}
              onClick={() => void handleDelete()}
            >
              {deleting ? 'Eliminando...' : 'Eliminar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Tags Tab ─────────────────────────────────────────────────────────────────

function TagsTab() {
  const { tags, isLoading, error, createTag, archiveTag, replaceTag } = useTags();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<TagCreateRequest>({ name: '' });
  const [saving, setSaving] = useState(false);
  const { fieldErrors, handleApiError, clearErrors } = useFormErrors();
  const [editTag, setEditTag] = useState<Tag | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    clearErrors();
    try {
      await createTag({ name: form.name.trim(), color: form.color });
      setOpen(false);
      setForm({ name: '' });
    } catch (err) {
      handleApiError(err);
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) return <TabSkeleton testId="tags-skeleton" />;
  if (error) {
    if (isSessionExpired(error)) return null;
    return <TabError testId="tags-error" message={`No se pudieron cargar las etiquetas: ${error.message}`} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          Nueva etiqueta
        </Button>
      </div>

      {tags.length === 0 ? (
        <TabEmpty testId="tags-empty" message="No hay etiquetas." />
      ) : (
        <div className="flex flex-wrap gap-2">
          {tags.map((t) => (
            <div
              key={t.id}
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1 ${
                t.archived ? 'opacity-50' : ''
              }`}
              style={t.color ? { borderColor: t.color, color: t.color } : undefined}
            >
              <span className="text-body-sm font-medium">{t.name}</span>
              <button
                type="button"
                aria-label={`Editar etiqueta ${t.name}`}
                onClick={() => setEditTag(t)}
                className="ml-0.5 text-muted-foreground hover:text-foreground"
              >
                <Pencil className="h-3 w-3" />
              </button>
              {!t.archived && (
                <button
                  type="button"
                  title="Archivar"
                  onClick={() => void archiveTag(t.id)}
                  className="ml-0.5 text-muted-foreground hover:text-foreground"
                >
                  <Archive className="h-3 w-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nueva etiqueta</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => void handleCreate(e)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="tag-name">Nombre *</Label>
              <Input
                id="tag-name"
                placeholder="Nombre de la etiqueta"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
                aria-invalid={!!fieldErrors['name']}
                aria-describedby={fieldErrors['name'] ? 'tag-name-error' : undefined}
              />
              {fieldErrors['name'] && (
                <p id="tag-name-error" className="text-body-sm text-destructive" role="alert">
                  {fieldErrors['name']}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tag-color">Color (hex)</Label>
              <Input
                id="tag-color"
                placeholder="#3b82f6"
                value={form.color ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, color: e.target.value || undefined }))}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={!form.name.trim() || saving}>
                {saving ? 'Creando...' : 'Crear'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {editTag && (
        <TagEditModal
          open={true}
          tag={editTag}
          onClose={() => setEditTag(null)}
          onSaved={(updated) => {
            replaceTag(updated);
            setEditTag(null);
          }}
        />
      )}
    </div>
  );
}

// ─── Puppet Tab ───────────────────────────────────────────────────────────────

function PuppetTab({ slug }: { slug: string }) {
  const { config, createConfig: _cc, updateConfig: _uc, runHealthCheck: _rhc } = usePuppetConfig();
  const { sources, isLoading: sourcesLoading, addSource, removeSource } = useDocSources();
  const [addSourceOpen, setAddSourceOpen] = useState(false);
  const [currentConfig, setCurrentConfig] = useState<PuppetConfig | null>(config);

  // Sync config from hook on initial load
  if (config !== null && currentConfig === null) {
    setCurrentConfig(config);
  }

  const workspaceId = slug;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="mb-4 text-sm font-semibold text-foreground">Configuración de Puppet</h2>
        <PuppetConfigForm
          existingConfig={currentConfig}
          workspaceId={workspaceId}
          onSaved={(saved) => setCurrentConfig(saved)}
        />
      </div>

      <div>
        <h2 className="mb-4 text-sm font-semibold text-foreground">Fuentes de documentación</h2>
        <DocSourcesTable
          sources={sources}
          isLoading={sourcesLoading}
          onAddSource={() => setAddSourceOpen(true)}
          onDeleteSource={async (id) => { await removeSource(id); }}
        />
        <AddDocSourceModal
          open={addSourceOpen}
          workspaceId={workspaceId}
          onClose={() => setAddSourceOpen(false)}
          onSubmit={async (req) => {
            await addSource(req);
            setAddSourceOpen(false);
          }}
        />
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function AdminPage({ params: { slug: _slug } }: AdminPageProps) {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <PageContainer variant="wide">
      <h1 className="mb-6 text-h2 font-semibold">Administración</h1>

      <Tabs defaultValue="members">
        <TabsList className="mb-6 flex-wrap">
          <TabsTrigger value="members">Members</TabsTrigger>
          <TabsTrigger value="audit">Audit</TabsTrigger>
          <TabsTrigger value="health">Health</TabsTrigger>
          <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="projects">Projects</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="jira">Jira</TabsTrigger>
          <TabsTrigger value="tags">Tags</TabsTrigger>
          <TabsTrigger value="puppet">Puppet</TabsTrigger>
          <TabsTrigger value="rules">Rules</TabsTrigger>
          <TabsTrigger value="contextPresets">Context Presets</TabsTrigger>
          <TabsTrigger value="support">Support</TabsTrigger>
        </TabsList>

        <TabsContent value="members">
          <MembersTabEnhanced />
        </TabsContent>
        <TabsContent value="audit">
          <AuditTab />
        </TabsContent>
        <TabsContent value="health">
          <HealthTab />
        </TabsContent>
        <TabsContent value="dashboard">
          <AdminDashboardTab />
        </TabsContent>
        <TabsContent value="projects">
          <ProjectsTab />
        </TabsContent>
        <TabsContent value="integrations">
          <IntegrationsTab />
        </TabsContent>
        <TabsContent value="jira">
          <JiraConfigTab />
        </TabsContent>
        <TabsContent value="tags">
          <TagsTab />
        </TabsContent>
        <TabsContent value="puppet">
          <PuppetTab slug={_slug} />
        </TabsContent>
        <TabsContent value="rules">
          <ValidationRulesTab />
        </TabsContent>
        <TabsContent value="contextPresets">
          <ContextPresetsTab />
        </TabsContent>
        <TabsContent value="support">
          <SupportTab />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
