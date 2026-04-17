import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// next-intl mock
vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      'switcher.light': 'Light',
      'switcher.dark': 'Dark',
      'switcher.system': 'System',
      'switcher.ariaLabel': 'Theme selector',
    };
    return map[key] ?? key;
  },
}));

const mockSetTheme = vi.fn();
let mockTheme: string | undefined = 'light';

vi.mock('next-themes', () => ({
  useTheme: () => ({
    theme: mockTheme,
    setTheme: mockSetTheme,
  }),
}));

import { ThemeSwitcher } from '@/components/system/theme-switcher';

beforeEach(() => {
  vi.clearAllMocks();
  mockTheme = 'light';
});

describe('ThemeSwitcher', () => {
  it('renders three options: Light, Dark, System', () => {
    render(<ThemeSwitcher />);
    expect(screen.getByRole('button', { name: /light/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /dark/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /system/i })).toBeInTheDocument();
  });

  it('active option (light) has aria-pressed="true"', () => {
    mockTheme = 'light';
    render(<ThemeSwitcher />);
    expect(screen.getByRole('button', { name: /light/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /dark/i })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: /system/i })).toHaveAttribute('aria-pressed', 'false');
  });

  it('active option (dark) has aria-pressed="true"', () => {
    mockTheme = 'dark';
    render(<ThemeSwitcher />);
    expect(screen.getByRole('button', { name: /light/i })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: /dark/i })).toHaveAttribute('aria-pressed', 'true');
  });

  it('active option (system) has aria-pressed="true"', () => {
    mockTheme = 'system';
    render(<ThemeSwitcher />);
    expect(screen.getByRole('button', { name: /system/i })).toHaveAttribute('aria-pressed', 'true');
  });

  it('click on Light calls setTheme("light")', async () => {
    mockTheme = 'dark';
    render(<ThemeSwitcher />);
    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    expect(mockSetTheme).toHaveBeenCalledWith('light');
    expect(mockSetTheme).toHaveBeenCalledTimes(1);
  });

  it('click on Dark calls setTheme("dark")', async () => {
    mockTheme = 'light';
    render(<ThemeSwitcher />);
    await userEvent.click(screen.getByRole('button', { name: /dark/i }));
    expect(mockSetTheme).toHaveBeenCalledWith('dark');
  });

  it('click on System calls setTheme("system")', async () => {
    render(<ThemeSwitcher />);
    await userEvent.click(screen.getByRole('button', { name: /system/i }));
    expect(mockSetTheme).toHaveBeenCalledWith('system');
  });

  it('when theme is matrix, no option shows as active', () => {
    mockTheme = 'matrix';
    render(<ThemeSwitcher />);
    expect(screen.getByRole('button', { name: /light/i })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: /dark/i })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: /system/i })).toHaveAttribute('aria-pressed', 'false');
  });

  it('when theme is undefined (SSR), no option shows as active', () => {
    mockTheme = undefined;
    render(<ThemeSwitcher />);
    expect(screen.getByRole('button', { name: /light/i })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: /dark/i })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: /system/i })).toHaveAttribute('aria-pressed', 'false');
  });
});
