import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      'userMenu.trigger': 'Open user menu',
      'userMenu.theme': 'Theme',
      'userMenu.matrixMode': 'Matrix mode',
      'userMenu.rainEffect': 'Rain effect',
      'userMenu.rainRequiresMatrix': 'Requires Matrix mode',
      'userMenu.rainReducedMotion': 'Disabled by your system preference',
      'userMenu.settings': 'Settings',
      'userMenu.settingsComingSoon': 'Coming soon',
      'userMenu.signOut': 'Sign out',
      'switcher.light': 'Light',
      'switcher.dark': 'Dark',
      'switcher.system': 'System',
      'switcher.ariaLabel': 'Theme selector',
      'redPill.aria': 'Enter Matrix theme',
      'redPill.tooltip': 'Enter Matrix',
      'bluePill.aria': 'Exit Matrix theme',
      'bluePill.tooltip': 'Exit Matrix',
      'rain.on': 'Enable rain',
      'rain.off': 'Disable rain',
      'rain.toggle': 'Toggle rain',
    };
    return map[key] ?? key;
  },
}));

const mockSetTheme = vi.fn();
let mockTheme: string = 'light';

vi.mock('next-themes', () => ({
  useTheme: () => ({
    theme: mockTheme,
    setTheme: mockSetTheme,
  }),
}));

const mockLogout = vi.fn();
vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      full_name: 'Ada Lovelace',
      email: 'ada@tuio.com',
      avatar_url: null,
    },
    logout: mockLogout,
  }),
}));

vi.mock('@/lib/theme/trinity', () => ({
  getPreviousTheme: () => 'dark',
  setPreviousTheme: vi.fn(),
  isRainEnabled: () => false,
  setRainEnabled: vi.fn(),
}));

// Radix Tooltip passthrough
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Import AFTER mocks
import { UserMenu } from '@/components/workspace/user-menu/user-menu';

beforeEach(() => {
  vi.clearAllMocks();
  mockTheme = 'light';
});

// Helper: open the menu
async function openMenu() {
  const trigger = screen.getByRole('button', { name: /open user menu/i });
  await userEvent.click(trigger);
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('UserMenu — trigger', () => {
  it('renders an avatar button with correct aria-label', () => {
    render(<UserMenu />);
    expect(
      screen.getByRole('button', { name: /open user menu/i }),
    ).toBeInTheDocument();
  });

  it('trigger has aria-haspopup="menu"', () => {
    render(<UserMenu />);
    expect(
      screen.getByRole('button', { name: /open user menu/i }),
    ).toHaveAttribute('aria-haspopup', 'menu');
  });
});

describe('UserMenu — identity block', () => {
  it('shows the user name in the menu', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
  });

  it('shows the user email in the menu', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByText('ada@tuio.com')).toBeInTheDocument();
  });

  it('identity block is not interactive (no role=menuitem)', async () => {
    render(<UserMenu />);
    await openMenu();
    // The identity block is a label-only div — it must not be a menuitem
    const nameEl = screen.getByText('Ada Lovelace');
    expect(nameEl.closest('[role="menuitem"]')).toBeNull();
  });
});

describe('UserMenu — theme segment', () => {
  it('renders Light, Dark, System buttons inside menu', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByRole('button', { name: /light/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /dark/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /system/i })).toBeInTheDocument();
  });

  it('active theme (light) button has aria-pressed="true"', async () => {
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByRole('button', { name: /light/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('clicking Dark calls setTheme("dark")', async () => {
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('button', { name: /dark/i }));
    expect(mockSetTheme).toHaveBeenCalledWith('dark');
  });
});

describe('UserMenu — Matrix mode toggle', () => {
  it('renders a Matrix mode toggle', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByRole('button', { name: /matrix mode/i })).toBeInTheDocument();
  });

  it('in light theme: Matrix toggle is unchecked (not in matrix)', async () => {
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    const toggle = screen.getByRole('button', { name: /matrix mode/i });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
  });

  it('in matrix theme: Matrix toggle is checked', async () => {
    mockTheme = 'matrix';
    render(<UserMenu />);
    await openMenu();
    const toggle = screen.getByRole('button', { name: /matrix mode/i });
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
  });

  it('clicking Matrix toggle in light mode calls setTheme("matrix") and saves previous theme', async () => {
    const { setPreviousTheme } = await import('@/lib/theme/trinity');
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('button', { name: /matrix mode/i }));
    expect(vi.mocked(setPreviousTheme)).toHaveBeenCalledWith('light');
    expect(mockSetTheme).toHaveBeenCalledWith('matrix');
  });

  it('clicking Matrix toggle in matrix mode reverts to previous theme', async () => {
    mockTheme = 'matrix';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('button', { name: /matrix mode/i }));
    // getPreviousTheme returns 'dark' per mock
    expect(mockSetTheme).toHaveBeenCalledWith('dark');
  });
});

describe('UserMenu — Rain effect toggle', () => {
  it('Rain toggle is disabled when Matrix mode is off', async () => {
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    const rainBtn = screen.getByRole('button', { name: /rain effect/i });
    expect(rainBtn).toBeDisabled();
  });

  it('Rain toggle has aria-disabled when Matrix mode is off', async () => {
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    const rainBtn = screen.getByRole('button', { name: /rain effect/i });
    expect(rainBtn).toHaveAttribute('aria-disabled', 'true');
  });

  it('Rain toggle is enabled when Matrix mode is on', async () => {
    mockTheme = 'matrix';
    render(<UserMenu />);
    await openMenu();
    const rainBtn = screen.getByRole('button', { name: /rain effect/i });
    expect(rainBtn).not.toBeDisabled();
  });
});

describe('UserMenu — Settings placeholder', () => {
  it('renders a Settings item', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByText(/settings/i)).toBeInTheDocument();
  });
});

describe('UserMenu — Sign out', () => {
  it('renders Sign out button', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(
      screen.getByRole('menuitem', { name: /sign out/i }),
    ).toBeInTheDocument();
  });

  it('clicking Sign out calls logout()', async () => {
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('menuitem', { name: /sign out/i }));
    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
  });
});
