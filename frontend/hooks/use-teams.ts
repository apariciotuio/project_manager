'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  listTeams as apiListTeams,
  createTeam as apiCreateTeam,
  deleteTeam as apiDeleteTeam,
  addMember as apiAddMember,
} from '@/lib/api/teams-api';
import type { Team as ApiTeam } from '@/lib/api/teams-api';
import type {
  Team,
  TeamCreateRequest,
  TeamAddMemberRequest,
} from '@/lib/types/api';

// Map EP-08 API Team to the legacy Team shape used by existing UI.
// member_count is derived from the members array length.
function toTeam(t: ApiTeam): Team {
  return {
    id: t.id,
    name: t.name,
    description: t.description,
    member_count: t.members.length,
    members: t.members.map((m) => ({
      id: m.user_id,
      user_id: m.user_id,
      full_name: m.display_name,
      email: '',
      avatar_url: null,
    })),
  };
}

interface UseTeamsResult {
  teams: Team[];
  isLoading: boolean;
  error: Error | null;
  isPendingMutation: boolean;
  createTeam: (req: TeamCreateRequest) => Promise<Team>;
  deleteTeam: (id: string) => Promise<void>;
  addMember: (teamId: string, req: TeamAddMemberRequest) => Promise<void>;
}

export function useTeams(): UseTeamsResult {
  const [teams, setTeams] = useState<Team[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [isPendingMutation, setIsPendingMutation] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const raw = await apiListTeams();
        if (!cancelled) setTeams(raw.map(toTeam));
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const createTeam = useCallback(async (req: TeamCreateRequest): Promise<Team> => {
    const raw = await apiCreateTeam({ name: req.name, description: req.description });
    const team = toTeam(raw);
    setTeams((prev) => [...prev, team]);
    return team;
  }, []);

  const deleteTeam = useCallback(async (id: string): Promise<void> => {
    setIsPendingMutation(true);
    try {
      await apiDeleteTeam(id);
      setTeams((prev) => prev.filter((t) => t.id !== id));
    } finally {
      setIsPendingMutation(false);
    }
  }, []);

  const addMember = useCallback(
    async (teamId: string, req: TeamAddMemberRequest): Promise<void> => {
      setIsPendingMutation(true);
      try {
        const member = await apiAddMember(teamId, { user_id: req.user_id });
        setTeams((prev) =>
          prev.map((t) =>
            t.id === teamId
              ? {
                  ...t,
                  member_count: t.member_count + 1,
                  members: [
                    ...t.members,
                    {
                      id: member.user_id,
                      user_id: member.user_id,
                      full_name: member.display_name,
                      email: '',
                      avatar_url: null,
                    },
                  ],
                }
              : t,
          ),
        );
      } finally {
        setIsPendingMutation(false);
      }
    },
    []
  );

  return { teams, isLoading, error, isPendingMutation, createTeam, deleteTeam, addMember };
}
