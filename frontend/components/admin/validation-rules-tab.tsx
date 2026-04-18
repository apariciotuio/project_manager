'use client';

import { useState } from 'react';
import { useValidationRules } from '@/hooks/use-admin';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { ValidationRule, RuleEnforcement } from '@/lib/types/api';

const ENFORCEMENT_VARIANT: Record<RuleEnforcement, 'default' | 'secondary' | 'destructive'> = {
  recommended: 'secondary',
  required: 'default',
  blocked_override: 'destructive',
};

interface CreateRuleFormState {
  work_item_type: string;
  validation_type: string;
  enforcement: RuleEnforcement;
  project_id: string;
}

const EMPTY_FORM: CreateRuleFormState = {
  work_item_type: '',
  validation_type: '',
  enforcement: 'recommended',
  project_id: '',
};

export function ValidationRulesTab() {
  const { rules, isLoading, error, createRule, updateRule, deleteRule } = useValidationRules();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ValidationRule | null>(null);
  const [form, setForm] = useState<CreateRuleFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.work_item_type.trim() || !form.validation_type.trim()) return;
    setSaving(true);
    setFormError(null);
    try {
      await createRule({
        work_item_type: form.work_item_type.trim(),
        validation_type: form.validation_type.trim(),
        enforcement: form.enforcement,
        ...(form.project_id ? { project_id: form.project_id } : {}),
      });
      setCreateOpen(false);
      setForm(EMPTY_FORM);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setFormError(msg.includes('rule_already_exists') ? 'A rule for this combination already exists' : msg);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteRule(deleteTarget.id);
      setDeleteTarget(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setDeleteError(msg.includes('rule_has_history') ? 'Cannot delete — use Deactivate instead' : msg);
    } finally {
      setDeleting(false);
    }
  }

  if (isLoading) {
    return (
      <div data-testid="rules-skeleton" className="space-y-3 animate-pulse">
        {[1, 2, 3].map((n) => <div key={n} className="h-12 rounded-md bg-muted" />)}
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="rules-error" role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-body-sm text-destructive">
        Failed to load validation rules: {error.message}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => { setCreateOpen(true); setFormError(null); }}>
          Add rule
        </Button>
      </div>

      {rules.length === 0 ? (
        <p data-testid="rules-empty" className="py-8 text-center text-muted-foreground">
          No validation rules configured.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-body-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="pb-2 pr-4 font-medium">Work item type</th>
                <th className="pb-2 pr-4 font-medium">Validation type</th>
                <th className="pb-2 pr-4 font-medium">Enforcement</th>
                <th className="pb-2 pr-4 font-medium">Scope</th>
                <th className="pb-2 pr-4 font-medium">Status</th>
                <th className="pb-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-medium">{r.work_item_type}</td>
                  <td className="py-2 pr-4">{r.validation_type}</td>
                  <td className="py-2 pr-4">
                    <Badge variant={ENFORCEMENT_VARIANT[r.enforcement]}>{r.enforcement}</Badge>
                  </td>
                  <td className="py-2 pr-4">
                    <span className="text-xs text-muted-foreground">
                      {r.project_id ? `project` : 'workspace'}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    {r.effective ? (
                      <Badge variant="default">effective</Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        superseded by {r.superseded_by?.slice(0, 8)}
                      </span>
                    )}
                  </td>
                  <td className="py-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive text-xs"
                      aria-label="Delete rule"
                      onClick={() => { setDeleteTarget(r); setDeleteError(null); }}
                    >
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={(v) => { setCreateOpen(v); if (!v) setFormError(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create validation rule</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => void handleCreate(e)} className="space-y-4">
            {formError && (
              <p role="alert" className="text-body-sm text-destructive">{formError}</p>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="rule-wit">Work item type *</Label>
              <Input
                id="rule-wit"
                value={form.work_item_type}
                onChange={(e) => setForm((f) => ({ ...f, work_item_type: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rule-vt">Validation type *</Label>
              <Input
                id="rule-vt"
                value={form.validation_type}
                onChange={(e) => setForm((f) => ({ ...f, validation_type: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>Enforcement</Label>
              <Select
                value={form.enforcement}
                onValueChange={(v) => setForm((f) => ({ ...f, enforcement: v as RuleEnforcement }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recommended">recommended</SelectItem>
                  <SelectItem value="required">required</SelectItem>
                  <SelectItem value="blocked_override">blocked_override</SelectItem>
                </SelectContent>
              </Select>
              {form.enforcement === 'blocked_override' && (
                <p className="text-xs text-amber-600">
                  This will supersede any project-level rule of the same type
                </p>
              )}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={!form.work_item_type.trim() || !form.validation_type.trim() || saving}>
                {saving ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <Dialog open={!!deleteTarget} onOpenChange={(v) => { if (!v) { setDeleteTarget(null); setDeleteError(null); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete validation rule</DialogTitle>
            <DialogDescription>
              Delete rule for &ldquo;{deleteTarget?.work_item_type}&rdquo; / &ldquo;{deleteTarget?.validation_type}&rdquo;? This cannot be undone.
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
