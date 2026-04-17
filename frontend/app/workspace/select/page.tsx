'use client';
// NOTE: GET /api/v1/workspaces/mine is NOT in EP-00 backend scope.
// MSW stubs are used in tests. See backend task for implementation.

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiGet, apiPost } from '@/lib/api-client';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

interface Workspace {
  id: string;
  name: string;
  slug: string;
  role: string;
}

interface WorkspacesResponse {
  data: Workspace[];
}

export default function WorkspaceSelectPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const res = await apiGet<WorkspacesResponse>('/api/v1/workspaces/mine');
        setWorkspaces(res.data);
      } catch {
        // TODO: show HumanError state
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  async function handleSelect(workspace: Workspace) {
    try {
      await apiPost('/api/v1/workspaces/select', { workspace_id: workspace.id });
      // Refresh the JWT so it includes workspace_id — needed for RLS-scoped endpoints
      await apiPost('/api/v1/auth/refresh', {});
    } catch {
      // Redirect anyway — server state is source of truth
    }
    const returnTo = searchParams.get('returnTo');
    // Only honour returnTo if it's scoped to the selected workspace
    if (returnTo && returnTo.startsWith(`/workspace/${workspace.slug}`)) {
      router.replace(returnTo);
    } else {
      router.replace(`/workspace/${workspace.slug}/items`);
    }
  }

  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div
          data-testid="loading-spinner"
          role="status"
          aria-label="Cargando"
          className="flex flex-col gap-2 w-full max-w-sm"
        >
          <Skeleton className="h-12 w-full rounded-md" />
          <Skeleton className="h-12 w-full rounded-md" />
          <Skeleton className="h-12 w-full rounded-md" />
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-h2">Elige un workspace</h1>
      <div className="w-full max-w-sm rounded-xl border border-border bg-card shadow">
        {workspaces.map((ws, idx) => (
          <div key={ws.id}>
            {idx > 0 && <Separator />}
            <Button
              variant="ghost"
              onClick={() => void handleSelect(ws)}
              className="w-full justify-start rounded-none px-4 py-3 text-body-sm first:rounded-t-xl last:rounded-b-xl"
            >
              <span className="font-medium text-foreground">{ws.name}</span>
              <span className="ml-2 text-caption text-muted-foreground">{ws.role}</span>
            </Button>
          </div>
        ))}
      </div>
    </main>
  );
}
