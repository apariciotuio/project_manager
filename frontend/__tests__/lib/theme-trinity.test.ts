/**
 * Trinity helpers — unit tests (RED first, then GREEN).
 * localStorage is mocked via jsdom's built-in implementation.
 */
import { describe, it, expect, beforeEach } from 'vitest';

// These will fail until trinity.ts is implemented
import {
  getPreviousTheme,
  setPreviousTheme,
  isRainEnabled,
  setRainEnabled,
  type AppTheme,
} from '@/lib/theme/trinity';

const PREVIOUS_KEY = 'trinity:previousTheme';
const RAIN_KEY = 'trinity:rainEnabled';

beforeEach(() => {
  localStorage.clear();
});

describe('getPreviousTheme', () => {
  it('returns "system" when localStorage is empty', () => {
    expect(getPreviousTheme()).toBe('system');
  });

  it('returns "system" when stored value is not in the allowlist (security)', () => {
    localStorage.setItem(PREVIOUS_KEY, '<script>alert(1)</script>');
    expect(getPreviousTheme()).toBe('system');
  });

  it('returns "system" when stored value is an unknown string', () => {
    localStorage.setItem(PREVIOUS_KEY, 'custom-evil-theme');
    expect(getPreviousTheme()).toBe('system');
  });

  it('returns the stored value when it is "dark"', () => {
    localStorage.setItem(PREVIOUS_KEY, 'dark');
    expect(getPreviousTheme()).toBe('dark');
  });

  it('returns the stored value when it is "light"', () => {
    localStorage.setItem(PREVIOUS_KEY, 'light');
    expect(getPreviousTheme()).toBe('light');
  });

  it('returns the stored value when it is "matrix"', () => {
    localStorage.setItem(PREVIOUS_KEY, 'matrix');
    expect(getPreviousTheme()).toBe('matrix');
  });

  it('returns the stored value when it is "system"', () => {
    localStorage.setItem(PREVIOUS_KEY, 'system');
    expect(getPreviousTheme()).toBe('system');
  });
});

describe('setPreviousTheme', () => {
  it('writes "light" to localStorage', () => {
    setPreviousTheme('light');
    expect(localStorage.getItem(PREVIOUS_KEY)).toBe('light');
  });

  it('writes "dark" to localStorage', () => {
    setPreviousTheme('dark');
    expect(localStorage.getItem(PREVIOUS_KEY)).toBe('dark');
  });

  it('writes "matrix" to localStorage', () => {
    setPreviousTheme('matrix');
    expect(localStorage.getItem(PREVIOUS_KEY)).toBe('matrix');
  });

  it('writes "system" to localStorage', () => {
    setPreviousTheme('system');
    expect(localStorage.getItem(PREVIOUS_KEY)).toBe('system');
  });
});

describe('isRainEnabled', () => {
  it('defaults to false when key is absent', () => {
    expect(isRainEnabled()).toBe(false);
  });

  it('returns true only for the exact string "true"', () => {
    localStorage.setItem(RAIN_KEY, 'true');
    expect(isRainEnabled()).toBe(true);
  });

  it('returns false for "false"', () => {
    localStorage.setItem(RAIN_KEY, 'false');
    expect(isRainEnabled()).toBe(false);
  });

  it('returns false for "1" (truthy-string but not "true")', () => {
    localStorage.setItem(RAIN_KEY, '1');
    expect(isRainEnabled()).toBe(false);
  });
});

describe('setRainEnabled', () => {
  it('writes "true" for setRainEnabled(true)', () => {
    setRainEnabled(true);
    expect(localStorage.getItem(RAIN_KEY)).toBe('true');
  });

  it('writes "false" for setRainEnabled(false)', () => {
    setRainEnabled(false);
    expect(localStorage.getItem(RAIN_KEY)).toBe('false');
  });
});

describe('AppTheme type', () => {
  it('AppTheme accepts valid values', () => {
    const themes: AppTheme[] = ['light', 'dark', 'matrix', 'system'];
    expect(themes).toHaveLength(4);
  });
});
