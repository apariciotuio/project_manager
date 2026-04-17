'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
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

// ─── Option sets (authoritative) ──────────────────────────────────────────────

const PRIORITY_VALUES: readonly Priority[] = ['low', 'medium', 'high', 'critical'];
const TYPE_VALUES: readonly WorkItemType[] = [
  'idea',
  'bug',
  'enhancement',
  'task',
  'initiative',
  'spike',
  'business_change',
  'requirement',
  'milestone',
  'story',
];

const isPriority = (v: string): v is Priority => (PRIORITY_VALUES as readonly string[]).includes(v);
const isWorkItemType = (v: string): v is WorkItemType =>
  (TYPE_VALUES as readonly string[]).includes(v);

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
  const t = useTranslations('modals.workItemEdit');
  const tCommon = useTranslations('common');

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
          <DialogTitle>{t('title')}</DialogTitle>
        </DialogHeader>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {/* Title */}
          <div className="space-y-1.5">
            <Label htmlFor="edit-title">{t('fields.title')}</Label>
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
            <Label htmlFor="edit-description">{t('fields.description')}</Label>
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
            <Label htmlFor="edit-priority">{t('fields.priority')}</Label>
            <Select
              value={priority ?? '__none__'}
              onValueChange={(v) => {
                if (v === '__none__') { setPriority(null); return; }
                if (isPriority(v)) setPriority(v);
              }}
            >
              <SelectTrigger id="edit-priority">
                <SelectValue placeholder={t('fields.noPriority')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">{t('fields.noPriority')}</SelectItem>
                {PRIORITY_VALUES.map((val) => (
                  <SelectItem key={val} value={val}>{t(`priority.${val}`)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Type */}
          <div className="space-y-1.5">
            <Label htmlFor="edit-type">{t('fields.type')}</Label>
            <Select
              value={type}
              onValueChange={(v) => { if (isWorkItemType(v)) setType(v); }}
            >
              <SelectTrigger id="edit-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TYPE_VALUES.map((val) => (
                  <SelectItem key={val} value={val}>{t(`type.${val}`)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              {tCommon('cancel')}
            </Button>
            <Button type="submit" disabled={!hasChanges || saving}>
              {saving ? tCommon('saving') : tCommon('save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
