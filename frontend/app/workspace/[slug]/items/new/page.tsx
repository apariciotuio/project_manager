'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useTemplates } from '@/hooks/use-templates';
import { apiPost, apiPatch } from '@/lib/api-client';
import { useAuth } from '@/app/providers/auth-provider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { WorkItemType } from '@/lib/types/work-item';
import type { DraftResponse, Template } from '@/lib/types/api';

interface WorkItemCreateResponse {
  data: { id: string };
}

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

const AUTO_SAVE_DELAY = 5000;

interface NewItemPageProps {
  params: { slug: string };
}

export default function NewItemPage({ params: { slug } }: NewItemPageProps) {
  const router = useRouter();
  const { user } = useAuth();
  const { templates, isLoading: templatesLoading } = useTemplates();

  const [title, setTitle] = useState('');
  const [type, setType] = useState<WorkItemType>('task');
  const [description, setDescription] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Create draft on mount
  useEffect(() => {
    void (async () => {
      try {
        const res = await apiPost<DraftResponse>('/api/v1/drafts', {});
        setDraftId(res.data.id);
      } catch {
        // Non-fatal: auto-save will be skipped if draft creation fails
      }
    })();
  }, []);

  const saveDraft = useCallback(
    (currentTitle: string, currentType: string, currentDesc: string) => {
      if (!draftId) return;
      void apiPatch(`/api/v1/drafts/${draftId}`, {
        title: currentTitle,
        type: currentType,
        description: currentDesc,
      }).catch(() => {
        // Silently ignore auto-save failures
      });
    },
    [draftId]
  );

  // Auto-save every 5 seconds when content changes
  useEffect(() => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(() => {
      saveDraft(title, type, description);
    }, AUTO_SAVE_DELAY);

    return () => {
      if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    };
  }, [title, type, description, saveDraft]);

  function applyTemplate(template: Template) {
    setSelectedTemplate(template);
    if (template.type) setType(template.type as WorkItemType);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !user) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const res = await apiPost<WorkItemCreateResponse>('/api/v1/work-items', {
        title: title.trim(),
        type,
        description: description.trim() || undefined,
        project_id: '',
      });
      router.push(`/workspace/${slug}/items/${res.data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear el elemento');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-6 text-h3 font-semibold">Nuevo elemento</h1>

      {/* Template picker */}
      {!templatesLoading && templates.length > 0 && (
        <div className="mb-6">
          <Label className="mb-2 block text-body-sm font-medium">Plantilla</Label>
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
        <CardHeader>
          <CardTitle>Detalles</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="title">Título *</Label>
              <Input
                id="title"
                placeholder="Título del elemento"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="type">Tipo</Label>
              <Select value={type} onValueChange={(v) => setType(v as WorkItemType)}>
                <SelectTrigger id="type">
                  <SelectValue placeholder="Selecciona un tipo" />
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

            <div className="space-y-1.5">
              <Label htmlFor="description">Descripción</Label>
              <Textarea
                id="description"
                placeholder="Descripción opcional"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
              />
            </div>

            {error && (
              <p className="text-body-sm text-destructive">{error}</p>
            )}

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={!title.trim() || isSubmitting}
              >
                {isSubmitting ? 'Creando...' : 'Crear'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
