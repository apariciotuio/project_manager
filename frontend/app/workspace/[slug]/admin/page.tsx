'use client';

import { useState } from 'react';
import { useAuth } from '@/app/providers/auth-provider';
import { useAuditEvents, useHealth, useProjects, useIntegrations, useTags } from '@/hooks/use-admin';
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
import { Plus, Archive } from 'lucide-react';
import type { ProjectCreateRequest, TagCreateRequest, IntegrationConfigCreateRequest } from '@/lib/types/api';
import { isSessionExpired } from '@/lib/types/auth';
import { PageContainer } from '@/components/layout/page-container';

interface AdminPageProps {
  params: { slug: string };
}

// ─── Members Tab ──────────────────────────────────────────────────────────────

function MembersTab() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="space-y-4">
      <p className="text-body-sm text-muted-foreground">
        Vista de miembros del workspace (stub — mostrando usuario actual).
      </p>
      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <div>
            <p className="font-medium">{user.full_name}</p>
            <p className="text-body-sm text-muted-foreground">{user.email}</p>
          </div>
          {user.is_superadmin && (
            <Badge variant="secondary" className="ml-auto">
              Superadmin
            </Badge>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Audit Tab ────────────────────────────────────────────────────────────────

function AuditTab() {
  const { events, total, isLoading, error } = useAuditEvents();

  if (isLoading) return <p className="text-body-sm text-muted-foreground">Cargando...</p>;
  if (error) return isSessionExpired(error) ? null : <p className="text-body-sm text-destructive">No se pudo cargar la auditoría: {error.message}</p>;

  return (
    <div className="space-y-3">
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
          <p className="py-8 text-center text-muted-foreground">No hay eventos de auditoría.</p>
        )}
      </div>
    </div>
  );
}

// ─── Health Tab (workspace work item state summary) ──────────────────────────

