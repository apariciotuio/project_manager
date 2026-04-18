'use client';

import type { ReactNode } from 'react';
import { WorkspaceSidebar } from '@/components/workspace/workspace-sidebar';
import { useAuth } from '@/app/providers/auth-provider';

interface WorkspaceLayoutProps {
  children: ReactNode;
  params: { slug: string };
}

/**
 * F-1 auth guard: block render until the session resolves.
 * Middleware already redirects on missing/expired tokens (server-side, no flash).
 * This client-side guard is defense-in-depth: it suppresses workspace UI during
 * the brief window while AuthProvider is bootstrapping from the API, ensuring no
 * flash of authenticated content when navigating client-side to a protected page.
 */
export default function WorkspaceLayout({ children, params }: WorkspaceLayoutProps) {
  const { slug } = params;
  const { isLoading, isAuthenticated } = useAuth();

  // Render nothing while the session check is in-flight or if the user is not
  // authenticated. The middleware + AuthProvider redirect handles the actual
  // navigation; this guard prevents the workspace shell from flickering.
  if (isLoading || !isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <WorkspaceSidebar slug={slug} />
      <main className="flex flex-1 flex-col overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
