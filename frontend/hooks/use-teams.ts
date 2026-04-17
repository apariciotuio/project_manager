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

  const fetchTeams = useCallback(async () => {
    const res = await apiGet<TeamsResponse>('/api/v1/teams');
    setTeams(res.data);
  }, []);

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
    // Update local state from response body (no round-trip)
    const res = await apiPost<TeamResponse>('/api/v1/teams', req);
    setTeams((prev) => [...prev, res.data]);
    return res.data;
  }, []);

  const deleteTeam = useCallback(async (id: string): Promise<void> => {
    // Update local state pessimistically after 2xx
    setIsPendingMutation(true);
    try {
      await apiDelete(`/api/v1/teams/${id}`);
      setTeams((prev) => prev.filter((t) => t.id !== id));
    } finally {
      setIsPendingMutation(false);
    }
  }, []);

  const addMember = useCallback(
    async (teamId: string, req: TeamAddMemberRequest): Promise<void> => {
      // Re-fetch list after 2xx: response body is a membership payload,
      // not a full Team — re-fetch is cheaper than merging partial data.
      setIsPendingMutation(true);
      try {
        await apiPost(`/api/v1/teams/${teamId}/members`, req);
        await fetchTeams();
      } finally {
        setIsPendingMutation(false);
      }
    },
    [fetchTeams]
  );

  return { teams, isLoading, error, isPendingMutation, createTeam, deleteTeam, addMember };
}
