'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PuppetHealthBadge } from '@/components/admin/puppet-health-badge';
import { apiPost, apiPatch } from '@/lib/api-client';
import type {
  PuppetConfig,
  PuppetConfigCreate,
  PuppetConfigUpdate,
  PuppetConfigResponse,
} from '@/lib/types/puppet';

interface PuppetConfigFormProps {
  existingConfig: PuppetConfig | null;
  workspaceId: string;
  onSaved: (config: PuppetConfig) => void;
}

export function PuppetConfigForm({ existingConfig, workspaceId, onSaved }: PuppetConfigFormProps) {
  const t = useTranslations('workspace.admin.integrations.puppet');

  const [baseUrl, setBaseUrl] = useState(existingConfig?.base_url ?? '');
  const [apiKey, setApiKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState(
    existingConfig?.last_health_check_status ?? 'unchecked'
  );

  const isEdit = existingConfig !== null;

  function validate(): boolean {
    if (!baseUrl.trim()) {
      setUrlError(t('errors.baseUrlRequired'));
      return false;
    }
    setUrlError(null);
    return true;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    try {
      let saved: PuppetConfig;
      if (isEdit && existingConfig) {
        const patch: PuppetConfigUpdate = {};
        if (baseUrl.trim() !== existingConfig.base_url) patch.base_url = baseUrl.trim();
        if (apiKey.trim()) patch.api_key = apiKey;
        const res = await apiPatch<PuppetConfigResponse>(
          `/api/v1/admin/integrations/puppet/${existingConfig.id}`,
          patch
        );
        saved = res.data;
      } else {
        const req: PuppetConfigCreate = {
          base_url: baseUrl.trim(),
          api_key: apiKey,
          workspace_id: workspaceId,
        };
        const res = await apiPost<PuppetConfigResponse>('/api/v1/admin/integrations/puppet', req);
        saved = res.data;
      }
      setHealthStatus(saved.last_health_check_status);
      onSaved(saved);
    } finally {
      setSaving(false);
    }
  }

  async function handleTestConnection() {
    if (!existingConfig) return;
    setTesting(true);
    try {
      const res = await apiPost<PuppetConfigResponse>(
        `/api/v1/admin/puppet/${existingConfig.id}/health-check`,
        {}
      );
      setHealthStatus(res.data.last_health_check_status);
    } finally {
      setTesting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
      {/* Health status */}
      <div className="flex items-center gap-3">
        <PuppetHealthBadge status={healthStatus as 'ok' | 'error' | 'unchecked'} />
        {existingConfig && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={testing}
            onClick={() => void handleTestConnection()}
          >
            {testing ? t('testing') : t('testConnection')}
          </Button>
        )}
      </div>

      {/* Base URL */}
      <div className="space-y-1.5">
        <Label htmlFor="puppet-base-url">{t('fields.baseUrl')}</Label>
        <Input
          id="puppet-base-url"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://puppet.example.com"
          aria-invalid={!!urlError}
          aria-describedby={urlError ? 'puppet-base-url-error' : undefined}
        />
        {urlError && (
          <p id="puppet-base-url-error" role="alert" className="text-body-sm text-destructive">
            {urlError}
          </p>
        )}
      </div>

      {/* API Key */}
      <div className="space-y-1.5">
        <Label htmlFor="puppet-api-key">{t('fields.apiKey')}</Label>
        <Input
          id="puppet-api-key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={isEdit ? t('apiKeyRotatePlaceholder') : ''}
        />
      </div>

      <Button type="submit" disabled={saving}>
        {saving ? t('saving') : t('save')}
      </Button>
    </form>
  );
}
