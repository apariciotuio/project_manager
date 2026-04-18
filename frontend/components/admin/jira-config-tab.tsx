'use client';

import { useState } from 'react';
import { useJiraConfigs } from '@/hooks/use-admin';
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
} from '@/components/ui/dialog';
import type { JiraConfig, JiraConfigState, JiraTestResult } from '@/lib/types/api';

const STATE_VARIANT: Record<JiraConfigState, 'default' | 'secondary' | 'destructive'> = {
  active: 'default',
  disabled: 'secondary',
  error: 'destructive',
};

interface TestResult {
  configId: string;
  result: JiraTestResult;
}

interface CreateFormState {
  base_url: string;
  token: string;
  validationError: string | null;
  serverError: string | null;
}

const EMPTY_FORM: CreateFormState = {
  base_url: '',
  token: '',
  validationError: null,
  serverError: null,
};

export function JiraConfigTab() {
  const { configs, isLoading, error, createConfig, testConnection } = useJiraConfigs();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<CreateFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, JiraTestResult>>({});

  function validateForm(): boolean {
    if (!form.base_url.startsWith('https://')) {
      setForm((f) => ({ ...f, validationError: 'Base URL must use HTTPS' }));
      return false;
    }
    return true;
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!validateForm()) return;
    setSaving(true);
    setForm((f) => ({ ...f, serverError: null }));
    try {
      await createConfig({
        base_url: form.base_url.trim(),
        credentials: { token: form.token },
      });
      setCreateOpen(false);
      setForm(EMPTY_FORM);
    } catch (err) {
      setForm((f) => ({
        ...f,
        serverError: err instanceof Error ? err.message : String(err),
      }));
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(configId: string) {
    setTestingId(configId);
    try {
      const result = await testConnection(configId);
      setTestResults((prev) => ({ ...prev, [configId]: result }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [configId]: { status: 'unreachable', message: err instanceof Error ? err.message : String(err) },
      }));
    } finally {
      setTestingId(null);
    }
  }

  function testResultLabel(result: JiraTestResult): string {
    if (result.status === 'ok') return 'Connection successful';
    if (result.status === 'auth_failure') return result.message ?? 'Authentication failed — check your API token';
    return result.message ?? 'Connection timed out or unreachable';
  }

  if (isLoading) {
    return (
      <div data-testid="jira-configs-skeleton" className="space-y-3 animate-pulse">
        {[1, 2].map((n) => <div key={n} className="h-16 rounded-md bg-muted" />)}
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="jira-configs-error" role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-body-sm text-destructive">
        Failed to load Jira configs: {error.message}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => { setCreateOpen(true); setForm(EMPTY_FORM); }}>
          Add Jira config
        </Button>
      </div>

      {configs.length === 0 ? (
        <p data-testid="jira-configs-empty" className="py-8 text-center text-muted-foreground">
          No Jira integrations configured.
        </p>
      ) : (
        <div className="space-y-3">
          {configs.map((c) => {
            const testResult = testResults[c.id];
            const isTesting = testingId === c.id;
            return (
              <div key={c.id} className="rounded-lg border bg-card p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{c.base_url}</p>
                    <p className="text-xs text-muted-foreground">{c.auth_type}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={STATE_VARIANT[c.state]}>{c.state}</Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs"
                      disabled={isTesting}
                      onClick={() => void handleTest(c.id)}
                    >
                      {isTesting ? 'Testing...' : 'Test connection'}
                    </Button>
                  </div>
                </div>
                {testResult && (
                  <p className={`mt-2 text-xs ${testResult.status === 'ok' ? 'text-green-600' : 'text-destructive'}`}>
                    {testResultLabel(testResult)}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={(v) => { setCreateOpen(v); if (!v) setForm(EMPTY_FORM); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Jira config</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => void handleCreate(e)} className="space-y-4">
            {form.serverError && (
              <p role="alert" className="text-body-sm text-destructive">{form.serverError}</p>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="jira-base-url">Base URL *</Label>
              <Input
                id="jira-base-url"
                placeholder="https://yourcompany.atlassian.net"
                value={form.base_url}
                onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value, validationError: null }))}
                required
              />
              {form.validationError && (
                <p role="alert" className="text-xs text-destructive">{form.validationError}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="jira-token">API Token</Label>
              <Input
                id="jira-token"
                type="password"
                placeholder="Token (write-only)"
                value={form.token}
                onChange={(e) => setForm((f) => ({ ...f, token: e.target.value }))}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={!form.base_url.trim() || saving}>
                {saving ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
