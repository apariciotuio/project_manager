import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ slug: 'acme' }),
}));

// next-intl mock — TagEditModal uses useTranslations
vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      full_name: 'Ada Lovelace',
      workspace_id: 'ws1',
      workspace_slug: 'acme',
      email: 'ada@co.com',
      avatar_url: null,
      is_superadmin: false,
    },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

const MEMBER_FIXTURE = {
  id: 'u1',
  user_id: 'u1',
  email: 'ada@co.com',
  display_name: 'Ada Lovelace',
  state: 'active',
  role: 'admin',
  capabilities: [],
  context_labels: [],
  joined_at: '2026-01-01T00:00:00Z',
};

const ADMIN_MEMBERS_RESPONSE = {
  data: { items: [MEMBER_FIXTURE], pagination: { cursor: null, has_next: false } },
  message: 'ok',
};

const AUDIT_EVENT_FIXTURE = {
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
};

const PROJECT_FIXTURE = {
  id: 'p1',
  name: 'Alpha',
  description: null,
  created_at: '2026-01-01T00:00:00Z',
};

const INTEGRATION_FIXTURE = {
  id: 'i1',
  workspace_id: 'ws1',
  integration_type: 'jira',
  project_id: null,
  mapping: null,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  created_by: 'u1',
};

const TAG_FIXTURE = {
  id: 'tag1',
  name: 'urgent',
  color: '#ff0000',
  archived: false,
  created_at: '2026-01-01T00:00:00Z',
};

function setupAllHandlers() {
  server.use(
    // New admin members endpoint (EP-10)
    http.get('http://localhost/api/v1/admin/members', () =>
      HttpResponse.json(ADMIN_MEMBERS_RESPONSE)
    ),
    http.get('http://localhost/api/v1/admin/audit-events', () =>
      HttpResponse.json({
        data: {
          items: [AUDIT_EVENT_FIXTURE],
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
    http.get('http://localhost/api/v1/admin/dashboard', () =>
      HttpResponse.json({ data: { member_count: 1, project_count: 1, integration_count: 0, recent_audit_count: 0, health: 'healthy', work_items_by_state: {}, total_active: 0 }, message: 'ok' })
    ),
    http.get('http://localhost/api/v1/projects', () =>
      HttpResponse.json({ data: [PROJECT_FIXTURE] })
    ),
    http.get('http://localhost/api/v1/integrations/configs', () =>
      HttpResponse.json({ data: [INTEGRATION_FIXTURE] })
    ),
    http.get('http://localhost/api/v1/admin/integrations/jira', () =>
      HttpResponse.json({ data: [], message: 'ok' })
    ),
    http.get('http://localhost/api/v1/tags', () =>
      HttpResponse.json({ data: [TAG_FIXTURE] })
    ),
    http.get('http://localhost/api/v1/admin/rules/validation', () =>
      HttpResponse.json({ data: [], message: 'ok' })
    ),
    http.get('http://localhost/api/v1/admin/context-presets', () =>
      HttpResponse.json({ data: [], message: 'ok' })
    ),
    http.get('http://localhost/api/v1/admin/support/orphaned-work-items', () =>
      HttpResponse.json({ data: [], message: 'ok' })
    ),
    http.get('http://localhost/api/v1/admin/support/pending-invitations', () =>
      HttpResponse.json({ data: [], message: 'ok' })
    ),
    http.get('http://localhost/api/v1/admin/support/failed-exports', () =>
      HttpResponse.json({ data: [], message: 'ok' })
    ),
    http.get('http://localhost/api/v1/admin/support/config-blocked-work-items', () =>
      HttpResponse.json({ data: [], message: 'ok' })
    )
  );
}

async function renderAdminPage() {
  // Dynamic import to pick up fresh module state
  const { default: AdminPage } = await import('@/app/workspace/[slug]/admin/page');
  render(<AdminPage params={{ slug: 'acme' }} />);
}

// ─── Tab structure ────────────────────────────────────────────────────────────

describe('AdminPage — tab structure', () => {
  it('renders all tab triggers', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /members/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /audit/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /health/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /projects/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /integrations/i })).toBeTruthy();
      expect(screen.getByRole('tab', { name: /tags/i })).toBeTruthy();
    });
  });
});

