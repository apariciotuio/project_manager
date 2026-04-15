'use client';

import { useTheme as useNextTheme } from 'next-themes';

type Theme = 'light' | 'dark' | 'system';

/**
 * Thin wrapper around next-themes.
 * Provides a stable API for the rest of the codebase.
 */
export function useTheme(): {
  theme: Theme;
  resolvedTheme: 'light' | 'dark' | undefined;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
} {
  const { theme, resolvedTheme, setTheme } = useNextTheme();

  function toggleTheme() {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  }

  return {
    theme: (theme as Theme) ?? 'system',
    resolvedTheme: resolvedTheme as 'light' | 'dark' | undefined,
    setTheme: (t: Theme) => setTheme(t),
    toggleTheme,
  };
}
