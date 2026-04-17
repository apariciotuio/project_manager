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
    user: { id: 'u1', full_name: 'Ada', workspace_id: 'ws1', workspace_slug: 'acme', email: 'a@b.com', avatar_url: null, is_superadmin: false },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

const mockTeams = [
  { id: 'team1', name: 'Frontend', description: 'UI team', member_count: 3, members: [
    { id: 'm1', user_id: 'u1', full_name: 'Ada Lovelace', email: 'ada@co.com', avatar_url: null },
  ] },
  { id: 'team2', name: 'Backend', description: null, member_count: 1, members: [] },
];

describe('TeamsPage', () => {
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

    const nameInput = await screen.findByPlaceholderText(/nombre del equipo/i);
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
