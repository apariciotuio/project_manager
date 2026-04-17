import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockSetTheme = vi.fn();
let mockTheme: string = 'light';

vi.mock('next-themes', () => ({
  useTheme: () => ({ theme: mockTheme, setTheme: mockSetTheme }),
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

// Import AFTER mocks
import { UserMenu } from '@/components/workspace/user-menu/user-menu';

beforeEach(() => {
  vi.clearAllMocks();
  mockTheme = 'light';
  document.cookie = 'tuio-locale=; path=/; max-age=0';
  // Stub reload so the language toggle doesn't nuke jsdom
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...window.location, reload: vi.fn() },
  });
});

async function openMenu() {
  const trigger = screen.getByRole('button', { name: /abrir menú de usuario/i });
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
  it('renders an avatar button with a Spanish aria-label', () => {
    render(<UserMenu />);
    expect(
      screen.getByRole('button', { name: /abrir menú de usuario/i }),
    ).toBeInTheDocument();
  });

  it('trigger has aria-haspopup="menu"', () => {
    render(<UserMenu />);
    expect(
      screen.getByRole('button', { name: /abrir menú de usuario/i }),
    ).toHaveAttribute('aria-haspopup', 'menu');
  });
});

describe('UserMenu — theme segment (Claro / Oscuro / Píldora)', () => {
  it('renders three radio options with icon labels', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByRole('radio', { name: /claro/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /oscuro/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /píldora/i })).toBeInTheDocument();
  });

  it('active theme (light) radio has aria-checked="true"', async () => {
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByRole('radio', { name: /claro/i })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  });

  it('active theme (matrix) is reflected on Píldora', async () => {
    mockTheme = 'matrix';
    render(<UserMenu />);
    await openMenu();
    expect(screen.getByRole('radio', { name: /píldora/i })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  });

  it('clicking Oscuro calls setTheme("dark") and persists previous', async () => {
    const { setPreviousTheme } = await import('@/lib/theme/trinity');
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /oscuro/i }));
    expect(mockSetTheme).toHaveBeenCalledWith('dark');
    expect(vi.mocked(setPreviousTheme)).toHaveBeenCalledWith('dark');
  });

  it('clicking Píldora from light calls setTheme("matrix") and fires cascade', async () => {
    const { setPreviousTheme } = await import('@/lib/theme/trinity');
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /píldora/i }));
    expect(vi.mocked(setPreviousTheme)).toHaveBeenCalledWith('light');
    expect(mockSetTheme).toHaveBeenCalledWith('matrix');
    expect(screen.getByTestId('cascade-active')).toBeInTheDocument();
  });

  it('clicking Claro from matrix exits without firing cascade', async () => {
    mockTheme = 'matrix';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /claro/i }));
    expect(mockSetTheme).toHaveBeenCalledWith('light');
    expect(screen.queryByTestId('cascade-active')).toBeNull();
  });

  it('clicking the already-active theme is a no-op', async () => {
    mockTheme = 'light';
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('radio', { name: /claro/i }));
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
    const localeBtn = screen.getByRole('button', { name: /idioma actual/i });
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
  it('renders a Cerrar sesión menuitem', async () => {
    render(<UserMenu />);
    await openMenu();
    expect(
      screen.getByRole('menuitem', { name: /cerrar sesión/i }),
    ).toBeInTheDocument();
  });

  it('clicking Cerrar sesión calls logout()', async () => {
    render(<UserMenu />);
    await openMenu();
    await userEvent.click(screen.getByRole('menuitem', { name: /cerrar sesión/i }));
    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
  });
});