function HealthTab() {
  const { health, isLoading, error } = useHealth();

  if (isLoading) return <p className="text-body-sm text-muted-foreground">Cargando...</p>;
  if (error) return isSessionExpired(error) ? null : <p className="text-body-sm text-destructive">No se pudo cargar el resumen: {error.message}</p>;
  if (!health) return null;

  const states = Object.entries(health.work_items_by_state);

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <p className="text-body-sm text-muted-foreground">
          Distribución de elementos de trabajo por estado.
        </p>
        <p className="text-body-sm">
          <span className="font-semibold text-foreground">{health.total_active}</span>{' '}
          <span className="text-muted-foreground">activos</span>
        </p>
      </div>
      {states.length === 0 ? (
        <p className="py-8 text-center text-muted-foreground">Aún no hay elementos de trabajo.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {states.map(([state, count]) => (
            <Card key={state}>
              <CardContent className="flex items-center justify-between p-4">
                <p className="font-medium capitalize">{state.replace(/_/g, ' ')}</p>
                <p className="text-h3 font-semibold">{count}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Projects Tab ─────────────────────────────────────────────────────────────

function ProjectsTab() {
  const { projects, isLoading, error, createProject } = useProjects();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ProjectCreateRequest>({ name: '' });
  const [saving, setSaving] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await createProject({ name: form.name.trim(), description: form.description });
      setOpen(false);
      setForm({ name: '' });
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) return <p className="text-body-sm text-muted-foreground">Cargando...</p>;
  if (error) return isSessionExpired(error) ? null : <p className="text-body-sm text-destructive">No se pudieron cargar los proyectos: {error.message}</p>;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          Nuevo proyecto
        </Button>
      </div>

      {projects.length === 0 ? (
        <p className="py-8 text-center text-muted-foreground">No hay proyectos.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {projects.map((p) => (
            <Card key={p.id}>
              <CardHeader className="pb-2">
                <CardTitle className="text-body">{p.name}</CardTitle>
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

      <Dialog open={open} onOpenChange={setOpen}>
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
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="proj-desc">Descripción</Label>
              <Textarea
                id="proj-desc"
                placeholder="Descripción opcional"
                value={form.description ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={3}
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
    </div>
  );
}

// ─── Integrations Tab ─────────────────────────────────────────────────────────

interface JiraCredentials {
  base_url: string;
  email: string;
  api_token: string;
}

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
  const { configs, isLoading, error, createIntegration } = useIntegrations();
  const { projects } = useProjects();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<IntegrationFormState>(EMPTY_INTEGRATION_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.base_url.trim()) return;
    setSaving(true);
    setFormError(null);
    try {
      const creds: JiraCredentials = {
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
      setSuccessToast(true);
      setTimeout(() => setSuccessToast(false), 3000);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) return <p className="text-body-sm text-muted-foreground">Cargando...</p>;
  if (error) return isSessionExpired(error) ? null : <p className="text-body-sm text-destructive">No se pudieron cargar las integraciones: {error.message}</p>;

  return (
    <div className="space-y-4">
      {successToast && (
        <div className="rounded-md bg-green-50 px-4 py-2 text-body-sm text-green-800 dark:bg-green-900/20 dark:text-green-300">
          Integración creada
        </div>
      )}

      <div className="flex justify-end">
        <Button size="sm" onClick={() => { setOpen(true); setFormError(null); }}>
          <Plus className="mr-1.5 h-4 w-4" />
          Nueva integración
        </Button>
      </div>

      {configs.length === 0 ? (
        <p className="py-8 text-center text-muted-foreground">
          No hay integraciones configuradas. Crea una para exportar items a Jira u otros sistemas.
        </p>
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
                  </div>
                  <div className="text-right">
                    <Badge variant={c.is_active ? 'default' : 'secondary'}>
                      {c.is_active ? 'Activa' : 'Inactiva'}
                    </Badge>
                    <p className="mt-1 text-xs text-muted-foreground">
                      <RelativeTime iso={c.created_at} />
                    </p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

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
                onValueChange={(v) => setForm((f) => ({ ...f, project_id: v === '__none__' ? '' : v }))}
              >
                <SelectTrigger id="int-project">
                  <SelectValue placeholder="Todos los proyectos / sin proyecto específico" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Todos los proyectos / sin proyecto específico</SelectItem>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
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
    </div>
  );
}

// ─── Tags Tab ─────────────────────────────────────────────────────────────────

function TagsTab() {
  const { tags, isLoading, error, createTag, archiveTag } = useTags();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<TagCreateRequest>({ name: '' });
  const [saving, setSaving] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await createTag({ name: form.name.trim(), color: form.color });
      setOpen(false);
      setForm({ name: '' });
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) return <p className="text-body-sm text-muted-foreground">Cargando...</p>;
  if (error) return isSessionExpired(error) ? null : <p className="text-body-sm text-destructive">No se pudieron cargar las etiquetas: {error.message}</p>;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          Nueva etiqueta
        </Button>
      </div>

      {tags.length === 0 ? (
        <p className="py-8 text-center text-muted-foreground">No hay etiquetas.</p>
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
              />
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
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function AdminPage({ params: { slug: _slug } }: AdminPageProps) {
  return (
    <PageContainer variant="wide">
      <h1 className="mb-6 text-h2 font-semibold">Administración</h1>

      <Tabs defaultValue="members">
        <TabsList className="mb-6 flex-wrap">
          <TabsTrigger value="members">Miembros</TabsTrigger>
          <TabsTrigger value="audit">Auditoría</TabsTrigger>
          <TabsTrigger value="health">Salud</TabsTrigger>
          <TabsTrigger value="projects">Proyectos</TabsTrigger>
          <TabsTrigger value="integrations">Integraciones</TabsTrigger>
          <TabsTrigger value="tags">Etiquetas</TabsTrigger>
        </TabsList>

        <TabsContent value="members">
          <MembersTab />
        </TabsContent>
        <TabsContent value="audit">
          <AuditTab />
        </TabsContent>
        <TabsContent value="health">
          <HealthTab />
        </TabsContent>
        <TabsContent value="projects">
          <ProjectsTab />
        </TabsContent>
        <TabsContent value="integrations">
          <IntegrationsTab />
        </TabsContent>
        <TabsContent value="tags">
          <TagsTab />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
