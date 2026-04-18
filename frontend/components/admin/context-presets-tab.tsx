'use client';

import { useState } from 'react';
import { useContextPresets } from '@/hooks/use-admin';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Pencil, Trash2, Plus } from 'lucide-react';
import type { ContextPreset } from '@/lib/types/api';

interface PresetFormState {
  name: string;
  description: string;
}

const EMPTY_FORM: PresetFormState = { name: '', description: '' };

export function ContextPresetsTab() {
  const { presets, isLoading, error, createPreset, updatePreset, deletePreset } =
    useContextPresets();

  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ContextPreset | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ContextPreset | null>(null);
  const [form, setForm] = useState<PresetFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function openCreate() {
    setForm(EMPTY_FORM);
    setFormError(null);
    setCreateOpen(true);
  }

  function openEdit(p: ContextPreset) {
    setForm({ name: p.name, description: p.description ?? '' });
    setFormError(null);
    setEditTarget(p);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setFormError(null);
    try {
      await createPreset({
        name: form.name.trim(),
        ...(form.description.trim() ? { description: form.description.trim() } : {}),
      });
      setCreateOpen(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editTarget || !form.name.trim()) return;
    setSaving(true);
    setFormError(null);
    try {
      await updatePreset(editTarget.id, { name: form.name.trim(), description: form.description.trim() || undefined });
      setEditTarget(null);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deletePreset(deleteTarget.id);
      setDeleteTarget(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setDeleteError(msg.includes('preset_in_use') ? `Cannot delete — ${msg}` : msg);
    } finally {
      setDeleting(false);
    }
  }

  if (isLoading) {
    return (
      <div data-testid="presets-skeleton" className="space-y-3 animate-pulse">
        {[1, 2, 3].map((n) => <div key={n} className="h-16 rounded-md bg-muted" />)}
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="presets-error" role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-body-sm text-destructive">
        Failed to load context presets: {error.message}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={openCreate}>
          <Plus className="mr-1.5 h-4 w-4" />
          New preset
        </Button>
      </div>

      {presets.length === 0 ? (
        <p data-testid="presets-empty" className="py-8 text-center text-muted-foreground">
          No context presets configured.
        </p>
      ) : (
        <div className="space-y-3">
          {presets.map((p) => (
            <div key={p.id} className="flex items-start justify-between rounded-lg border bg-card p-4">
              <div>
                <p className="font-medium">{p.name}</p>
                {p.description && (
                  <p className="text-body-sm text-muted-foreground">{p.description}</p>
                )}
                <p className="mt-1 text-xs text-muted-foreground">{p.sources.length} source{p.sources.length !== 1 ? 's' : ''}</p>
              </div>
              <div className="flex gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7"
                  aria-label={`Edit preset ${p.name}`}
                  onClick={() => openEdit(p)}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7 text-destructive hover:text-destructive"
                  aria-label="Delete preset"
                  onClick={() => { setDeleteTarget(p); setDeleteError(null); }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={(v) => { setCreateOpen(v); if (!v) setFormError(null); }}>
        <DialogContent>
          <DialogHeader><DialogTitle>New context preset</DialogTitle></DialogHeader>
          <form onSubmit={(e) => void handleCreate(e)} className="space-y-4">
            {formError && <p role="alert" className="text-body-sm text-destructive">{formError}</p>}
            <div className="space-y-1.5">
              <Label htmlFor="preset-name">Name *</Label>
              <Input
                id="preset-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="preset-desc">Description</Label>
              <Textarea
                id="preset-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={2}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={!form.name.trim() || saving}>
                {saving ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={!!editTarget} onOpenChange={(v) => { if (!v) { setEditTarget(null); setFormError(null); } }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit preset</DialogTitle></DialogHeader>
          <form onSubmit={(e) => void handleEdit(e)} className="space-y-4">
            {formError && <p role="alert" className="text-body-sm text-destructive">{formError}</p>}
            <div className="space-y-1.5">
              <Label htmlFor="edit-preset-name">Name *</Label>
              <Input
                id="edit-preset-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-preset-desc">Description</Label>
              <Textarea
                id="edit-preset-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={2}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditTarget(null)}>Cancel</Button>
              <Button type="submit" disabled={!form.name.trim() || saving}>
                {saving ? 'Saving...' : 'Save'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <Dialog open={!!deleteTarget} onOpenChange={(v) => { if (!v) { setDeleteTarget(null); setDeleteError(null); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete preset</DialogTitle>
            <DialogDescription>
              Delete &ldquo;{deleteTarget?.name}&rdquo;? This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {deleteError && (
            <p role="alert" className="text-body-sm text-destructive">{deleteError}</p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDeleteTarget(null); setDeleteError(null); }}>Cancel</Button>
            <Button variant="destructive" disabled={deleting} onClick={() => void handleDelete()}>
              {deleting ? 'Deleting...' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
