import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { useTeams } from '@/hooks/use-teams';

const mockTeams = [
  {
    id: 'team1',
    name: 'Frontend',
    description: 'Frontend team',
    member_count: 3,
    members: [],
  },
  {
    id: 'team2',
    name: 'Backend',
    description: null,
    member_count: 2,
    members: [],
  },
];

describe('useTeams', () => {
  it('returns teams on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ data: mockTeams })
      )
    );

    const { result } = renderHook(() => useTeams());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.teams).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });

  it('sets error on API failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'fail' } }, { status: 500 })
      )
    );

    const { result } = renderHook(() => useTeams());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBeInstanceOf(Error);
  });

  it('createTeam appends to list', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ data: mockTeams })
      ),
      http.post('http://localhost/api/v1/teams', () =>
        HttpResponse.json({
          data: { id: 'team3', name: 'QA', description: null, member_count: 0, members: [] },
        })
      )
    );

    const { result } = renderHook(() => useTeams());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.createTeam({ name: 'QA' });
    });

    expect(result.current.teams).toHaveLength(3);
    expect(result.current.teams[2]!.name).toBe('QA');
  });

  it('deleteTeam removes from list', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ data: mockTeams })
      ),
      http.delete('http://localhost/api/v1/teams/team1', () =>
        new HttpResponse(null, { status: 204 })
      )
    );

    const { result } = renderHook(() => useTeams());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.deleteTeam('team1');
    });

    expect(result.current.teams).toHaveLength(1);
    expect(result.current.teams[0]!.id).toBe('team2');
  });

  it('addMember re-fetches team and updates member list in state', async () => {
    const teamWithMember = {
      ...mockTeams[0],
      member_count: 1,
      members: [{ id: 'm1', user_id: 'u1', full_name: 'Alice', email: 'alice@co.com', avatar_url: null }],
    };
    let fetchCount = 0;
    server.use(
      http.get('http://localhost/api/v1/teams', () => {
        fetchCount++;
        if (fetchCount === 1) return HttpResponse.json({ data: mockTeams });
        return HttpResponse.json({
          data: [teamWithMember, mockTeams[1]],
        });
      }),
      http.post('http://localhost/api/v1/teams/team1/members', () =>
        HttpResponse.json(
          { data: { id: 'm1', team_id: 'team1', user_id: 'u1', role: 'member', joined_at: '2026-01-01T00:00:00Z', removed_at: null } },
          { status: 201 }
        )
      )
    );

    const { result } = renderHook(() => useTeams());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // Initially no members
    expect(result.current.teams[0]!.members).toHaveLength(0);

    await act(async () => {
      await result.current.addMember('team1', { user_id: 'u1' });
    });

    // After addMember, list re-fetched — team1 now has a member
    await waitFor(() => {
      expect(result.current.teams[0]!.members).toHaveLength(1);
    });
    expect(result.current.teams[0]!.members[0]!.full_name).toBe('Alice');
  });

  it('addMember does not update state when backend returns error', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ data: mockTeams })
      ),
      http.post('http://localhost/api/v1/teams/team1/members', () =>
        HttpResponse.json(
          { error: { code: 'TEAM_MEMBER_ALREADY_EXISTS', message: 'already member', field: 'user_id' } },
          { status: 409 }
        )
      )
    );

    const { result } = renderHook(() => useTeams());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await expect(
      act(async () => {
        await result.current.addMember('team1', { user_id: 'u1' });
      })
    ).rejects.toBeInstanceOf(Error);

    expect(result.current.teams[0]!.members).toHaveLength(0);
  });
});
