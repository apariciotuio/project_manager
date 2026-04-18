'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import type { DocSourceCreate, DocSourceType } from '@/lib/types/puppet';

interface AddDocSourceModalProps {
  open: boolean;
  workspaceId: string;
  onClose: () => void;
  onSubmit: (data: DocSourceCreate) => Promise<void>;
}

function validateUrl(url: string, sourceType: DocSourceType): string | null {
  if (!url.trim()) return null; // handled by required check
  switch (sourceType) {
    case 'github_repo':
      return url.startsWith('https://github.com/') ? null : 'invalidGithubUrl';
    case 'url':
      return url.startsWith('http://') || url.startsWith('https://') ? null : 'invalidHttpUrl';
    case 'path':
      return url.startsWith('/') || url.startsWith('./') || url.startsWith('../') ? null : 'invalidPath';
  }
}

export function AddDocSourceModal({
  open,
  workspaceId,
  onClose,
  onSubmit,
}: AddDocSourceModalProps) {
  const t = useTranslations('workspace.admin.docSources.modal');
  const tBase = useTranslations('workspace.admin.docSources');

  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [sourceType, setSourceType] = useState<DocSourceType>('github_repo');
  const [isPublic, setIsPublic] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  function validate(): boolean {
    if (!name.trim()) {
      setValidationError(t('errors.nameRequired'));
      return false;
    }
    if (!url.trim()) {
      setValidationError(t('errors.urlRequired'));
      return false;
    }
    const urlErr = validateUrl(url.trim(), sourceType);
    if (urlErr) {
      setValidationError(t(`errors.${urlErr}`));
      return false;
    }
    setValidationError(null);
    return true;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      await onSubmit({
        workspace_id: workspaceId,
        name: name.trim(),
        source_type: sourceType,
        url: url.trim(),
        is_public: isPublic,
      });
      onClose();
    } catch {
      // parent handles errors
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('title')}</DialogTitle>
        </DialogHeader>

        <form id="add-doc-source-form" onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {/* Source type */}
          <div className="space-y-1.5">
            <Label htmlFor="doc-source-type">{t('fields.sourceType')}</Label>
            <Select
              value={sourceType}
              onValueChange={(v) => {
                setSourceType(v as DocSourceType);
                setValidationError(null);
              }}
            >
              <SelectTrigger id="doc-source-type" aria-label={t('fields.sourceType')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="github_repo">{tBase('sourceTypes.github_repo')}</SelectItem>
                <SelectItem value="url">{tBase('sourceTypes.url')}</SelectItem>
                <SelectItem value="path">{tBase('sourceTypes.path')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Name */}
          <div className="space-y-1.5">
            <Label htmlFor="doc-source-name">{t('fields.name')}</Label>
            <Input
              id="doc-source-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('fields.namePlaceholder')}
              aria-invalid={!!validationError}
            />
          </div>

          {/* URL */}
          <div className="space-y-1.5">
            <Label htmlFor="doc-source-url">{t('fields.url')}</Label>
            <Input
              id="doc-source-url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={t('fields.urlPlaceholder')}
              aria-invalid={!!validationError}
            />
          </div>

          {/* Is public */}
          <div className="flex items-center gap-2">
            <input
              id="doc-source-public"
              type="checkbox"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
              className="h-4 w-4"
              aria-label={t('fields.isPublic')}
            />
            <Label htmlFor="doc-source-public">{t('fields.isPublic')}</Label>
          </div>

          {validationError && (
            <p role="alert" className="text-body-sm text-destructive">
              {validationError}
            </p>
          )}
        </form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            {t('cancel')}
          </Button>
          <Button type="submit" form="add-doc-source-form" disabled={submitting}>
            {submitting ? t('submitting') : t('submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
