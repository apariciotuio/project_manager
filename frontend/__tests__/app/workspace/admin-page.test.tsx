import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ slug: 'acme' }),
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: { id: 'u1', full_name: 'Ada Lovelace', workspace_id: 'ws1', workspace_slug: 'acme', email: 'ada@co.com', avatar_url: null, is_superadmin: false },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

function setupAllHandlers() {
  server.use(
    http.get('http://localhost/api/v1/admin/audit-events', () =>
      HttpResponse.json({
        data: [
          { id: 'e1', actor_id: 'u1', actor_name: 'Ada', action: 'create', resource_type: 'work_item', resource_id: 'wi1', metadata: null, created_at: '2026-04-16T10:00:00Z' },
        ],
        total: 1,
      })
    ),
    http.get('http://localhost/api/v1/admin/health', () =>
      HttpResponse.json({ status: 'ok', checks: [{ name: 'db', status: 'ok', latency_ms: 3, message: null }], version: '1.0.0' })
    ),
    http.get('http://localhost/api/v1/projects', () =>
      HttpResponse.json({ data: [{ id: 'p1', name: 'Alpha', description: null, created_at: '2026-01-01T00:00:00Z' }] })
    ),
    http.get('http://localhost/api/v1/integrations/configs', () =>
      HttpResponse.json({ data: [{ id: 'i1', provider: 'jira', enabled: true, config: {}, created_at: '2026-01-01T00:00:00Z' }] })
    ),
    http.get('http://localhost/api/v1/tags', () =>
      HttpResponse.json({ data: [{ id: 'tag1', name: 'urgent', color: '#ff0000', archived: false, created_at: '2026-01-01T00:00:00Z' }] })
    )
  );
}

describe('AdminPage', () => {
  it('renders tab list with all sections', async () => {
    setupAllHandlers();
    const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
    render(<AdminPage params={{ slug: 'acme' }} />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /miembros/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /auditoría/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /salud/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /proyectos/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /integraciones/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /etiquetas/i })).toBeTruthy();
    });
  });

  it('members tab shows current user', async () => {
    setupAllHandlers();
    const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
    render(<AdminPage params={{ slug: 'acme' }} />);

    expect(await screen.findByText('Ada Lovelace')).toBeTruthy();
  });

  it('audit tab shows action column', async () => {
    setupAllHandlers();
    const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
    render(<AdminPage params={{ slug: 'acme' }} />);

    await userEvent.click(await screen.findByRole('tab', { name: /auditoría/i }));

    await waitFor(() => {
      expect(screen.getByText('create')).toBeTruthy();
    });
  });

  it('health tab shows status', async () => {
    setupAllHandlers();
    const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
    render(<AdminPage params={{ slug: 'acme' }} />);

    await userEvent.click(await screen.findByRole('tab', { name: /salud/i }));

    await waitFor(() => {
      expect(screen.getByText(/estado general/i)).toBeTruthy();
    });
  });

  it('projects tab shows project names', async () => {
    setupAllHandlers();
    const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
    render(<AdminPage params={{ slug: 'acme' }} />);

    await userEvent.click(await screen.findByRole('tab', { name: /proyectos/i }));

    await waitFor(() => {
      expect(screen.getByText('Alpha')).toBeTruthy();
    });
  });

  it('integrations tab shows provider names', async () => {
    setupAllHandlers();
    const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
    render(<AdminPage params={{ slug: 'acme' }} />);

    await userEvent.click(await screen.findByRole('tab', { name: /integraciones/i }));

    await waitFor(() => {
      expect(screen.getByText('jira')).toBeTruthy();
    });
  });

  it('tags tab shows tag names', async () => {
    setupAllHandlers();
    const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
    render(<AdminPage params={{ slug: 'acme' }} />);

    await userEvent.click(await screen.findByRole('tab', { name: /etiquetas/i }));

    await waitFor(() => {
      expect(screen.getByText('urgent')).toBeTruthy();
    });
  });
});