// ─── Tab 1: Members ───────────────────────────────────────────────────────────

describe('AdminPage — Members tab', () => {
  it('shows skeleton while loading', async () => {
    // Delay response so skeleton is visible
    server.use(
      http.get('http://localhost/api/v1/admin/members', async () => { await new Promise((r) => setTimeout(r, 200)); return HttpResponse.json(ADMIN_MEMBERS_RESPONSE); }),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();

    // Skeleton should be present before data resolves
    expect(document.querySelector('[data-testid="admin-members-skeleton"]')).toBeTruthy();
  });

  it('shows empty state when no members', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () => HttpResponse.json({ data: { items: [], pagination: { cursor: null, has_next: false } }, message: 'ok' })),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();
    await waitFor(() => {
      expect(screen.getByTestId('admin-members-empty')).toBeTruthy();
    });
  });

  it('shows error banner on fetch failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'oops' } }, { status: 500 })
      ),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();
    await waitFor(() => {
      expect(screen.getByTestId('admin-members-error')).toBeTruthy();
    });
  });

  it('renders member table with display_name / email / state', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeTruthy();
      expect(screen.getByText('ada@co.com')).toBeTruthy();
      // State badge visible in new MembersTabEnhanced
      expect(screen.getByText('active')).toBeTruthy();
    });
  });
});

// ─── Tab 2: Audit ─────────────────────────────────────────────────────────────

describe('AdminPage — Audit tab', () => {
  it('renders audit events table', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /audit/i }));

    await waitFor(() => {
      // 'create' appears both in the filter <option> and in the table cell
      expect(screen.getAllByText('create').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Ada')).toBeTruthy();
    });
  });

  it('shows empty state when no events', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () => HttpResponse.json(ADMIN_MEMBERS_RESPONSE)),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /audit/i }));

    await waitFor(() => {
      expect(screen.getByTestId('audit-empty')).toBeTruthy();
    });
  });

  it('action filter triggers re-fetch with action param', async () => {
    let capturedUrl = '';
    server.use(
      http.get('http://localhost/api/v1/admin/members', () => HttpResponse.json(ADMIN_MEMBERS_RESPONSE)),
      http.get('http://localhost/api/v1/admin/audit-events', ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } });
      }),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /audit/i }));

    const actionSelect = await screen.findByTestId('audit-action-filter');
    await userEvent.selectOptions(actionSelect, 'create');

    await waitFor(() => {
      expect(capturedUrl).toContain('action=create');
    });
  });
});

// ─── Tab 3: Health ────────────────────────────────────────────────────────────

describe('AdminPage — Health tab', () => {
  it('shows total_active count', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /health/i }));

    await waitFor(() => {
      expect(screen.getByText(/activos/i)).toBeTruthy();
      expect(screen.getByText('3')).toBeTruthy();
    });
  });

  it('renders a bar segment for each state', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /health/i }));

    await waitFor(() => {
      // draft: 2, in_review: 1 — both should appear
      const segments = document.querySelectorAll('[data-testid^="health-bar-segment-"]');
      expect(segments.length).toBe(2);
    });
  });

  it('bar segments proportions add up (all have width > 0 when count > 0)', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /health/i }));

    await waitFor(() => {
      const segments = document.querySelectorAll('[data-testid^="health-bar-segment-"]');
      segments.forEach((seg) => {
        const style = (seg as HTMLElement).style.width;
        expect(style).not.toBe('0%');
      });
    });
  });

  it('shows empty state for zero-item workspace', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () => HttpResponse.json(ADMIN_MEMBERS_RESPONSE)),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /health/i }));

    await waitFor(() => {
      expect(screen.getByTestId('health-empty')).toBeTruthy();
    });
  });

  it('shows error banner on health fetch failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () => HttpResponse.json(ADMIN_MEMBERS_RESPONSE)),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'fail' } }, { status: 500 })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /health/i }));

    await waitFor(() => {
      expect(screen.getByTestId('health-error')).toBeTruthy();
    });
  });
});

// ─── Tab 4: Projects ──────────────────────────────────────────────────────────

