'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useTemplates } from '@/hooks/use-templates';
import { useProjects } from '@/hooks/use-admin';
import { useTags } from '@/hooks/use-admin';
import { usePreCreationDraft } from '@/hooks/use-pre-creation-draft';
import { createWorkItem, listWorkItems } from '@/lib/api/work-items';
import { useAuth } from '@/app/providers/auth-provider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import type { WorkItemType, WorkItemResponse } from '@/lib/types/work-item';
import type { Template } from '@/lib/types/api';
import type { DraftData } from '@/hooks/use-pre-creation-draft';
import { PageContainer } from '@/components/layout/page-container';
import { DraftResumeBanner } from '@/components/capture/draft-resume-banner';
import { StalenessWarning } from '@/components/capture/staleness-warning';

// ─── Constants ────────────────────────────────────────────────────────────────

const WORK_ITEM_TYPES: { value: WorkItemType; label: string }[] = [
  { value: 'idea', label: 'Idea' },
  { value: 'bug', label: 'Bug' },
  { value: 'enhancement', label: 'Mejora' },
  { value: 'task', label: 'Tarea' },
  { value: 'initiative', label: 'Iniciativa' },
  { value: 'spike', label: 'Spike' },
  { value: 'business_change', label: 'Cambio de negocio' },
  { value: 'requirement', label: 'Requisito' },
  { value: 'milestone', label: 'Hito' },
  { value: 'story', label: 'Historia' },
];

// Types that can have a parent (initiative or milestone)
const CHILD_TYPES: WorkItemType[] = [
  'story',
  'task',
  'bug',
  'spike',
  'enhancement',
  'requirement',
  'business_change',
];

interface NewItemPageProps {
  params: { slug: string };
}

