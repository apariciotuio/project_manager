import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

import { PuppetConfigForm } from '@/components/admin/puppet-config-form';
import type { PuppetConfig } from '@/lib/types/puppet';

const BASE_CONFIG: PuppetConfig = {
  id: 'cfg-1',
  base_url: 'https://puppet.example.com',
  state: 'active',
  last_health_check_status: 'ok',
  last_health_check_at: '2026-04-18T10:00:00Z',
  created_at: '2026-04-01T00:00:00Z',
};

// Translation-key regex helpers
const RX_BASE_URL = /workspace\.admin\.integrations\.puppet\.fields\.baseUrl/i;
const RX_API_KEY = /workspace\.admin\.integrations\.puppet\.fields\.apiKey/i;
const RX_SAVE = /workspace\.admin\.integrations\.puppet\.save/i;
const RX_TEST = /workspace\.admin\.integrations\.puppet\.testConnection/i;

function renderForm(config: PuppetConfig | null = null, workspaceId = 'ws-1') {
  const onSaved = vi.fn();
  render(<PuppetConfigForm existingConfig={config} workspaceId={workspaceId} onSaved={onSaved} />);
  return { onSaved };
}

describe('PuppetConfigForm', () => {
  it('renders base_url and api_key fields', () => {
    renderForm();
    expect(screen.getByLabelText(RX_BASE_URL)).toBeInTheDocument();
    expect(screen.getByLabelText(RX_API_KEY)).toBeInTheDocument();
  });

  it('api_key field is masked (type=password)', () => {
    renderForm();
    expect(screen.getByLabelText(RX_API_KEY)).toHaveAttribute('type', 'password');
  });

  it('api_key has "Enter new key to rotate" placeholder in edit mode', () => {
    renderForm(BASE_CONFIG);
    const input = screen.getByLabelText(RX_API_KEY);
    expect(input).toHaveAttribute(
      'placeholder',
      expect.stringMatching(/workspace\.admin\.integrations\.puppet\.apiKeyRotatePlaceholder/i)
    );
  });

  it('shows inline validation error when base_url is empty and form submitted', async () => {
    const user = userEvent.setup();
    renderForm();
    await user.click(screen.getByRole('button', { name: RX_SAVE }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('POSTs with correct shape when creating new config', async () => {
    const user = userEvent.setup();
    let postedBody: unknown;
    server.use(
      http.post('http://localhost/api/v1/admin/integrations/puppet', async ({ request }) => {
        postedBody = await request.json();
        return HttpResponse.json({ data: BASE_CONFIG });
      })
    );
    const { onSaved } = renderForm(null, 'ws-1');
    await user.type(screen.getByLabelText(RX_BASE_URL), 'https://puppet.example.com');
    await user.type(screen.getByLabelText(RX_API_KEY), 'secret-key');
    await user.click(screen.getByRole('button', { name: RX_SAVE }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(BASE_CONFIG));
    expect(postedBody).toMatchObject({
      base_url: 'https://puppet.example.com',
      api_key: 'secret-key',
      workspace_id: 'ws-1',
    });
  });

  it('PATCHes when existing config is provided', async () => {
    const user = userEvent.setup();
    let patchedBody: unknown;
    const updated = { ...BASE_CONFIG, base_url: 'https://new.example.com' };
    server.use(
      http.patch('http://localhost/api/v1/admin/integrations/puppet/cfg-1', async ({ request }) => {
        patchedBody = await request.json();
        return HttpResponse.json({ data: updated });
      })
    );
    const { onSaved } = renderForm(BASE_CONFIG, 'ws-1');
    const urlInput = screen.getByLabelText(RX_BASE_URL);
    await user.clear(urlInput);
    await user.type(urlInput, 'https://new.example.com');
    await user.click(screen.getByRole('button', { name: RX_SAVE }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(updated));
    expect(patchedBody).toMatchObject({ base_url: 'https://new.example.com' });
  });

  it('renders health status badge with correct status', () => {
    renderForm(BASE_CONFIG);
    // badge should reflect 'ok' status
    expect(
      screen.getByTestId('puppet-health-badge')
    ).toBeInTheDocument();
  });

  it('health status error renders warning variant badge', () => {
    renderForm({ ...BASE_CONFIG, last_health_check_status: 'error' });
    const badge = screen.getByTestId('puppet-health-badge');
    expect(badge).toHaveAttribute('data-status', 'error');
  });

  it('"Test Connection" button calls health-check endpoint and updates badge', async () => {
    const user = userEvent.setup();
    server.use(
      http.post('http://localhost/api/v1/admin/puppet/cfg-1/health-check', () =>
        HttpResponse.json({ data: { ...BASE_CONFIG, last_health_check_status: 'error' } })
      )
    );
    renderForm(BASE_CONFIG);
    await user.click(screen.getByRole('button', { name: RX_TEST }));
    await waitFor(() => {
      expect(screen.getByTestId('puppet-health-badge')).toHaveAttribute('data-status', 'error');
    });
  });

  it('"Test Connection" button shows loading state while request is in flight', async () => {
    const user = userEvent.setup();
    let resolve!: () => void;
    server.use(
      http.post('http://localhost/api/v1/admin/puppet/cfg-1/health-check', () =>
        new Promise<Response>((res) => {
          resolve = () => res(HttpResponse.json({ data: BASE_CONFIG }) as unknown as Response);
        })
      )
    );
    renderForm(BASE_CONFIG);
    await user.click(screen.getByRole('button', { name: RX_TEST }));
    expect(
      screen.getByRole('button', { name: /workspace\.admin\.integrations\.puppet\.testing/i })
    ).toBeDisabled();
    resolve();
  });
});
