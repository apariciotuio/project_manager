/**
 * EP-09 — SortControl component.
 * Tests: renders all sort options, updates URL on change, reflects current URL value.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SortControl, SORT_OPTIONS } from '@/components/work-item/sort-control';

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
    set: vi.fn(),
  }),
}));

beforeEach(() => {
  mockReplace.mockReset();
  mockSearchParams = {};
});

describe('SortControl', () => {
  it('renders a select with all sort options', () => {
    render(<SortControl />);
    const select = screen.getByRole('combobox', { name: /sort/i });
    expect(select).toBeDefined();
    for (const opt of SORT_OPTIONS) {
      expect(screen.getByRole('option', { name: opt.label })).toBeDefined();
    }
  });

  it('defaults to empty (no sort) when no URL param present', () => {
    render(<SortControl />);
    const select = screen.getByRole('combobox', { name: /sort/i }) as HTMLSelectElement;
    expect(select.value).toBe('');
  });

  it('reflects current sort from URL param', () => {
    mockSearchParams = { sort: 'updated_asc' };
    render(<SortControl />);
    const select = screen.getByRole('combobox', { name: /sort/i }) as HTMLSelectElement;
    expect(select.value).toBe('updated_asc');
  });

  it('calls router.replace with ?sort=<value> on change', async () => {
    const user = userEvent.setup();
    render(<SortControl />);
    const select = screen.getByRole('combobox', { name: /sort/i });
    await user.selectOptions(select, 'title_asc');
    expect(mockReplace).toHaveBeenCalledOnce();
    const url = mockReplace.mock.calls[0][0] as string;
    expect(url).toContain('sort=title_asc');
  });

  it('removes sort param when selecting empty option', async () => {
    mockSearchParams = { sort: 'updated_desc' };
    const user = userEvent.setup();
    render(<SortControl />);
    const select = screen.getByRole('combobox', { name: /sort/i });
    await user.selectOptions(select, '');
    expect(mockReplace).toHaveBeenCalledOnce();
    const url = mockReplace.mock.calls[0][0] as string;
    expect(url).not.toContain('sort=');
  });
});
