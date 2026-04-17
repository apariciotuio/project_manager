'use client';

import { useEffect, useState } from 'react';
import { apiGet } from '@/lib/api-client';

export interface WorkspaceMember {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  role: string;
}

interface Response {
  data: WorkspaceMember[];
}

interface UseWorkspaceMembersResult {
  members: WorkspaceMember[];
  isLoading: boolean;
  error: Error | null;
}

export function useWorkspaceMembers(): UseWorkspaceMembersResult {
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<Response>('/api/v1/workspaces/members');
        if (!cancelled) setMembers(res.data);
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

  return { members, isLoading, error };
}
