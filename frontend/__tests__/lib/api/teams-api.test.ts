/**
 * EP-08 — teams-api.ts unit tests.
 * Covers all team management endpoints.
 */
import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import {
  listTeams,
  getTeam,
  createTeam,
  updateTeam,
  deleteTeam,
  addMember,
  removeMember,
  updateMemberRole,
  suspendTeam,
  resumeTeam,
} from '@/lib/api/teams-api';
import type { Team } from '@/lib/api/teams-api';

const TEAM: Team = {
  id: 'team-1',
  workspace_id: 'ws-1',
  name: 'Alpha',
  description: 'Alpha team',
  status: 'active',
  can_receive_reviews: true,
  created_at: '2026-01-01T00:00:00Z',
  members: [
    { user_id: 'u-1', display_name: 'Alice', role: 'lead', joined_at: '2026-01-01T00:00:00Z' },
  ],
};

describe('listTeams', () => {
  it('returns array of teams on 200', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ data: [TEAM], message: 'ok' })
      )
    );
    const result = await listTeams();
    expect(result).toHaveLength(1);
    expect(result[0]!.id).toBe('team-1');
    expect(result[0]!.status).toBe('active');
  });

  it('throws on network error', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ error: { code: 'INTERNAL', message: 'server error' } }, { status: 500 })
      )
    );
    await expect(listTeams()).rejects.toBeDefined();
  });
});

describe('getTeam', () => {
  it('returns team DTO on 200', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams/team-1', () =>
        HttpResponse.json({ data: TEAM, message: 'ok' })
      )
    );
    const result = await getTeam('team-1');
    expect(result.id).toBe('team-1');
    expect(result.can_receive_reviews).toBe(true);
    expect(result.members).toHaveLength(1);
  });

  it('throws 404 when team not found', async () => {
    server.use(
      http.get('http://localhost/api/v1/teams/missing', () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'team not found' } }, { status: 404 })
      )
    );
    await expect(getTeam('missing')).rejects.toBeDefined();
  });
});

describe('createTeam', () => {
  it('returns created team on 201', async () => {
    server.use(
      http.post('http://localhost/api/v1/teams', () =>
        HttpResponse.json({ data: TEAM, message: 'created' }, { status: 201 })
      )
    );
    const result = await createTeam({ name: 'Alpha', can_receive_reviews: true });
    expect(result.id).toBe('team-1');
    expect(result.name).toBe('Alpha');
  });

  it('throws 409 TEAM_NAME_CONFLICT on duplicate name', async () => {
    server.use(
      http.post('http://localhost/api/v1/teams', () =>
        HttpResponse.json(
          { error: { code: 'TEAM_NAME_CONFLICT', message: 'team name already exists' } },
          { status: 409 }
        )
      )
    );
    await expect(createTeam({ name: 'Alpha' })).rejects.toMatchObject({ code: 'TEAM_NAME_CONFLICT' });
  });
});

describe('updateTeam', () => {
  it('returns updated team on 200', async () => {
    const updated = { ...TEAM, name: 'Beta' };
    server.use(
      http.patch('http://localhost/api/v1/teams/team-1', () =>
        HttpResponse.json({ data: updated, message: 'updated' })
      )
    );
    const result = await updateTeam('team-1', { name: 'Beta' });
    expect(result.name).toBe('Beta');
  });
});

describe('deleteTeam', () => {
  it('resolves on 200', async () => {
    server.use(
      http.delete('http://localhost/api/v1/teams/team-1', () =>
        HttpResponse.json({ message: 'deleted' })
      )
    );
    await expect(deleteTeam('team-1')).resolves.toBeUndefined();
  });
});

describe('addMember', () => {
  it('resolves on 200', async () => {
    server.use(
      http.post('http://localhost/api/v1/teams/team-1/members', () =>
        HttpResponse.json({ data: TEAM.members[0], message: 'member added' })
      )
    );
    await expect(addMember('team-1', { user_id: 'u-2', role: 'member' })).resolves.toBeDefined();
  });

  it('throws 409 LAST_LEAD_REMOVAL when removing last lead', async () => {
    server.use(
      http.post('http://localhost/api/v1/teams/team-1/members', () =>
        HttpResponse.json(
          { error: { code: 'LAST_LEAD_REMOVAL', message: 'cannot remove last lead' } },
          { status: 409 }
        )
      )
    );
    await expect(addMember('team-1', { user_id: 'u-1', role: 'member' })).rejects.toMatchObject({
      code: 'LAST_LEAD_REMOVAL',
    });
  });
});

describe('removeMember', () => {
  it('resolves on 200', async () => {
    server.use(
      http.delete('http://localhost/api/v1/teams/team-1/members/u-2', () =>
        HttpResponse.json({ message: 'member removed' })
      )
    );
    await expect(removeMember('team-1', 'u-2')).resolves.toBeUndefined();
  });
});

describe('updateMemberRole', () => {
  it('resolves with member on 200', async () => {
    const member = { ...TEAM.members[0], role: 'member' as const };
    server.use(
      http.patch('http://localhost/api/v1/teams/team-1/members/u-1', () =>
        HttpResponse.json({ data: member, message: 'role updated' })
      )
    );
    const result = await updateMemberRole('team-1', 'u-1', 'member');
    expect(result.role).toBe('member');
  });

  it('throws 409 LAST_LEAD_REMOVAL when demoting last lead', async () => {
    server.use(
      http.patch('http://localhost/api/v1/teams/team-1/members/u-1', () =>
        HttpResponse.json(
          { error: { code: 'LAST_LEAD_REMOVAL', message: 'cannot demote last lead' } },
          { status: 409 }
        )
      )
    );
    await expect(updateMemberRole('team-1', 'u-1', 'member')).rejects.toMatchObject({
      code: 'LAST_LEAD_REMOVAL',
    });
  });
});

describe('suspendTeam', () => {
  it('resolves on 200', async () => {
    server.use(
      http.post('http://localhost/api/v1/teams/team-1/suspend', () =>
        HttpResponse.json({ message: 'suspended' })
      )
    );
    await expect(suspendTeam('team-1')).resolves.toBeUndefined();
  });
});

describe('resumeTeam', () => {
  it('resolves on 200', async () => {
    server.use(
      http.post('http://localhost/api/v1/teams/team-1/resume', () =>
        HttpResponse.json({ message: 'resumed' })
      )
    );
    await expect(resumeTeam('team-1')).resolves.toBeUndefined();
  });
});
