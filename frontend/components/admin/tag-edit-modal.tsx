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
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { ColorPicker } from '@/components/ui/color-picker';
import { apiPatch } from '@/lib/api-client';
import { useFormErrors } from '@/lib/errors/use-form-errors';
import type { Tag } from '@/lib/types/api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface TagUpdatePayload {
  name?: string;
  color?: string | null;
}

export interface TagEditModalProps {
  open: boolean;
  tag: Tag;
  onClose: () => void;
  onSaved: (updated: Tag) => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function TagEditModal({ open, tag, onClose, onSaved }: TagEditModalProps) {
  const t = useTranslations('modals.tagEdit');
  const tCommon = useTranslations('common');

  const [name, setName] = useState(tag.name);
  const [color, setColor] = useState<string | undefined>(tag.color ?? undefined);
  const [saving, setSaving] = useState(false);

  const { fieldErrors, handleApiError, clearErrors } = useFormErrors();

  // Reset when modal opens/tag changes
  useEffect(() => {
    if (open) {
      setName(tag.name);
      setColor(tag.color ?? undefined);
      clearErrors();
    }
  }, [open, tag, clearErrors]);

  function buildPatch(): TagUpdatePayload {
    const patch: TagUpdatePayload = {};
    if (name.trim() !== tag.name) patch.name = name.trim();
    if ((color ?? null) !== (tag.color ?? null)) patch.color = color ?? null;
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
      const res = await apiPatch<{ data: Tag }>(`/api/v1/tags/${tag.id}`, patch);
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
          <DialogTitle>
            {t('title')}
            {tag.archived && (
              <Badge variant="secondary" className="ml-2 text-xs">
                {t('archived')}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {/* Name */}
          <div className="space-y-1.5">
            <Label htmlFor="tag-edit-name">{t('fields.name')}</Label>
            <Input
              id="tag-edit-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              aria-invalid={!!fieldErrors['name']}
              aria-describedby={fieldErrors['name'] ? 'tag-edit-name-error' : undefined}
            />
            {fieldErrors['name'] && (
              <p id="tag-edit-name-error" className="text-body-sm text-destructive" role="alert">
                {fieldErrors['name']}
              </p>
            )}
          </div>

          {/* Color */}
          <div className="space-y-1.5">
            <Label>{t('fields.color')}</Label>
            <ColorPicker value={color} onChange={setColor} />
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
