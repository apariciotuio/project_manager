import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      'bluePill.aria': 'Exit Matrix theme',
      'bluePill.tooltip': 'Exit Matrix',
      'announce.exited': 'Matrix theme deactivated',
    };
    return map[key] ?? key;
  },
}));

const mockSetTheme = vi.fn();
let mockTheme: string | undefined = 'matrix';

vi.mock('next-themes', () => ({
  useTheme: () => ({
    theme: mockTheme,
    setTheme: mockSetTheme,
  }),
}));

vi.mock('@/lib/theme/trinity', () => ({
  setPreviousTheme: vi.fn(),
  getPreviousTheme: () => 'dark',
  isRainEnabled: () => false,
  setRainEnabled: vi.fn(),
}));

vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => null,
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { BluePill } from '@/components/system/blue-pill';

beforeEach(() => {
  vi.clearAllMocks();
  mockTheme = 'matrix';
});

describe('BluePill', () => {
  it('returns null when theme is "light"', () => {
    mockTheme = 'light';
    const { container } = render(<BluePill />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null when theme is "dark"', () => {
    mockTheme = 'dark';
    const { container } = render(<BluePill />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null when theme is "system"', () => {
    mockTheme = 'system';
    const { container } = render(<BluePill />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null when theme is undefined (SSR hydration guard)', () => {
    mockTheme = undefined;
    const { container } = render(<BluePill />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a button when theme is "matrix"', () => {
    mockTheme = 'matrix';
    render(<BluePill />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('has the correct aria-label', () => {
    mockTheme = 'matrix';
    render(<BluePill />);
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Exit Matrix theme');
  });

  it('on click: calls setTheme with getPreviousTheme() result', async () => {
    mockTheme = 'matrix';
    render(<BluePill />);
    await userEvent.click(screen.getByRole('button'));
    expect(mockSetTheme).toHaveBeenCalledWith('dark');
    expect(mockSetTheme).toHaveBeenCalledTimes(1);
  });

  it('button has min-h and min-w for 44px touch target', () => {
    mockTheme = 'matrix';
    render(<BluePill />);
    const btn = screen.getByRole('button');
    expect(btn.className).toMatch(/min-h-\[44px\]/);
    expect(btn.className).toMatch(/min-w-\[44px\]/);
  });
});
