/**
 * EP-09 — QuickFilterChips component tests.
 * i18n mock returns the key — buttons render the i18n key text.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QuickFilterChips } from '@/components/workspace/quick-filter-chips';

const mockReplace = vi.fn();
let mockSearchParams: Record<string, string> = {};

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/workspace/acme/items',
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams[key] ?? null,
    toString: () =>
      Object.entries(mockSearchParams)
        .map(([k, v]) => `${k}=${v}`)
        .join('&'),
  }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

describe('QuickFilterChips', () => {
  beforeEach(() => {
    mockSearchParams = {};
    mockReplace.mockClear();
  });

  it('renders all 5 chips', () => {
    render(<QuickFilterChips />);
    // i18n mock returns key — component renders key text
    expect(screen.getByRole('button', { name: 'all' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'myItems' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'ownedByMe' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'createdByMe' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'pendingMyReview' })).toBeInTheDocument();
  });

  it('"All" chip is active when no mine param in URL', () => {
    render(<QuickFilterChips />);
    expect(screen.getByRole('button', { name: 'all' })).toHaveAttribute('data-active', 'true');
    expect(screen.getByRole('button', { name: 'myItems' })).toHaveAttribute('data-active', 'false');
  });

  it('clicking "My items" sets ?mine=true&mine_type=any in URL', async () => {
    render(<QuickFilterChips />);
    await userEvent.click(screen.getByRole('button', { name: 'myItems' }));
    expect(mockReplace).toHaveBeenCalledOnce();
    const url: string = mockReplace.mock.calls[0][0] as string;
    expect(url).toContain('mine=true');
    expect(url).toContain('mine_type=any');
  });

  it('clicking "Owned by me" sets ?mine=true&mine_type=owner in URL', async () => {
    render(<QuickFilterChips />);
    await userEvent.click(screen.getByRole('button', { name: 'ownedByMe' }));
    const url: string = mockReplace.mock.calls[0][0] as string;
    expect(url).toContain('mine=true');
    expect(url).toContain('mine_type=owner');
  });

  it('clicking "Created by me" sets ?mine=true&mine_type=creator in URL', async () => {
    render(<QuickFilterChips />);
    await userEvent.click(screen.getByRole('button', { name: 'createdByMe' }));
    const url: string = mockReplace.mock.calls[0][0] as string;
    expect(url).toContain('mine=true');
    expect(url).toContain('mine_type=creator');
  });

  it('clicking "Pending my review" sets ?mine=true&mine_type=reviewer in URL', async () => {
    render(<QuickFilterChips />);
    await userEvent.click(screen.getByRole('button', { name: 'pendingMyReview' }));
    const url: string = mockReplace.mock.calls[0][0] as string;
    expect(url).toContain('mine=true');
    expect(url).toContain('mine_type=reviewer');
  });

  it('active chip shown when mine params present in URL', () => {
    mockSearchParams = { mine: 'true', mine_type: 'any' };
    render(<QuickFilterChips />);
    expect(screen.getByRole('button', { name: 'myItems' })).toHaveAttribute('data-active', 'true');
    expect(screen.getByRole('button', { name: 'all' })).toHaveAttribute('data-active', 'false');
  });

  it('clicking the active chip deactivates it — removes mine params', async () => {
    mockSearchParams = { mine: 'true', mine_type: 'owner' };
    render(<QuickFilterChips />);
    await userEvent.click(screen.getByRole('button', { name: 'ownedByMe' }));
    const url: string = mockReplace.mock.calls[0][0] as string;
    expect(url).not.toContain('mine=true');
    expect(url).not.toContain('mine_type=');
  });

  it('only one chip active at a time', () => {
    mockSearchParams = { mine: 'true', mine_type: 'creator' };
    render(<QuickFilterChips />);
    const active = screen
      .getAllByRole('button')
      .filter((b) => b.getAttribute('data-active') === 'true');
    expect(active).toHaveLength(1);
  });

  it('clicking "All" clears mine params from URL', async () => {
    mockSearchParams = { mine: 'true', mine_type: 'reviewer' };
    render(<QuickFilterChips />);
    await userEvent.click(screen.getByRole('button', { name: 'all' }));
    const url: string = mockReplace.mock.calls[0][0] as string;
    expect(url).not.toContain('mine=');
  });

  it('preserves other URL params when switching chips', async () => {
    mockSearchParams = { state: 'draft' };
    render(<QuickFilterChips />);
    await userEvent.click(screen.getByRole('button', { name: 'myItems' }));
    const url: string = mockReplace.mock.calls[0][0] as string;
    expect(url).toContain('state=draft');
    expect(url).toContain('mine=true');
  });
});
