import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ slug: 'acme' }),
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: { id: 'u1', full_name: 'Ada', workspace_id: 'ws1', workspace_slug: 'acme', email: 'a@b.com', avatar_url: null, is_superadmin: false },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

// EP-08 API shape: TeamMember has display_name + role + joined_at
const mockTeams = [
  {
    id: 'team1', name: 'Frontend', description: 'UI team',
    workspace_id: 'ws1', status: 'active', can_receive_reviews: false, created_at: '2026-01-01T00:00:00Z',
    members: [
      { user_id: 'u1', display_name: 'Ada Lovelace', role: 'lead', joined_at: '2026-01-01T00:00:00Z' },
      { user_id: 'u2', display_name: 'Bob', role: 'member', joined_at: '2026-01-02T00:00:00Z' },
      { user_id: 'u3', display_name: 'Carol', role: 'member', joined_at: '2026-01-03T00:00:00Z' },
    ],
  },
  {
    id: 'team2', name: 'Backend', description: null,
    workspace_id: 'ws1', status: 'active', can_receive_reviews: true, created_at: '2026-01-01T00:00:00Z',
    members: [
      { user_id: 'u4', display_name: 'Dave', role: 'lead', joined_at: '2026-01-01T00:00:00Z' },
    ],
  },
];

describe('TeamsPage', () => {
  it('shows skeleton while loading', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', async () => {
        await new Promise(() => {});
        return HttpResponse.json({ data: [] });
      }),
    );

    const { default: TeamsPage } = await import('@/app/workspace/[slug]/teams/page');
    render(<TeamsPage params={{ slug: 'acme' }} />);

    expect(document.querySelector('[data-testid="teams-skeleton"]')).toBeTruthy();
  });

  it('shows empty state when no teams exist', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () => HttpResponse.json({ data: [] })),
    );

    const { default: TeamsPage } = await import('@/app/workspace/[slug]/teams/page');
    render(<TeamsPage params={{ slug: 'acme' }} />);

    expect(await screen.findByTestId('teams-empty')).toBeTruthy();
  });

  it('shows error state on 5xx', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'oops' } }, { status: 500 }),
      ),
    );

    const { default: TeamsPage } = await import('@/app/workspace/[slug]/teams/page');
    render(<TeamsPage params={{ slug: 'acme' }} />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
  });

  it('renders team names', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () => HttpResponse.json({ data: mockTeams }))
    );

    const { default: TeamsPage } = await import('@/app/workspace/[slug]/teams/page');
    render(<TeamsPage params={{ slug: 'acme' }} />);

    expect(await screen.findByText('Frontend')).toBeTruthy();
    expect(await screen.findByText('Backend')).toBeTruthy();
  });

  it('shows member count', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () => HttpResponse.json({ data: mockTeams }))
    );

    const { default: TeamsPage } = await import('@/app/workspace/[slug]/teams/page');
    render(<TeamsPage params={{ slug: 'acme' }} />);

    await waitFor(() => {
      expect(screen.getByText(/3 miembro/i)).toBeTruthy();
    });
  });

  it('opens create team dialog when button is clicked', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () => HttpResponse.json({ data: mockTeams }))
    );

    const { default: TeamsPage } = await import('@/app/workspace/[slug]/teams/page');
    render(<TeamsPage params={{ slug: 'acme' }} />);

    await screen.findByText('Frontend');
    const btn = screen.getByRole('button', { name: /crear equipo/i });
    await userEvent.click(btn);

    expect(await screen.findByRole('dialog')).toBeTruthy();
  });

  it('creates a new team via the dialog', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () => HttpResponse.json({ data: [] })),
      http.post('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ data: { id: 'team3', name: 'Design', description: null, member_count: 0, members: [] } })
      )
    );

    const { default: TeamsPage } = await import('@/app/workspace/[slug]/teams/page');
    render(<TeamsPage params={{ slug: 'acme' }} />);

    await waitFor(() => expect(screen.queryByText(/cargando/i)).toBeNull());

    const btn = screen.getByRole('button', { name: /crear equipo/i });
    await userEvent.click(btn);

    const nameInput = await screen.findByPlaceholderText(/workspace\.teams\.createDialog\.namePlaceholder/i);
    await userEvent.type(nameInput, 'Design');

    const submit = screen.getByRole('button', { name: /crear$/i });
    await userEvent.click(submit);

    await waitFor(() => {
      expect(screen.getByText('Design')).toBeTruthy();
    });
  });

  it('expands team to show members on click', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () => HttpResponse.json({ data: mockTeams }))
    );

    const { default: TeamsPage } = await import('@/app/workspace/[slug]/teams/page');
    render(<TeamsPage params={{ slug: 'acme' }} />);

    await screen.findByText('Frontend');
    const teamCard = screen.getByRole('button', { name: /frontend/i });
    await userEvent.click(teamCard);

    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeTruthy();
    });
  });
});
