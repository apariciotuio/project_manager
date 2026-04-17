'use client';

import type { ReactNode } from 'react';
import { WorkspaceSidebar } from '@/components/workspace/workspace-sidebar';

interface WorkspaceLayoutProps {
  children: ReactNode;
  params: { slug: string };
}

export default function WorkspaceLayout({ children, params }: WorkspaceLayoutProps) {
  const { slug } = params;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <WorkspaceSidebar slug={slug} />
      <main className="flex flex-1 flex-col overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
