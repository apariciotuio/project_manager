/**
 * Smoke test — RED first, then GREEN after page implementation.
 * Verifies the home page renders with the expected title.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import HomePage from '@/app/page';

// Mock next-intl so the component doesn't need a full provider tree in unit tests
vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => {
    const translations: Record<string, string> = {
      'app.title': 'Work Maturation Platform',
      'theme.toggle': 'Toggle theme',
      'health.ok': 'OK',
      'health.degraded': 'Degraded',
      'health.unknown': 'Unknown',
    };
    return translations[key] ?? key;
  },
}));

// Mock the HealthIndicator to avoid real fetch calls
vi.mock('@/components/health-indicator', () => ({
  HealthIndicator: () => <div data-testid="health-indicator" />,
}));

// Mock the ThemeToggle
vi.mock('@/components/ui/theme-toggle', () => ({
  ThemeToggle: () => <button data-testid="theme-toggle">Toggle theme</button>,
}));

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ status: 'ok' }),
  } as Response);
});

describe('HomePage', () => {
  it('renders the platform title', () => {
    render(<HomePage />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Work Maturation Platform',
    );
  });

  it('renders the theme toggle', () => {
    render(<HomePage />);
    expect(screen.getByTestId('theme-toggle')).toBeInTheDocument();
  });

  it('renders the health indicator', () => {
    render(<HomePage />);
    expect(screen.getByTestId('health-indicator')).toBeInTheDocument();
  });
});
