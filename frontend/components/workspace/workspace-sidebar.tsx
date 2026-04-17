'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { List, Bell, Users, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUnreadCount } from '@/hooks/use-unread-count';
import { MatrixRain } from '@/components/system/matrix-rain';
import { UserMenu } from '@/components/workspace/user-menu/user-menu';
import { NotificationBell } from '@/components/notifications/notification-bell';

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface WorkspaceSidebarProps {
  slug: string;
  workspaceName?: string;
}

export function WorkspaceSidebar({ slug, workspaceName }: WorkspaceSidebarProps) {
  const { count: unreadCount } = useUnreadCount();
  const pathname = usePathname();
  const t = useTranslations('nav');

  const navItems: NavItem[] = [
    { href: `/workspace/${slug}/items`, label: t('items'), icon: List },
    { href: `/workspace/${slug}/inbox`, label: t('inbox'), icon: Bell },
    { href: `/workspace/${slug}/teams`, label: t('teams'), icon: Users },
    { href: `/workspace/${slug}/admin`, label: t('admin'), icon: Settings },
  ];

  return (
    <>
      <MatrixRain />
      <nav
        aria-label={t('workspaceAriaLabel')}
        className="flex h-full w-[280px] shrink-0 flex-col border-r border-border bg-card"
      >
        {/* Workspace name + NotificationBell */}
        <div className="flex h-14 items-center justify-between border-b border-border px-4">
          <span className="truncate text-body font-semibold text-foreground">
            {workspaceName ?? slug}
          </span>
          <NotificationBell slug={slug} />
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
                      aria-label={t('unreadNotifications', { count: unreadCount })}
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

        {/* Announce theme changes */}
        <div role="status" aria-live="polite" className="sr-only" id="theme-announcer" />

        {/* User footer — avatar opens UserMenu */}
        <div className="border-t border-border p-3">
          <UserMenu />
        </div>
      </nav>
    </>
  );
}
