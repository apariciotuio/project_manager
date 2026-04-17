'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { apiPatch } from '@/lib/api-client';
import { useFormErrors } from '@/lib/errors/use-form-errors';
import type { WorkItemResponse, WorkItemType, Priority } from '@/lib/types/work-item';

// ─── Label helpers ────────────────────────────────────────────────────────────

const PRIORITY_LABELS: Record<Priority, string> = {
  low: 'Baja',
  medium: 'Media',
  high: 'Alta',
  critical: 'Crítica',
};

const TYPE_LABELS: Record<WorkItemType, string> = {
  idea: 'Idea',
  bug: 'Error',
  enhancement: 'Mejora',
  task: 'Tarea',
  initiative: 'Iniciativa',
  spike: 'Spike',
  business_change: 'Cambio de negocio',
  requirement: 'Requisito',
  milestone: 'Hito',
  story: 'Historia',
};

// ─── Types ────────────────────────────────────────────────────────────────────

interface WorkItemUpdatePayload {
  title?: string;
  description?: string;
  priority?: Priority | null;
  type?: WorkItemType;
}

export interface WorkItemEditModalProps {
  open: boolean;
  workItem: WorkItemResponse;
  onClose: () => void;
  onSaved: (updated: WorkItemResponse) => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function WorkItemEditModal({ open, workItem, onClose, onSaved }: WorkItemEditModalProps) {
  const [title, setTitle] = useState(workItem.title);
  const [description, setDescription] = useState(workItem.description ?? '');
  const [priority, setPriority] = useState<Priority | null>(workItem.priority);
  const [type, setType] = useState<WorkItemType>(workItem.type);
  const [saving, setSaving] = useState(false);

  const { fieldErrors, handleApiError, clearErrors } = useFormErrors();

  // Reset form when workItem changes (e.g. after re-open)
  useEffect(() => {
    if (open) {
      setTitle(workItem.title);
      setDescription(workItem.description ?? '');
      setPriority(workItem.priority);
      setType(workItem.type);
      clearErrors();
    }
  }, [open, workItem, clearErrors]);

  // Compute diff — only send changed fields
  function buildPatch(): WorkItemUpdatePayload {
    const patch: WorkItemUpdatePayload = {};
    if (title.trim() !== workItem.title) patch.title = title.trim();
    if (description !== (workItem.description ?? '')) patch.description = description;
    if (priority !== workItem.priority) patch.priority = priority;
    if (type !== workItem.type) patch.type = type;
    return patch;
  }

  const hasChanges = Object.keys(buildPatch()).length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!hasChanges || saving) return;
    setSaving(true);
    clearErrors();
    try {
      const patch = buildPatch();
      const res = await apiPatch<{ data: WorkItemResponse }>(
        `/api/v1/work-items/${workItem.id}`,
        patch
      );
      onSaved(res.data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Editar elemento</DialogTitle>
        </DialogHeader>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {/* Title */}
          <div className="space-y-1.5">
            <Label htmlFor="edit-title">Título *</Label>
            <Input
              id="edit-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              aria-invalid={!!fieldErrors['title']}
              aria-describedby={fieldErrors['title'] ? 'edit-title-error' : undefined}
            />
            {fieldErrors['title'] && (
              <p id="edit-title-error" className="text-body-sm text-destructive" role="alert">
                {fieldErrors['title']}
              </p>
            )}
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <Label htmlFor="edit-description">Descripción</Label>
            <Textarea
              id="edit-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              aria-invalid={!!fieldErrors['description']}
              aria-describedby={fieldErrors['description'] ? 'edit-description-error' : undefined}
            />
            {fieldErrors['description'] && (
              <p id="edit-description-error" className="text-body-sm text-destructive" role="alert">
                {fieldErrors['description']}
              </p>
            )}
          </div>

          {/* Priority */}
          <div className="space-y-1.5">
            <Label htmlFor="edit-priority">Prioridad</Label>
            <Select
              value={priority ?? '__none__'}
              onValueChange={(v) => setPriority(v === '__none__' ? null : (v as Priority))}
            >
              <SelectTrigger id="edit-priority">
                <SelectValue placeholder="Sin prioridad" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Sin prioridad</SelectItem>
                {(Object.entries(PRIORITY_LABELS) as [Priority, string][]).map(([val, label]) => (
                  <SelectItem key={val} value={val}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Type */}
          <div className="space-y-1.5">
            <Label htmlFor="edit-type">Tipo</Label>
            <Select
              value={type}
              onValueChange={(v) => setType(v as WorkItemType)}
            >
              <SelectTrigger id="edit-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.entries(TYPE_LABELS) as [WorkItemType, string][]).map(([val, label]) => (
                  <SelectItem key={val} value={val}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!hasChanges || saving}>
              {saving ? 'Guardando...' : 'Guardar'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
