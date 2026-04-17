'use client';

import { useEffect, useState } from 'react';
import { LogOut, Sun, Moon, Pill, Languages } from 'lucide-react';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import { useAuth } from '@/app/providers/auth-provider';
import { UserAvatar } from '@/components/domain/user-avatar';
import { MatrixEntryCascade } from '@/components/system/matrix-entry-cascade/matrix-entry-cascade';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { getPreviousTheme, setPreviousTheme } from '@/lib/theme/trinity';

type ThemeChoice = 'light' | 'dark' | 'matrix';
type LocaleChoice = 'es' | 'en';

const LOCALE_COOKIE = 'tuio-locale';

interface ThemeOption {
  key: ThemeChoice;
  label: string;
  Icon: typeof Sun;
  ringClass: string;
  iconClass: string;
}

const THEME_OPTIONS: ReadonlyArray<ThemeOption> = [
  {
    key: 'light',
    label: 'Claro',
    Icon: Sun,
    ringClass: 'data-[active=true]:bg-amber-100 data-[active=true]:text-amber-700 data-[active=true]:ring-amber-400/60',
    iconClass: 'text-amber-500',
  },
  {
    key: 'dark',
    label: 'Oscuro',
    Icon: Moon,
    ringClass: 'data-[active=true]:bg-indigo-950/70 data-[active=true]:text-indigo-200 data-[active=true]:ring-indigo-400/60',
    iconClass: 'text-indigo-400',
  },
  {
    key: 'matrix',
    label: 'Píldora',
    Icon: Pill,
    ringClass: 'data-[active=true]:bg-emerald-950/70 data-[active=true]:text-emerald-200 data-[active=true]:ring-emerald-400/70',
    iconClass: 'text-emerald-500',
  },
];

function readLocaleCookie(): LocaleChoice {
  if (typeof document === 'undefined') return 'es';
  const match = document.cookie.match(/(?:^|;\s*)tuio-locale=([^;]+)/);
  const value = match?.[1];
  return value === 'en' ? 'en' : 'es';
}

function writeLocaleCookie(locale: LocaleChoice): void {
  // 1 year, site-wide, accessible server-side (layout.tsx reads it)
  const maxAge = 60 * 60 * 24 * 365;
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=${maxAge}; samesite=lax`;
}

export function UserMenu() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [cascadeActive, setCascadeActive] = useState(false);
  const [locale, setLocale] = useState<LocaleChoice>('es');

  useEffect(() => {
    setMounted(true);
    setLocale(readLocaleCookie());
  }, []);

  const currentTheme: ThemeChoice | null = mounted
    ? theme === 'matrix'
      ? 'matrix'
      : theme === 'dark'
        ? 'dark'
        : 'light'
    : null;

  function handleThemeChange(next: ThemeChoice) {
    if (!mounted || next === currentTheme) return;

    if (next === 'matrix') {
      setPreviousTheme((theme ?? 'light') as 'light' | 'dark');
      setTheme('matrix');
      setCascadeActive(true);
      return;
    }

    setCascadeActive(false);
    setTheme(next);
    setPreviousTheme(next);
  }

  function handleLocaleToggle() {
    const next: LocaleChoice = locale === 'es' ? 'en' : 'es';
    writeLocaleCookie(next);
    setLocale(next);
    // Reload so the server-rendered messages reflect the new locale.
    window.location.reload();
  }

  return (
    <>
      <MatrixEntryCascade
        active={cascadeActive}
        onComplete={() => setCascadeActive(false)}
      />
      <div className="flex items-center gap-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="Abrir menú de usuario"
              aria-haspopup="menu"
              className={cn(
                'flex shrink-0 items-center rounded-full',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
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
            className="w-64"
            onCloseAutoFocus={(e) => e.preventDefault()}
          >
            {/* Theme + language — compact icon row */}
            <div className="flex items-center gap-1 px-1.5 py-1.5">
              <div
                role="radiogroup"
                aria-label="Tema"
                className="flex flex-1 items-center gap-1"
              >
                {THEME_OPTIONS.map(({ key, label, Icon, ringClass, iconClass }) => {
                  const isActive = currentTheme === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      role="radio"
                      aria-checked={isActive}
                      aria-label={label}
                      title={label}
                      data-active={isActive}
                      onClick={() => handleThemeChange(key)}
                      className={cn(
                        'flex h-9 w-9 items-center justify-center rounded-md transition-all',
                        'text-muted-foreground hover:bg-accent hover:text-foreground',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
                        'data-[active=true]:ring-2',
                        ringClass,
                      )}
                    >
                      <Icon className={cn('h-4 w-4', isActive && iconClass)} aria-hidden />
                    </button>
                  );
                })}
              </div>

              <button
                type="button"
                aria-label={`Idioma actual: ${locale === 'es' ? 'Español' : 'English'}. Cambiar.`}
                title={locale === 'es' ? 'Cambiar a English' : 'Cambiar a Español'}
                onClick={handleLocaleToggle}
                className={cn(
                  'ml-1 flex h-9 items-center gap-1.5 rounded-md px-2 transition-colors',
                  'text-muted-foreground hover:bg-accent hover:text-foreground',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
                )}
              >
                <Languages className="h-4 w-4 text-sky-500" aria-hidden />
                <span className="text-caption font-semibold">{locale.toUpperCase()}</span>
              </button>
            </div>

            <DropdownMenuSeparator />

            <DropdownMenuItem
              onClick={() => void logout()}
              className="flex items-center gap-2 text-destructive focus:text-destructive"
            >
              <LogOut className="h-4 w-4" aria-hidden />
              Cerrar sesión
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Identity block — visible outside the menu, to the right of the avatar */}
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-body-sm font-medium text-foreground">
            {user?.full_name ?? ''}
          </span>
          <span className="truncate text-caption text-muted-foreground">
            {user?.email ?? ''}
          </span>
        </div>
      </div>
    </>
  );
}

export { getPreviousTheme };
