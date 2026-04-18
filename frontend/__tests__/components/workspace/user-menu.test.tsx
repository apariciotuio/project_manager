import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockSetTheme = vi.fn();
let mockTheme: string = 'light';
let mockResolvedTheme: string = 'light';

vi.mock('next-themes', () => ({
  useTheme: () => ({ theme: mockTheme, resolvedTheme: mockResolvedTheme, setTheme: mockSetTheme }),
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
}));

// Cascade stub — unit tests don't exercise the canvas
vi.mock('@/components/system/matrix-entry-cascade/matrix-entry-cascade', () => ({
  MatrixEntryCascade: ({ active }: { active: boolean }) =>
    active ? <div data-testid="cascade-active" /> : null,
}));

// next-intl mock — returns the key so tests assert against translation keys
vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

// Import AFTER mocks
import { UserMenu } from '@/components/workspace/user-menu/user-menu';

beforeEach(() => {
  vi.clearAllMocks();
  mockTheme = 'light';
  mockResolvedTheme = 'light';
  document.cookie = 'tuio-locale=; path=/; max-age=0';
  // Stub reload so the language toggle doesn't nuke jsdom
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...window.location, reload: vi.fn() },
  });
});

async function openMenu() {
  // triggerAria key → 'userMenu.triggerAria'
  const trigger = screen.getByRole('button', { name: /userMenu\.triggerAria/i });
  await userEvent.click(trigger);
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('UserMenu — sidebar identity', () => {
  it('renders the user name next to the avatar', () => {
    render(<UserMenu />);
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
  });

  it('renders the user email next to the avatar', () => {
    render(<UserMenu />);
    expect(screen.getByText('ada@tuio.com')).toBeInTheDocument();
  });

  it('identity block is NOT inside the menu', () => {
    render(<UserMenu />);
    // name is visible without opening the menu
    const name = screen.getByText('Ada Lovelace');
    expect(name.closest('[role="menu"]')).toBeNull();
  });
});

describe('UserMenu — trigger', () => {
  it('renders an avatar button with a translated aria-label key', () => {
    render(<UserMenu />);
    expect(
      screen.getByRole('button', { name: /userMenu\.triggerAria/i }),
    ).toBeInTheDocument();
  });

  it('trigger has aria-haspopup="menu"', () => {
    render(<UserMenu />);
    expect(
      screen.getByRole('button', { name: /userMenu\.triggerAria/i }),
    ).toHaveAttribute('aria-haspopup', 'menu');
  });
});

describe('UserMenu — theme segment (light / dark / matrix)', () => {
  it('renders three radio options with translated labels', async () => {
    render(<UserMenu />);
    await openMenu();
    // Labels come from theme.switcher.light, theme.switcher.dark, theme.redPill.label
    expect(screen.getByRole('radio', { name: /theme\.switcher\.light/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /theme\.switcher\.dark/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /theme\.redPill\.label/i })).toBeInTheDocument();
  });

  it('active theme (light) radio has aria-checked="true"', async () => {
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByRole('radio', { name: /theme\.switcher\.light/i })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  });

  it('active theme (matrix) is reflected on the matrix radio', async () => {
    mockTheme = 'matrix';
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByRole('radio', { name: /theme\.redPill\.label/i })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  });

  it('clicking dark radio calls setTheme("dark") and persists previous', async () => {
    const { setPreviousTheme } = await import('@/lib/theme/trinity');
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /theme\.switcher\.dark/i }));
    expect(mockSetTheme).toHaveBeenCalledWith('dark');
    expect(vi.mocked(setPreviousTheme)).toHaveBeenCalledWith('dark');
  });

  it('clicking matrix radio from light calls setTheme("matrix") and fires cascade', async () => {
    const { setPreviousTheme } = await import('@/lib/theme/trinity');
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /theme\.redPill\.label/i }));
    expect(vi.mocked(setPreviousTheme)).toHaveBeenCalledWith('light');
    expect(mockSetTheme).toHaveBeenCalledWith('matrix');
    expect(screen.getByTestId('cascade-active')).toBeInTheDocument();
  });

  it('clicking light radio from matrix exits without firing cascade', async () => {
    mockTheme = 'matrix';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /theme\.switcher\.light/i }));
    expect(mockSetTheme).toHaveBeenCalledWith('light');
    expect(screen.queryByTestId('cascade-active')).toBeNull();
  });

  it('stores resolved theme (dark) not literal "system" when theme is "system" and switching to matrix', async () => {
    const { setPreviousTheme } = await import('@/lib/theme/trinity');
    mockTheme = 'system';
    mockResolvedTheme = 'dark';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /theme\.redPill\.label/i }));
    // Must store 'dark' (resolved), not 'system'
    expect(vi.mocked(setPreviousTheme)).toHaveBeenCalledWith('dark');
    expect(vi.mocked(setPreviousTheme)).not.toHaveBeenCalledWith('system');
  });

  it('stores resolved theme (light) not literal "system" when resolvedTheme is light', async () => {
    const { setPreviousTheme } = await import('@/lib/theme/trinity');
    mockTheme = 'system';
    mockResolvedTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /theme\.redPill\.label/i }));
    expect(vi.mocked(setPreviousTheme)).toHaveBeenCalledWith('light');
  });

  it('clicking the already-active theme is a no-op', async () => {
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /theme\.switcher\.light/i }));
    expect(mockSetTheme).not.toHaveBeenCalled();
  });
});

describe('UserMenu — language toggle', () => {
  it('defaults to ES when no cookie is set', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByText('ES')).toBeInTheDocument();
  });

  it('clicking the language button toggles ES → EN, writes cookie, reloads', async () => {
    render(<UserMenu />);
    await openMenu();
    const localeBtn = screen.getByRole('button', { name: /userMenu\.localeAriaLabel/i });
    await userEvent.click(localeBtn);
    expect(document.cookie).toContain('tuio-locale=en');
    expect(window.location.reload).toHaveBeenCalledOnce();
  });

  it('reads EN cookie on mount', async () => {
    document.cookie = 'tuio-locale=en; path=/';
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByText('EN')).toBeInTheDocument();
  });
});

describe('UserMenu — no settings placeholder', () => {
  it('does NOT render an "Ajustes próximamente" row', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(screen.queryByText(/ajustes/i)).toBeNull();
    expect(screen.queryByText(/próximamente/i)).toBeNull();
  });
});

describe('UserMenu — Sign out', () => {
  it('renders a sign-out menu item with translated key', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(
      screen.getByRole('menuitem', { name: /userMenu\.signOut/i }),
    ).toBeInTheDocument();
  });

  it('clicking sign-out calls logout()', async () => {
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('menuitem', { name: /userMenu\.signOut/i }));
    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
  });
});
