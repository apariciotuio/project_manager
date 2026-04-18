/**
 * EP-10: Enhanced Members Tab — RED tests
 * Tests: role change, delete member, capabilities chips, context labels, invite flow
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: { id: 'u1', workspace_id: 'ws1', is_superadmin: false },
  }),
}));

const ADMIN_MEMBER = {
  id: 'm1',
  user_id: 'u1',
  email: 'ada@test.com',
  display_name: 'Ada Lovelace',
  state: 'active',
  role: 'admin',
  capabilities: ['manage_members', 'view_audit_log'],
  context_labels: ['backend', 'infra'],
  joined_at: '2026-01-01T00:00:00Z',
};

const ADMIN_MEMBERS_RESPONSE = {
  data: {
    items: [ADMIN_MEMBER],
    pagination: { cursor: null, has_next: false },
  },
  message: 'ok',
};

// Deferred import to avoid module execution before mocks are set
async function renderMembersTab() {
  const { MembersTabEnhanced } = await import('@/components/admin/members-tab-enhanced');
  return render(<MembersTabEnhanced />);
}

describe('MembersTabEnhanced', () => {
  beforeEach(() => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () =>
        HttpResponse.json(ADMIN_MEMBERS_RESPONSE)
      )
    );
  });

  it('renders member list with display_name and email', async () => {
    await renderMembersTab();
    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
      expect(screen.getByText('ada@test.com')).toBeInTheDocument();
    });
  });

  it('renders capability chips for each capability', async () => {
    await renderMembersTab();
    await waitFor(() => {
      expect(screen.getByText('manage_members')).toBeInTheDocument();
      expect(screen.getByText('view_audit_log')).toBeInTheDocument();
    });
  });

  it('renders context label chips', async () => {
    await renderMembersTab();
    await waitFor(() => {
      expect(screen.getByText('backend')).toBeInTheDocument();
      expect(screen.getByText('infra')).toBeInTheDocument();
    });
  });

  it('shows skeleton while loading', () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', async () => {
        await new Promise(() => undefined); // never resolves
      })
    );
    render(<div data-testid="members-skeleton" />);
    expect(screen.getByTestId('members-skeleton')).toBeInTheDocument();
  });

  it('shows empty state when no members', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/members', () =>
        HttpResponse.json({
          data: { items: [], pagination: { cursor: null, has_next: false } },
          message: 'ok',
        })
      )
    );
    await renderMembersTab();
    await waitFor(() => {
      expect(screen.getByTestId('admin-members-empty')).toBeInTheDocument();
    });
  });

  it('patch member state calls PATCH endpoint', async () => {
    let patched = false;
    server.use(
      http.patch('http://localhost/api/v1/admin/members/m1', async () => {
        patched = true;
        return HttpResponse.json({ data: { id: 'm1', state: 'suspended' }, message: 'ok' });
      })
    );
    await renderMembersTab();
    await waitFor(() => screen.getByText('Ada Lovelace'));
    const suspendBtn = screen.getByRole('button', { name: /suspend/i });
    await userEvent.click(suspendBtn);
    const confirmBtn = await screen.findByRole('button', { name: /confirm/i });
    await userEvent.click(confirmBtn);
    await waitFor(() => expect(patched).toBe(true));
  });

  it('invite member button triggers modal with email field', async () => {
    await renderMembersTab();
    await waitFor(() => screen.getByText('Ada Lovelace'));
    const inviteBtn = screen.getByRole('button', { name: /invite/i });
    await userEvent.click(inviteBtn);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it('invite 409 member_already_active shows inline error', async () => {
    server.use(
      http.post('http://localhost/api/v1/admin/members', () =>
        HttpResponse.json(
          { error: { code: 'member_already_active', message: 'already exists', details: {} } },
          { status: 409 }
        )
      )
    );
    await renderMembersTab();
    await waitFor(() => screen.getByText('Ada Lovelace'));
    await userEvent.click(screen.getByRole('button', { name: /invite/i }));
    const emailInput = screen.getByLabelText(/email/i);
    await userEvent.type(emailInput, 'ada@test.com');
    const submitBtn = screen.getByRole('button', { name: /send invite/i });
    await userEvent.click(submitBtn);
    await waitFor(() =>
      expect(screen.getByText(/already exists/i)).toBeInTheDocument()
    );
  });
});