export default function NewItemPage({ params: { slug } }: NewItemPageProps) {
  const router = useRouter();
  const t = useTranslations('workspace.newItem');
  const { user } = useAuth();
  const { templates, isLoading: templatesLoading } = useTemplates();
  const { projects, isLoading: projectsLoading, createProject } = useProjects();
  const { tags, isLoading: tagsLoading } = useTags();

  // ─── Form state ─────────────────────────────────────────────────────────────
  const [title, setTitle] = useState('');
  const [type, setType] = useState<WorkItemType>('task');
  const [description, setDescription] = useState('');
  const [projectId, setProjectId] = useState<string>('');
  const [parentId, setParentId] = useState<string>('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localVersion, setLocalVersion] = useState(0);

  // ─── Parent candidates ───────────────────────────────────────────────────────
  const [parentCandidates, setParentCandidates] = useState<WorkItemResponse[]>([]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [initiatives, milestones] = await Promise.all([
          listWorkItems(null, { type: 'initiative' }),
          listWorkItems(null, { type: 'milestone' }),
        ]);
        if (!cancelled) {
          setParentCandidates([...initiatives.items, ...milestones.items]);
        }
      } catch {
        // Non-blocking
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // ─── Draft hydration ─────────────────────────────────────────────────────────
  const handleHydrate = useCallback((data: DraftData) => {
    if (data.title) setTitle(data.title);
    if (data.type) setType(data.type);
    if (data.description) setDescription(data.description);
    if (data.project_id) setProjectId(data.project_id);
    if (data.parent_work_item_id) setParentId(data.parent_work_item_id);
    if (data.tags) setSelectedTags(data.tags);
  }, []);

  const workspaceId = user?.workspace_id ?? '';
  const {
    draftId,
    conflictError,
    pendingServerDraft,
    save,
    discard,
    resolveConflict,
    keepMine,
    applyPendingDraft,
    discardPendingDraft,
  } = usePreCreationDraft(workspaceId, handleHydrate);

  // ─── Auto-save on form changes ───────────────────────────────────────────────
  useEffect(() => {
    if (!workspaceId) return;
    const nextVersion = localVersion + 1;
    setLocalVersion(nextVersion);
    save(
      { title, type, description, project_id: projectId || undefined, parent_work_item_id: parentId || undefined, tags: selectedTags },
      nextVersion,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, type, description, projectId, parentId, selectedTags]);

  // ─── New project dialog ───────────────────────────────────────────────────────
  const [projectDialogOpen, setProjectDialogOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [isCreatingProject, setIsCreatingProject] = useState(false);

  async function handleCreateProject() {
    if (!newProjectName.trim()) return;
    setIsCreatingProject(true);
    try {
      const project = await createProject({
        name: newProjectName.trim(),
        description: newProjectDesc.trim() || undefined,
      });
      setProjectId(project.id);
      setProjectDialogOpen(false);
      setNewProjectName('');
      setNewProjectDesc('');
    } catch (err) {
      // error surfaced inline — keep dialog open
      console.error(err);
    } finally {
      setIsCreatingProject(false);
    }
  }

  // ─── Template ────────────────────────────────────────────────────────────────
  function applyTemplate(template: Template) {
    setSelectedTemplate(template);
    if (template.type) setType(template.type as WorkItemType);
  }

  // ─── Tag toggle ──────────────────────────────────────────────────────────────
  function toggleTag(name: string) {
    setSelectedTags((prev) =>
      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name],
    );
  }

  // ─── Submit ──────────────────────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !user || !projectId) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const item = await createWorkItem({
        title: title.trim(),
        type,
        description: description.trim() || undefined,
        project_id: projectId,
        parent_work_item_id: parentId || undefined,
        tags: selectedTags.length > 0 ? selectedTags : undefined,
        template_id: selectedTemplate?.id,
      });
      await discard();
      router.push(`/workspace/${slug}/items/${item.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear el elemento');
    } finally {
      setIsSubmitting(false);
    }
  }

  const showParentPicker = CHILD_TYPES.includes(type);

  return (
    <PageContainer variant="narrow" className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-h2 font-semibold text-foreground">Nuevo elemento</h1>
        <p className="text-body-sm text-muted-foreground">
          Crea un elemento de trabajo. Podrás editar los detalles tras crearlo.
        </p>
      </header>

      {/* Draft resume banner — shown before the form when a server draft exists */}
      <DraftResumeBanner
        pendingDraft={pendingServerDraft}
        onResume={applyPendingDraft}
        onDiscard={() => void discardPendingDraft()}
      />

      {/* Conflict banner */}
      {conflictError && (
        <StalenessWarning
          lastServerUpdate={conflictError.server_data.updated_at ?? new Date().toISOString()}
          onOverwrite={() =>
            resolveConflict({
              title,
              type,
              description,
              project_id: projectId || undefined,
              parent_work_item_id: parentId || undefined,
              tags: selectedTags,
            })
          }
          onKeepMine={() =>
            keepMine({
              title,
              type,
              description,
              project_id: projectId || undefined,
              parent_work_item_id: parentId || undefined,
              tags: selectedTags,
            })
          }
        />
      )}

      {/* Template picker */}
      {!templatesLoading && templates.length > 0 && (
        <div className="flex flex-col gap-3">
          <Label className="text-body-sm font-medium">Plantilla</Label>
          <div className="flex flex-wrap gap-2">
            {templates.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => applyTemplate(t)}
                className={`rounded-md border px-3 py-1.5 text-body-sm transition-colors ${
                  selectedTemplate?.id === t.id
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border bg-card text-foreground hover:bg-accent'
                }`}
              >
                {t.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-6">

            {/* Title */}
            <div className="flex flex-col gap-2">
              <Label htmlFor="title">Título *</Label>
              <Input
                id="title"
                placeholder={t('fields.titlePlaceholder')}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                autoFocus
                className="h-11 text-body"
              />
            </div>

            {/* Type */}
            <div className="flex flex-col gap-2">
              <Label htmlFor="type">Tipo</Label>
              <Select value={type} onValueChange={(v) => setType(v as WorkItemType)}>
                <SelectTrigger id="type" className="h-11">
                  <SelectValue placeholder={t('fields.typePlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {WORK_ITEM_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Project picker */}
            <div className="flex flex-col gap-2">
              <Label htmlFor="project">Proyecto *</Label>
              {!projectsLoading && projects.length === 0 ? (
                <div className="flex items-center gap-3">
                  <span className="text-body-sm text-muted-foreground">Sin proyectos.</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setProjectDialogOpen(true)}
                  >
                    Crear proyecto
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Select value={projectId} onValueChange={setProjectId}>
                    <SelectTrigger id="project" className="h-11 flex-1">
                      <SelectValue placeholder="Selecciona un proyecto" />
                    </SelectTrigger>
                    <SelectContent>
                      {projects.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setProjectDialogOpen(true)}
                  >
                    Nuevo
                  </Button>
                </div>
              )}
            </div>

            {/* Parent picker (only for child types) */}
            {showParentPicker && (
              <div className="flex flex-col gap-2">
                <Label htmlFor="parent">Padre</Label>
                <Select
                  value={parentId || '__none__'}
                  onValueChange={(v) => setParentId(v === '__none__' ? '' : v)}
                >
                  <SelectTrigger id="parent" className="h-11">
                    <SelectValue placeholder="Sin padre" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">Sin padre</SelectItem>
                    {parentCandidates.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        [{item.type}] {item.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Tag picker */}
            {!tagsLoading && tags.filter((t) => !t.archived).length > 0 && (
              <div className="flex flex-col gap-2">
                <Label>Etiquetas</Label>
                <div className="flex flex-wrap gap-2">
                  {tags
                    .filter((t) => !t.archived)
                    .map((tag) => {
                      const selected = selectedTags.includes(tag.name);
                      return (
                        <button
                          key={tag.id}
                          type="button"
                          onClick={() => toggleTag(tag.name)}
                          aria-pressed={selected}
                          className={`rounded-full border px-3 py-1 text-body-sm font-medium transition-colors ${
                            selected
                              ? 'border-transparent text-white'
                              : 'border-border bg-transparent text-foreground hover:bg-accent'
                          }`}
                          style={
                            selected && tag.color
                              ? { backgroundColor: tag.color, borderColor: tag.color }
                              : selected
                                ? { backgroundColor: 'hsl(var(--primary))', borderColor: 'hsl(var(--primary))' }
                                : undefined
                          }
                        >
                          {tag.name}
                        </button>
                      );
                    })}
                </div>
              </div>
            )}

            {/* Description */}
            <div className="flex flex-col gap-2">
              <Label htmlFor="description">Descripción</Label>
              <Textarea
                id="description"
                placeholder={t('fields.descriptionPlaceholder')}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={8}
                className="min-h-[180px] resize-y"
              />
            </div>

            {error && (
              <p className="text-body-sm text-destructive">{error}</p>
            )}

            <div className="flex justify-end gap-2 border-t border-border pt-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={!title.trim() || !projectId || isSubmitting}
              >
                {isSubmitting ? 'Creando...' : 'Crear'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Create project dialog */}
      <Dialog open={projectDialogOpen} onOpenChange={setProjectDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Crear proyecto</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="new-project-name">Nombre *</Label>
              <Input
                id="new-project-name"
                placeholder="Nombre del proyecto"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="new-project-desc">Descripción</Label>
              <Textarea
                id="new-project-desc"
                placeholder={t('fields.descriptionPlaceholder')}
                value={newProjectDesc}
                onChange={(e) => setNewProjectDesc(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setProjectDialogOpen(false)}
            >
              Cancelar
            </Button>
            <Button
              type="button"
              disabled={!newProjectName.trim() || isCreatingProject}
              onClick={() => void handleCreateProject()}
            >
              {isCreatingProject ? 'Creando...' : 'Crear'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
