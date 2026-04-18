/**
 * EP-13 Groups 5/6 — Admin integrations page wires PuppetConfigForm + DocSourcesTable.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import AdminPage from '@/app/workspace/[slug]/admin/page';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  },
}));
vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({ user: { id: 'u1', is_superadmin: true } }),
}));
vi.mock('@/components/domain/relative-time', () => ({
  RelativeTime: ({ iso }: { iso: string }) => <span>{iso}</span>,
}));
vi.mock('@/components/admin/tag-edit-modal', () => ({
  TagEditModal: () => null,
}));

const BASE = 'http://localhost';

function stubAdminApis() {
  server.use(
    http.get(`${BASE}/api/v1/workspaces/current/members`, () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get(`${BASE}/api/v1/admin/audit`, () =>
      HttpResponse.json({ data: [], meta: { total: 0 } }),
    ),
    http.get(`${BASE}/api/v1/admin/health`, () =>
      HttpResponse.json({ data: { total_active: 0, work_items_by_state: {} } }),
    ),
    http.get(`${BASE}/api/v1/workspaces/current/projects`, () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get(`${BASE}/api/v1/integrations`, () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get(`${BASE}/api/v1/workspaces/current/tags`, () =>
      HttpResponse.json({ data: [] }),
    ),
    // Puppet & doc sources
    http.get(`${BASE}/api/v1/admin/integrations/puppet`, () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get(`${BASE}/api/v1/admin/documentation-sources`, () =>
      HttpResponse.json({ data: [] }),
    ),
  );
}

describe('AdminPage — puppet integrations tab', () => {
  it('shows Puppet tab in admin navigation', async () => {
    stubAdminApis();
    render(<AdminPage params={{ slug: 'acme' }} />);

    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /puppet/i })).toBeInTheDocument(),
    );
  });

  it('renders PuppetConfigForm when Puppet tab is active', async () => {
    stubAdminApis();
    render(<AdminPage params={{ slug: 'acme' }} />);

    const puppetTab = await screen.findByRole('tab', { name: /puppet/i });
    await userEvent.click(puppetTab);

    await waitFor(() =>
      expect(screen.getByLabelText(/base.?url/i)).toBeInTheDocument(),
    );
  });

  it('renders DocSourcesTable when Puppet tab is active', async () => {
    stubAdminApis();
    render(<AdminPage params={{ slug: 'acme' }} />);

    const puppetTab = await screen.findByRole('tab', { name: /puppet/i });
    await userEvent.click(puppetTab);

    await waitFor(() =>
      expect(screen.getByTestId('doc-sources-table')).toBeInTheDocument(),
    );
  });

  it('after PuppetConfigForm saves, updated config is reflected', async () => {
    stubAdminApis();
    server.use(
      http.post(`${BASE}/api/v1/admin/integrations/puppet`, () =>
        HttpResponse.json({
          data: {
            id: 'pc-1',
            base_url: 'https://puppet.example.com',
            state: 'active',
            last_health_check_status: 'unchecked',
            last_health_check_at: '2026-04-15T00:00:00Z',
            created_at: '2026-04-15T00:00:00Z',
          },
        }),
      ),
    );

    render(<AdminPage params={{ slug: 'acme' }} />);

    const puppetTab = await screen.findByRole('tab', { name: /puppet/i });
    await userEvent.click(puppetTab);

    const baseUrlInput = await screen.findByLabelText(/base.?url/i);
    await userEvent.type(baseUrlInput, 'https://puppet.example.com');

    const apiKeyInput = screen.getByLabelText(/api.?key/i);
    await userEvent.type(apiKeyInput, 'secret-key');

    const saveBtn = screen.getByRole('button', { name: /save/i });
    await userEvent.click(saveBtn);

    // After save, form reflects updated config (baseUrl still populated)
    await waitFor(() =>
      expect((baseUrlInput as HTMLInputElement).value).toBe('https://puppet.example.com'),
    );
  });
});
