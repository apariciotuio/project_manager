'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiDelete } from '@/lib/api-client';
import type {
  Team,
  TeamsResponse,
  TeamResponse,
  TeamCreateRequest,
  TeamAddMemberRequest,
} from '@/lib/types/api';

interface UseTeamsResult {
  teams: Team[];
  isLoading: boolean;
  error: Error | null;
  createTeam: (req: TeamCreateRequest) => Promise<Team>;
  deleteTeam: (id: string) => Promise<void>;
  addMember: (teamId: string, req: TeamAddMemberRequest) => Promise<void>;
}

export function useTeams(): UseTeamsResult {
  const [teams, setTeams] = useState<Team[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<TeamsResponse>('/api/v1/teams');
        if (!cancelled) setTeams(res.data);
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
    const res = await apiPost<TeamResponse>('/api/v1/teams', req);
    setTeams((prev) => [...prev, res.data]);
    return res.data;
  }, []);

  const deleteTeam = useCallback(async (id: string): Promise<void> => {
    await apiDelete(`/api/v1/teams/${id}`);
    setTeams((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addMember = useCallback(
    async (teamId: string, req: TeamAddMemberRequest): Promise<void> => {
      await apiPost(`/api/v1/teams/${teamId}/members`, req);
    },
    []
  );

  return { teams, isLoading, error, createTeam, deleteTeam, addMember };
}
