'use client';

import { useAuth } from '@/app/providers/auth-provider';
import { LogoutButton } from '@/components/auth/logout-button';
import { UserAvatar } from '@/components/domain/user-avatar';
import { Separator } from '@/components/ui/separator';

interface WorkspaceSlugPageProps {
  params: { slug: string };
}

export default function WorkspaceSlugPage({
  params: { slug },
}: WorkspaceSlugPageProps) {
  const { user } = useAuth();

  return (
    <div className="min-h-screen">
      <nav className="flex items-center justify-between border-b border-border bg-card px-6 py-3">
        <span className="text-body font-semibold text-foreground">{slug}</span>
        <div className="flex items-center gap-3">
          {user && (
            <>
              <UserAvatar
                name={user.full_name}
                avatarUrl={user.avatar_url}
                size="sm"
              />
              <span className="text-body-sm text-foreground">{user.full_name}</span>
              <Separator orientation="vertical" className="h-5" />
            </>
          )}
          <LogoutButton />
        </div>
      </nav>
      <main className="p-6">{/* workspace content */}</main>
    </div>
  );
}
