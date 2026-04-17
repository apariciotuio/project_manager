'use client';

import { useEffect, useState } from 'react';
import { LogOut, Settings } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import { useAuth } from '@/app/providers/auth-provider';
import { UserAvatar } from '@/components/domain/user-avatar';
import { ThemeSwitcher } from '@/components/system/theme-switcher';
import { MatrixEntryCascade } from '@/components/system/matrix-entry-cascade/matrix-entry-cascade';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { getPreviousTheme, setPreviousTheme, isRainEnabled, setRainEnabled } from '@/lib/theme/trinity';

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function UserMenu() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const t = useTranslations();
  const [mounted, setMounted] = useState(false);
  const [rainEnabled, setRainEnabledState] = useState(false);
  const [cascadeActive, setCascadeActive] = useState(false);

  useEffect(() => {
    setMounted(true);
    setRainEnabledState(isRainEnabled());
  }, []);

  const isMatrix = mounted && theme === 'matrix';
  const reducedMotion = mounted && prefersReducedMotion();

  function handleMatrixToggle() {
    if (!mounted) return;
    if (isMatrix) {
      // Exiting matrix — no cascade
      setCascadeActive(false);
      const prev = getPreviousTheme();
      setTheme(prev);
    } else {
      // Entering matrix — fire cascade (guard: previous theme must NOT be matrix)
      setPreviousTheme((theme ?? 'system') as 'light' | 'dark' | 'system');
      setTheme('matrix');
      setCascadeActive(true);
    }
  }

  function handleRainToggle() {
    if (!isMatrix) return;
    const next = !rainEnabled;
    setRainEnabledState(next);
    setRainEnabled(next);
  }

  function handleSignOut() {
    void logout();
  }

  // Rain disabled if: not matrix, or reduced motion
  const rainDisabled = !isMatrix || reducedMotion;
  const rainDisabledReason = reducedMotion
    ? t('userMenu.rainReducedMotion')
    : t('userMenu.rainRequiresMatrix');

  return (
    <>
    <MatrixEntryCascade
      active={cascadeActive}
      onComplete={() => setCascadeActive(false)}
    />
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t('userMenu.trigger')}
          aria-haspopup="menu"
          className={cn(
            'flex items-center rounded-full',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            'min-h-[44px] min-w-[44px] justify-center',
          )}
        >
          {user ? (
            <UserAvatar name={user.full_name} avatarUrl={user.avatar_url} size="sm" />
          ) : (
            <span className="h-8 w-8 rounded-full bg-muted" />
          )}
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        side="top"
        align="start"
        className="w-72"
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        {/* Identity block — non-interactive */}
        <DropdownMenuLabel asChild>
          <div className="flex flex-col gap-0.5 px-2 py-2">
            <span className="text-body-sm font-medium text-foreground">
              {user?.full_name ?? ''}
            </span>
            <span className="text-caption text-muted-foreground">
              {user?.email ?? ''}
            </span>
          </div>
        </DropdownMenuLabel>

        <DropdownMenuSeparator />

        {/* Theme segment */}
        <DropdownMenuGroup>
          <div className="px-2 py-1.5">
            <p className="mb-1.5 text-caption font-medium text-muted-foreground">
              {t('userMenu.theme')}
            </p>
            <ThemeSwitcher className="w-full" />
          </div>
        </DropdownMenuGroup>

        {/* Matrix mode toggle */}
        <DropdownMenuGroup>
          <div className="px-2 py-1">
            <button
              type="button"
              role="button"
              aria-pressed={isMatrix}
              aria-label={t('userMenu.matrixMode')}
              onClick={handleMatrixToggle}
              className={cn(
                'flex w-full items-center justify-between rounded-sm px-1 py-1.5 text-body-sm',
                'hover:bg-accent hover:text-accent-foreground',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                'min-h-[44px]',
              )}
            >
              <span>{t('userMenu.matrixMode')}</span>
              <span
                className={cn(
                  'h-5 w-9 rounded-full border transition-colors',
                  isMatrix
                    ? 'border-primary bg-primary'
                    : 'border-input bg-input',
                )}
                aria-hidden
              >
                <span
                  className={cn(
                    'block h-4 w-4 translate-y-0.5 rounded-full bg-background shadow transition-transform',
                    isMatrix ? 'translate-x-4' : 'translate-x-0.5',
                  )}
                />
              </span>
            </button>
          </div>
        </DropdownMenuGroup>

        {/* Rain effect toggle */}
        <DropdownMenuGroup>
          <div className="px-2 py-1">
            <button
              type="button"
              role="button"
              aria-pressed={rainEnabled && isMatrix}
              aria-label={t('userMenu.rainEffect')}
              aria-disabled={rainDisabled}
              disabled={rainDisabled}
              onClick={handleRainToggle}
              title={rainDisabled ? rainDisabledReason : undefined}
              className={cn(
                'flex w-full items-center justify-between rounded-sm px-1 py-1.5 text-body-sm',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                'min-h-[44px]',
                rainDisabled
                  ? 'cursor-not-allowed opacity-50'
                  : 'hover:bg-accent hover:text-accent-foreground',
              )}
            >
              <span>{t('userMenu.rainEffect')}</span>
              <span
                className={cn(
                  'h-5 w-9 rounded-full border transition-colors',
                  rainEnabled && isMatrix
                    ? 'border-primary bg-primary'
                    : 'border-input bg-input',
                )}
                aria-hidden
              >
                <span
                  className={cn(
                    'block h-4 w-4 translate-y-0.5 rounded-full bg-background shadow transition-transform',
                    rainEnabled && isMatrix ? 'translate-x-4' : 'translate-x-0.5',
                  )}
                />
              </span>
            </button>
          </div>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        {/* Settings placeholder */}
        <DropdownMenuItem
          disabled
          aria-disabled="true"
          className="flex items-center justify-between"
        >
          <span className="flex items-center gap-2">
            <Settings className="h-4 w-4" aria-hidden />
            {t('userMenu.settings')}
          </span>
          <span className="rounded-full bg-muted px-1.5 py-0.5 text-caption text-muted-foreground">
            {t('userMenu.settingsComingSoon')}
          </span>
        </DropdownMenuItem>

        {/* Sign out */}
        <DropdownMenuItem
          role="menuitem"
          onClick={handleSignOut}
          className="flex items-center gap-2 text-destructive focus:text-destructive"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          {t('userMenu.signOut')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    </>
  );
}
