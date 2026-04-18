/**
 * AppShell tests — EP-12 Group 1
 * RED: failing tests before implementation
 */
import { render, screen } from '@testing-library/react';
import { AppShell } from '@/components/layout/app-shell';

const NAV_ITEMS = [
  { href: '/inbox', label: 'Inbox', icon: 'inbox' as const },
  { href: '/items', label: 'Items', icon: 'list' as const },
  { href: '/search', label: 'Search', icon: 'search' as const },
];

describe('AppShell', () => {
  describe('mobile viewport (<640px)', () => {
    beforeEach(() => {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: (query: string) => ({
          matches: query.includes('max-width') || query.includes('640'),
          media: query,
          onchange: null,
          addListener: () => {},
          removeListener: () => {},
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
        }),
      });
    });

    it('renders bottom navigation bar', () => {
      render(
        <AppShell navItems={NAV_ITEMS} activeHref="/inbox">
          <div>content</div>
        </AppShell>,
      );
      expect(screen.getByRole('navigation', { name: /bottom navigation/i })).toBeInTheDocument();
    });

    it('renders all nav items with labels', () => {
      render(
        <AppShell navItems={NAV_ITEMS} activeHref="/inbox">
          <div>content</div>
        </AppShell>,
      );
      const bottomNav = screen.getByRole('navigation', { name: /bottom navigation/i });
      const links = bottomNav.querySelectorAll('a');
      const labels = Array.from(links).map((l) => l.textContent ?? '');
      expect(labels.some((l) => /inbox/i.test(l))).toBe(true);
      expect(labels.some((l) => /items/i.test(l))).toBe(true);
      expect(labels.some((l) => /search/i.test(l))).toBe(true);
    });
  });

  describe('desktop viewport (>=1024px)', () => {
    it('renders sidebar navigation', () => {
      render(
        <AppShell navItems={NAV_ITEMS} activeHref="/inbox">
          <div>content</div>
        </AppShell>,
      );
      expect(screen.getByRole('navigation', { name: /sidebar navigation/i })).toBeInTheDocument();
    });
  });

  it('highlights the active nav item', () => {
    render(
      <AppShell navItems={NAV_ITEMS} activeHref="/inbox">
        <div>content</div>
      </AppShell>,
    );
    // Both navs render aria-current — check at least one has it
    const links = screen.getAllByRole('link');
    const inboxLinks = links.filter((l) => /inbox/i.test(l.textContent ?? ''));
    expect(inboxLinks.length).toBeGreaterThan(0);
    expect(inboxLinks.some((l) => l.getAttribute('aria-current') === 'page')).toBe(true);
  });

  it('all nav links are keyboard-reachable (have href)', () => {
    render(
      <AppShell navItems={NAV_ITEMS} activeHref="/inbox">
        <div>content</div>
      </AppShell>,
    );
    const links = screen.getAllByRole('link');
    const hrefs = links.map((l) => l.getAttribute('href'));
    // Each nav item appears in both sidebar + bottom nav; unique hrefs cover all items
    const uniqueHrefs = [...new Set(hrefs)];
    expect(uniqueHrefs).toContain('/inbox');
    expect(uniqueHrefs).toContain('/items');
    expect(uniqueHrefs).toContain('/search');
  });

  it('renders children as main content', () => {
    render(
      <AppShell navItems={NAV_ITEMS} activeHref="/inbox">
        <div data-testid="main-content">hello</div>
      </AppShell>,
    );
    expect(screen.getByTestId('main-content')).toBeInTheDocument();
  });
});
