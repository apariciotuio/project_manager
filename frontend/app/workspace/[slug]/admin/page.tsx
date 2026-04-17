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
import { CheckCircle2, AlertTriangle, XCircle, Plus, Archive } from 'lucide-react';
import type { HealthStatus, ProjectCreateRequest, TagCreateRequest } from '@/lib/types/api';

interface AdminPageProps {
  params: { slug: string };
}

function StatusIcon({ status }: { status: HealthStatus }) {
  if (status === 'ok') return <CheckCircle2 className="h-4 w-4 text-green-500" />;
  if (status === 'degraded') return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
  return <XCircle className="h-4 w-4 text-destructive" />;
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
  if (error) return <p className="text-body-sm text-destructive">Error al cargar auditoría.</p>;

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
                <td className="py-2 pr-4">{e.actor_name ?? '—'}</td>
                <td className="py-2 pr-4 font-mono text-xs">{e.action}</td>
                <td className="py-2 pr-4 text-muted-foreground">
                  {e.resource_type}
                  {e.resource_id ? ` / ${e.resource_id}` : ''}
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

// ─── Health Tab ───────────────────────────────────────────────────────────────

function HealthTab() {
  const { health, isLoading, error } = useHealth();

  if (isLoading) return <p className="text-body-sm text-muted-foreground">Cargando...</p>;
  if (error) return <p className="text-body-sm text-destructive">Error al cargar salud.</p>;
  if (!health) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <StatusIcon status={health.status} />
        <span className="font-medium">Estado general: {health.status}</span>
        {health.version && (
          <span className="ml-auto text-body-sm text-muted-foreground">v{health.version}</span>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {health.checks.map((c) => (
          <Card key={c.name}>
            <CardContent className="flex items-center gap-3 p-4">
              <StatusIcon status={c.status} />
              <div>
                <p className="font-medium">{c.name}</p>
                {c.latency_ms !== null && (
                  <p className="text-body-sm text-muted-foreground">{c.latency_ms}ms</p>
                )}
                {c.message && (
                  <p className="text-body-sm text-muted-foreground">{c.message}</p>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
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
  if (error) return <p className="text-body-sm text-destructive">Error al cargar proyectos.</p>;

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

function IntegrationsTab() {
  const { configs, isLoading, error } = useIntegrations();

  if (isLoading) return <p className="text-body-sm text-muted-foreground">Cargando...</p>;
  if (error) return <p className="text-body-sm text-destructive">Error al cargar integraciones.</p>;

  return (
    <div className="space-y-3">
      {configs.length === 0 ? (
        <p className="py-8 text-center text-muted-foreground">No hay integraciones configuradas.</p>
      ) : (
        configs.map((c) => (
          <Card key={c.id}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="flex-1">
                <p className="font-medium">{c.provider}</p>
                <p className="text-body-sm text-muted-foreground">
                  {c.enabled ? 'Activa' : 'Inactiva'}
                </p>
              </div>
              <Badge variant={c.enabled ? 'default' : 'secondary'}>
                {c.enabled ? 'Activa' : 'Inactiva'}
              </Badge>
            </CardContent>
          </Card>
        ))
      )}
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
  if (error) return <p className="text-body-sm text-destructive">Error al cargar etiquetas.</p>;

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
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-h3 font-semibold">Administración</h1>

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
    </div>
  );
}
