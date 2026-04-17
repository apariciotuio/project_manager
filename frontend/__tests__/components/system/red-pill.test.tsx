import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      'redPill.aria': 'Enter Matrix theme',
      'redPill.tooltip': 'Enter Matrix',
      'announce.entered': 'Matrix theme activated',
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

vi.mock('@/lib/theme/trinity', () => ({
  setPreviousTheme: vi.fn(),
  getPreviousTheme: () => 'system',
  isRainEnabled: () => false,
  setRainEnabled: vi.fn(),
}));

// Radix Tooltip requires wrapping — mock it as passthrough
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children, asChild }: { children: React.ReactNode; asChild?: boolean }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => null,
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { RedPill } from '@/components/system/red-pill';
import * as trinity from '@/lib/theme/trinity';

let mockSetPreviousTheme: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  mockSetPreviousTheme = vi.mocked(trinity.setPreviousTheme);
});

describe('RedPill', () => {
  it('returns null when theme is "matrix"', () => {
    mockTheme = 'matrix';
    const { container } = render(<RedPill />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a button when theme is "light"', () => {
    mockTheme = 'light';
    render(<RedPill />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('renders a button when theme is "dark"', () => {
    mockTheme = 'dark';
    render(<RedPill />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('renders a button when theme is "system"', () => {
    mockTheme = 'system';
    render(<RedPill />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('does not render when theme is undefined (SSR hydration guard)', () => {
    mockTheme = undefined;
    const { container } = render(<RedPill />);
    expect(container.firstChild).toBeNull();
  });

  it('has the correct aria-label', () => {
    mockTheme = 'light';
    render(<RedPill />);
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Enter Matrix theme');
  });

  it('on click: calls setPreviousTheme with current theme before switching', async () => {
    mockTheme = 'dark';
    render(<RedPill />);
    await userEvent.click(screen.getByRole('button'));
    expect(mockSetPreviousTheme).toHaveBeenCalledWith('dark');
    expect(mockSetTheme).toHaveBeenCalledWith('matrix');
  });

  it('on click: setPreviousTheme is called before setTheme', async () => {
    const callOrder: string[] = [];
    mockSetPreviousTheme.mockImplementation(() => callOrder.push('setPrevious'));
    mockSetTheme.mockImplementation(() => callOrder.push('setTheme'));

    mockTheme = 'light';
    render(<RedPill />);
    await userEvent.click(screen.getByRole('button'));

    expect(callOrder).toEqual(['setPrevious', 'setTheme']);
  });

  it('button has min-h and min-w for 44px touch target', () => {
    mockTheme = 'light';
    render(<RedPill />);
    const btn = screen.getByRole('button');
    // Verify via class — Tailwind min-h-[44px] / min-w-[44px]
    expect(btn.className).toMatch(/min-h-\[44px\]/);
    expect(btn.className).toMatch(/min-w-\[44px\]/);
  });
});
