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
        data: {
          items: [
            {
              id: 'e1',
              category: 'work_item',
              action: 'create',
              actor_id: 'u1',
              actor_display: 'Ada',
              entity_type: 'work_item',
              entity_id: 'wi1',
              before_value: null,
              after_value: null,
              context: null,
              created_at: '2026-04-16T10:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
        },
      })
    ),
    http.get('http://localhost/api/v1/admin/health', () =>
      HttpResponse.json({
        data: {
          workspace_id: 'ws1',
          work_items_by_state: { draft: 2, in_review: 1 },
          total_active: 3,
        },
      })
    ),
    http.get('http://localhost/api/v1/projects', () =>
      HttpResponse.json({ data: [{ id: 'p1', name: 'Alpha', description: null, created_at: '2026-01-01T00:00:00Z' }] })
    ),
    http.get('http://localhost/api/v1/integrations/configs', () =>
      HttpResponse.json({
        data: [
          {
            id: 'i1',
            workspace_id: 'ws1',
            integration_type: 'jira',
            project_id: null,
            mapping: null,
            is_active: true,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
            created_by: 'u1',
          },
        ],
      })
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
      expect(screen.getByText(/activos/i)).toBeTruthy();
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

  it('integrations tab — nueva integración dialog shows jira credential fields', async () => {
    setupAllHandlers();
    server.use(
      http.post('http://localhost/api/v1/integrations/configs', () =>
        HttpResponse.json(
          {
            data: {
              id: 'i2',
              workspace_id: 'ws1',
              integration_type: 'jira',
              project_id: null,
              mapping: null,
              is_active: true,
              created_at: '2026-04-17T00:00:00Z',
              updated_at: '2026-04-17T00:00:00Z',
              created_by: 'u1',
            },
          },
          { status: 201 }
        )
      )
    );
    const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
    render(<AdminPage params={{ slug: 'acme' }} />);

    await userEvent.click(await screen.findByRole('tab', { name: /integraciones/i }));
    await userEvent.click(await screen.findByRole('button', { name: /nueva integración/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/url base de jira/i)).toBeTruthy();
      expect(screen.getByLabelText(/email/i)).toBeTruthy();
      expect(screen.getByLabelText(/api token/i)).toBeTruthy();
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

  it('tags tab — create tag shows field error when name is taken', async () => {
    setupAllHandlers();
    server.use(
      http.post('http://localhost/api/v1/tags', () =>
        HttpResponse.json(
          { error: { code: 'TAG_NAME_TAKEN', message: 'tag \'urgent\' already exists in this workspace', field: 'name' } },
          { status: 409 }
        )
      )
    );
    const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
    render(<AdminPage params={{ slug: 'acme' }} />);

    await userEvent.click(await screen.findByRole('tab', { name: /etiquetas/i }));
    await userEvent.click(await screen.findByRole('button', { name: /nueva etiqueta/i }));

    const nameInput = await screen.findByLabelText(/nombre/i);
    await userEvent.type(nameInput, 'urgent');
    await userEvent.click(screen.getByRole('button', { name: /^crear$/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
      expect(screen.getByText(/already exists/i)).toBeTruthy();
    });
  });
});
