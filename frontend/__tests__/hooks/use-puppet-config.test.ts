import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

import { usePuppetConfig } from '@/hooks/use-puppet-config';
import type { PuppetConfig } from '@/lib/types/puppet';

const BASE_CONFIG: PuppetConfig = {
  id: 'cfg-1',
  base_url: 'https://puppet.example.com',
  state: 'active',
  last_health_check_status: 'ok',
  last_health_check_at: '2026-04-18T10:00:00Z',
  created_at: '2026-04-01T00:00:00Z',
};

describe('usePuppetConfig', () => {
  it('loads config on mount', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/integrations/puppet', () =>
        HttpResponse.json({ data: [BASE_CONFIG] })
      )
    );
    const { result } = renderHook(() => usePuppetConfig());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.config).toEqual(BASE_CONFIG);
  });

  it('returns null config when list is empty', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/integrations/puppet', () =>
        HttpResponse.json({ data: [] })
      )
    );
    const { result } = renderHook(() => usePuppetConfig());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.config).toBeNull();
  });

  it('sets error on fetch failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/integrations/puppet', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'fail' } }, { status: 500 })
      )
    );
    const { result } = renderHook(() => usePuppetConfig());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).not.toBeNull();
  });

  it('createConfig POSTs and updates state', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/integrations/puppet', () =>
        HttpResponse.json({ data: [] })
      ),
      http.post('http://localhost/api/v1/admin/integrations/puppet', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>;
        expect(body['base_url']).toBe('https://puppet.example.com');
        return HttpResponse.json({ data: BASE_CONFIG });
      })
    );
    const { result } = renderHook(() => usePuppetConfig());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.createConfig({
        base_url: 'https://puppet.example.com',
        api_key: 'secret',
        workspace_id: 'ws-1',
      });
    });

    expect(result.current.config).toEqual(BASE_CONFIG);
  });

  it('updateConfig PATCHes the existing config', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/integrations/puppet', () =>
        HttpResponse.json({ data: [BASE_CONFIG] })
      ),
      http.patch('http://localhost/api/v1/admin/integrations/puppet/cfg-1', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>;
        expect(body['base_url']).toBe('https://updated.example.com');
        return HttpResponse.json({ data: { ...BASE_CONFIG, base_url: 'https://updated.example.com' } });
      })
    );
    const { result } = renderHook(() => usePuppetConfig());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.updateConfig('cfg-1', { base_url: 'https://updated.example.com' });
    });

    expect(result.current.config?.base_url).toBe('https://updated.example.com');
  });

  it('runHealthCheck POSTs and updates status', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/integrations/puppet', () =>
        HttpResponse.json({ data: [BASE_CONFIG] })
      ),
      http.post('http://localhost/api/v1/admin/puppet/cfg-1/health-check', () =>
        HttpResponse.json({ data: { ...BASE_CONFIG, last_health_check_status: 'error' } })
      )
    );
    const { result } = renderHook(() => usePuppetConfig());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.runHealthCheck('cfg-1');
    });

    expect(result.current.config?.last_health_check_status).toBe('error');
  });
});
