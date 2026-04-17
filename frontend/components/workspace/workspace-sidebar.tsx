'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { List, Bell, Users, Settings, LogOut } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { UserAvatar } from '@/components/domain/user-avatar';
import { useAuth } from '@/app/providers/auth-provider';
import { useNotifications } from '@/hooks/use-notifications';

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

function buildNavItems(slug: string): NavItem[] {
  return [
    { href: `/workspace/${slug}/items`, label: 'Elementos', icon: List },
    { href: `/workspace/${slug}/inbox`, label: 'Bandeja de entrada', icon: Bell },
    { href: `/workspace/${slug}/teams`, label: 'Equipos', icon: Users },
    { href: `/workspace/${slug}/admin`, label: 'Administración', icon: Settings },
  ];
}

interface WorkspaceSidebarProps {
  slug: string;
  workspaceName?: string;
}

export function WorkspaceSidebar({ slug, workspaceName }: WorkspaceSidebarProps) {
  const { user, logout } = useAuth();
  const { unreadCount } = useNotifications();
  const pathname = usePathname();
  const navItems = buildNavItems(slug);

  return (
    <nav
      aria-label="Navegación del workspace"
      className="flex h-full w-[280px] shrink-0 flex-col border-r border-border bg-card"
    >
      {/* Workspace name */}
      <div className="flex h-14 items-center border-b border-border px-4">
        <span className="truncate text-body font-semibold text-foreground">
          {workspaceName ?? slug}
        </span>
      </div>

      {/* Nav items */}
      <ul role="list" className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname.startsWith(href);
          const isInbox = href.includes('/inbox');
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-body-sm transition-colors',
                  isActive
                    ? 'bg-accent text-accent-foreground font-medium'
                    : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground',
                )}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                <span className="flex-1">{label}</span>
                {isInbox && unreadCount > 0 && (
                  <span
                    aria-label={`${unreadCount} notificaciones sin leer`}
                    className="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-xs font-medium text-primary-foreground"
                  >
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>

      {/* User footer */}
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-3">
          {user && (
            <UserAvatar
              name={user.full_name}
              avatarUrl={user.avatar_url}
              size="sm"
            />
          )}
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-body-sm font-medium text-foreground">
              {user?.full_name ?? ''}
            </span>
            <span className="truncate text-caption text-muted-foreground">
              {user?.email ?? ''}
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Cerrar sesión"
            onClick={() => void logout()}
            className="shrink-0 text-muted-foreground hover:text-foreground"
          >
            <LogOut className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      </div>
    </nav>
  );
}
