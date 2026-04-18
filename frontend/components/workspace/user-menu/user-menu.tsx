'use client';

import { useEffect, useState } from 'react';
import { LogOut, Sun, Moon, Pill, Languages } from 'lucide-react';
import { useTheme } from 'next-themes';
import { useTranslations } from 'next-intl';
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

interface ThemeOptionConfig {
  key: ThemeChoice;
  themeKey: 'light' | 'dark' | 'switcher';
  Icon: typeof Sun;
  ringClass: string;
  iconClass: string;
}

const THEME_OPTION_CONFIGS: ReadonlyArray<ThemeOptionConfig> = [
  {
    key: 'light',
    themeKey: 'light',
    Icon: Sun,
    ringClass: 'data-[active=true]:bg-amber-100 data-[active=true]:text-amber-700 data-[active=true]:ring-amber-400/60',
    iconClass: 'text-amber-500',
  },
  {
    key: 'dark',
    themeKey: 'dark',
    Icon: Moon,
    ringClass: 'data-[active=true]:bg-indigo-950/70 data-[active=true]:text-indigo-200 data-[active=true]:ring-indigo-400/60',
    iconClass: 'text-indigo-400',
  },
  {
    key: 'matrix',
    themeKey: 'switcher',
    Icon: Pill,
    ringClass: 'data-[active=true]:bg-emerald-950/70 data-[active=true]:text-emerald-200 data-[active=true]:ring-emerald-400/70',
    iconClass: 'text-emerald-500',
  },
];

/**
 * Resolves the active theme to a concrete ThemeChoice.
 * next-themes can return 'system' when the user has not picked explicitly;
 * in that case we fall back to resolvedTheme (the OS preference result) and
 * then to 'light' as a safe default.
 */
function normalizeTheme(
  theme: string | undefined,
  resolvedTheme: string | undefined,
): ThemeChoice {
  if (theme === 'matrix') return 'matrix';
  if (theme === 'dark') return 'dark';
  if (theme === 'light') return 'light';
  // theme is 'system' or undefined — use the resolved value
  if (resolvedTheme === 'dark') return 'dark';
  return 'light';
}

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
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [cascadeActive, setCascadeActive] = useState(false);
  const [locale, setLocale] = useState<LocaleChoice>('es');

  const t = useTranslations('userMenu');
  const tTheme = useTranslations('theme');

  useEffect(() => {
    setMounted(true);
    setLocale(readLocaleCookie());
  }, []);

  const currentTheme: ThemeChoice | null = mounted
    ? normalizeTheme(theme, resolvedTheme)
    : null;

  function getThemeLabel(key: ThemeChoice): string {
    if (key === 'light') return tTheme('switcher.light');
    if (key === 'dark') return tTheme('switcher.dark');
    return tTheme('redPill.label');
  }

  function handleThemeChange(next: ThemeChoice) {
    if (!mounted || next === currentTheme) return;

    if (next === 'matrix') {
      setPreviousTheme(normalizeTheme(theme, resolvedTheme));
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

  const nextLocale = locale === 'es' ? 'English' : 'Español';
  const currentLocaleLabel = locale === 'es' ? 'Español' : 'English';

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
              aria-label={t('triggerAria')}
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
                aria-label={t('themeAriaGroup')}
                className="flex flex-1 items-center gap-1"
              >
                {THEME_OPTION_CONFIGS.map(({ key, Icon, ringClass, iconClass }) => {
                  const isActive = currentTheme === key;
                  const label = getThemeLabel(key);
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
                aria-label={t('localeAriaLabel', { locale: currentLocaleLabel })}
                title={t('localeTitle', { locale: nextLocale })}
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
              {t('signOut')}
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