describe('AdminPage — Projects tab', () => {
  it('shows project list', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /projects/i }));

    await waitFor(() => {
      expect(screen.getByText('Alpha')).toBeTruthy();
    });
  });

  it('shows empty state when no projects', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () => HttpResponse.json({ data: { items: [], pagination: { cursor: null, has_next: false } }, message: 'ok' })),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /projects/i }));

    await waitFor(() => {
      expect(screen.getByTestId('projects-empty')).toBeTruthy();
    });
  });

  it('create project success — project appears in list', async () => {
    setupAllHandlers();
    server.use(
      http.post('http://localhost/api/v1/projects', () =>
        HttpResponse.json(
          { data: { id: 'p2', name: 'Beta', description: null, created_at: '2026-04-17T00:00:00Z' } },
          { status: 201 }
        )
      )
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /projects/i }));
    await userEvent.click(await screen.findByRole('button', { name: /nuevo proyecto/i }));

    const nameInput = await screen.findByLabelText(/nombre/i);
    await userEvent.type(nameInput, 'Beta');
    await userEvent.click(screen.getByRole('button', { name: /^crear$/i }));

    await waitFor(() => {
      expect(screen.getByText('Beta')).toBeTruthy();
    });
  });

  it('create project — 409 PROJECT_NAME_TAKEN shows inline field error', async () => {
    setupAllHandlers();
    server.use(
      http.post('http://localhost/api/v1/projects', () =>
        HttpResponse.json(
          {
            error: {
              code: 'PROJECT_NAME_TAKEN',
              message: "project 'Alpha' already exists",
              field: 'name',
            },
          },
          { status: 409 }
        )
      )
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /projects/i }));
    await userEvent.click(await screen.findByRole('button', { name: /nuevo proyecto/i }));

    const nameInput = await screen.findByLabelText(/nombre/i);
    await userEvent.type(nameInput, 'Alpha');
    await userEvent.click(screen.getByRole('button', { name: /^crear$/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
  });

  it('edit project — opens pre-filled modal and PATCH updates list', async () => {
    setupAllHandlers();
    server.use(
      http.patch('http://localhost/api/v1/projects/p1', () =>
        HttpResponse.json({
          data: { id: 'p1', name: 'Alpha Renamed', description: null, created_at: '2026-01-01T00:00:00Z' },
        })
      )
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /projects/i }));
    await userEvent.click(await screen.findByRole('button', { name: /editar alpha/i }));

    const nameInput = await screen.findByDisplayValue('Alpha');
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'Alpha Renamed');
    await userEvent.click(screen.getByRole('button', { name: /^guardar$/i }));

    await waitFor(() => {
      expect(screen.getByText('Alpha Renamed')).toBeTruthy();
    });
  });

  it('delete project — confirmation dialog then removes from list', async () => {
    setupAllHandlers();
    server.use(
      http.delete('http://localhost/api/v1/projects/p1', () =>
        new HttpResponse(null, { status: 204 })
      )
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /projects/i }));
    await userEvent.click(await screen.findByRole('button', { name: /eliminar alpha/i }));

    // Confirmation dialog
    const dialog = await screen.findByRole('dialog');
    const confirmBtn = within(dialog).getByRole('button', { name: /eliminar/i });
    await userEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.queryByText('Alpha')).toBeNull();
    });
  });
});

// ─── Tab 5: Integrations ──────────────────────────────────────────────────────

