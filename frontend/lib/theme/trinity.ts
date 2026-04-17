/**
 * Trinity — theme persistence helpers.
 *
 * Pure module, no React dependencies. Wraps localStorage with an allowlist
 * guard to prevent class-injection via a poisoned store.
 *
 * Storage keys are namespaced under `trinity:` as a forward reservation
 * for the eventual Trinity endpoint integration (separate epic).
 */

export type AppTheme = 'light' | 'dark' | 'matrix' | 'system';

const PREVIOUS_KEY = 'trinity:previousTheme';
const RAIN_KEY = 'trinity:rainEnabled';

const ALLOWED_THEMES = new Set<string>(['light', 'dark', 'matrix', 'system']);

function isServer(): boolean {
  return typeof window === 'undefined';
}

/**
 * Returns the previously stored non-matrix theme.
 * Falls back to 'system' if no value is stored or the stored value is not
 * in the allowlist (prevents localStorage injection attacks).
 */
export function getPreviousTheme(): AppTheme {
  if (isServer()) return 'system';
  const stored = localStorage.getItem(PREVIOUS_KEY);
  if (stored && ALLOWED_THEMES.has(stored)) return stored as AppTheme;
  return 'system';
}

/**
 * Persists the given theme under the trinity:previousTheme key.
 */
export function setPreviousTheme(theme: AppTheme): void {
  if (isServer()) return;
  localStorage.setItem(PREVIOUS_KEY, theme);
}

/**
 * Returns whether the Matrix rain animation is enabled.
 * Defaults to false when the key is absent.
 */
export function isRainEnabled(): boolean {
  if (isServer()) return false;
  return localStorage.getItem(RAIN_KEY) === 'true';
}

/**
 * Persists the rain-enabled flag.
 */
export function setRainEnabled(enabled: boolean): void {
  if (isServer()) return;
  localStorage.setItem(RAIN_KEY, String(enabled));
}