describe('AdminPage — Integrations tab', () => {
  it('shows integration list with provider and status badge', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /integrations/i }));

    await waitFor(() => {
      expect(screen.getByText('jira')).toBeTruthy();
    });
  });

  it('shows empty state when no integrations', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () => HttpResponse.json({ data: { items: [], pagination: { cursor: null, has_next: false } }, message: 'ok' })),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /integrations/i }));

    await waitFor(() => {
      expect(screen.getByTestId('integrations-empty')).toBeTruthy();
    });
  });

  it('create integration success — appears in list', async () => {
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

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /integrations/i }));
    await userEvent.click(await screen.findByRole('button', { name: /nueva integración/i }));

    const urlInput = await screen.findByLabelText(/url base de jira/i);
    await userEvent.type(urlInput, 'https://test.atlassian.net');

    await userEvent.click(screen.getByRole('button', { name: /^crear$/i }));

    // Two jira entries now
    await waitFor(() => {
      expect(screen.getAllByText('jira').length).toBeGreaterThanOrEqual(2);
    });
  });

  it('delete integration — confirmation then removes from list', async () => {
    setupAllHandlers();
    server.use(
      http.delete('http://localhost/api/v1/integrations/configs/i1', () =>
        new HttpResponse(null, { status: 204 })
      )
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /integrations/i }));
    await userEvent.click(await screen.findByRole('button', { name: /eliminar integración jira/i }));

    const dialog = await screen.findByRole('dialog');
    const confirmBtn = within(dialog).getByRole('button', { name: /eliminar/i });
    await userEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.queryByText('jira')).toBeNull();
    });
  });

  it('shows masked credentials hint in list', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /integrations/i }));

    await waitFor(() => {
      expect(screen.getByTestId('integration-credentials-masked-i1')).toBeTruthy();
    });
  });
});

// ─── Tab 6: Tags ──────────────────────────────────────────────────────────────

describe('AdminPage — Tags tab', () => {
  it('shows tag names', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /tags/i }));

    await waitFor(() => {
      expect(screen.getByText('urgent')).toBeTruthy();
    });
  });

  it('shows empty state when no tags', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () => HttpResponse.json({ data: { items: [], pagination: { cursor: null, has_next: false } }, message: 'ok' })),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] }))
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /tags/i }));

    await waitFor(() => {
      expect(screen.getByTestId('tags-empty')).toBeTruthy();
    });
  });

  it('shows error banner on tags fetch failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () => HttpResponse.json({ data: { items: [], pagination: { cursor: null, has_next: false } }, message: 'ok' })),
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } })
      ),
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({ data: { workspace_id: 'ws1', work_items_by_state: {}, total_active: 0 } })
      ),
      http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/integrations/configs', () => HttpResponse.json({ data: [] })),
      http.get('http://localhost/api/v1/tags', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'oops' } }, { status: 500 })
      )
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /tags/i }));

    await waitFor(() => {
      expect(screen.getByTestId('tags-error')).toBeTruthy();
    });
  });

  it('shows edit icon per tag', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /tags/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /editar etiqueta urgent/i })).toBeTruthy();
    });
  });

  it('clicking edit opens modal pre-filled', async () => {
    setupAllHandlers();
    await renderAdminPage();

    await userEvent.click(await screen.findByRole('tab', { name: /tags/i }));
    await userEvent.click(await screen.findByRole('button', { name: /editar etiqueta urgent/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeTruthy();
      expect(screen.getByRole('textbox', { name: /modals\.tagEdit\.fields\.name/i })).toHaveValue('urgent');
    });
  });

  it('edit tag PATCH updates list without reload', async () => {
    setupAllHandlers();
    server.use(
      http.patch('http://localhost/api/v1/tags/tag1', () =>
        HttpResponse.json({
          data: { id: 'tag1', name: 'blocker', color: '#ff0000', archived: false, created_at: '2026-01-01T00:00:00Z' },
        })
      )
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /tags/i }));
    await userEvent.click(await screen.findByRole('button', { name: /editar etiqueta urgent/i }));

    const nameInput = await screen.findByRole('textbox', { name: /modals\.tagEdit\.fields\.name/i });
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'blocker');
    await userEvent.click(screen.getByRole('button', { name: /^common\.save$/i }));

    await waitFor(() => {
      expect(screen.getByText('blocker')).toBeTruthy();
    });
  });

  it('create tag shows field error when name is taken (409)', async () => {
    setupAllHandlers();
    server.use(
      http.post('http://localhost/api/v1/tags', () =>
        HttpResponse.json(
          {
            error: {
              code: 'TAG_NAME_TAKEN',
              message: "tag 'urgent' already exists in this workspace",
              field: 'name',
            },
          },
          { status: 409 }
        )
      )
    );

    await renderAdminPage();
    await userEvent.click(await screen.findByRole('tab', { name: /tags/i }));
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
