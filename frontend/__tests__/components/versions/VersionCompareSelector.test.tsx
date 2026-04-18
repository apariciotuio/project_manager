/**
 * EP-07 Group 3b — VersionCompareSelector component.
 *
 * Tests:
 * - two dropdowns rendered (from / to)
 * - from > to shows inline error / disables invalid selection
 * - swap button swaps from and to values
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import type { WorkItemVersion } from '@/lib/types/versions';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const versions: WorkItemVersion[] = [
  {
    id: 'ver-1',
    work_item_id: 'wi-1',
    version_number: 1,
    trigger: 'content_edit',
    actor_type: 'human',
    actor_id: 'user-1',
    commit_message: 'First',
    archived: false,
    created_at: '2026-04-17T10:00:00Z',
  },
  {
    id: 'ver-2',
    work_item_id: 'wi-1',
    version_number: 2,
    trigger: 'content_edit',
    actor_type: 'human',
    actor_id: 'user-1',
    commit_message: 'Second',
    archived: false,
    created_at: '2026-04-17T11:00:00Z',
  },
  {
    id: 'ver-3',
    work_item_id: 'wi-1',
    version_number: 3,
    trigger: 'state_transition',
    actor_type: 'system',
    actor_id: null,
    commit_message: null,
    archived: false,
    created_at: '2026-04-17T12:00:00Z',
  },
];

async function renderSelector(
  fromVersion = 1,
  toVersion = 3,
  onChange = vi.fn(),
) {
  const { VersionCompareSelector } = await import(
    '@/components/versions/VersionCompareSelector'
  );
  return render(
    <VersionCompareSelector
      workItemId="wi-1"
      versions={versions}
      fromVersion={fromVersion}
      toVersion={toVersion}
      onChange={onChange}
    />,
  );
}

describe('VersionCompareSelector', () => {
  it('renders two dropdowns — from and to', async () => {
    await renderSelector();

    // Both selects should be present
    const selects = screen.getAllByRole('combobox');
    expect(selects).toHaveLength(2);
  });

  it('renders swap button', async () => {
    await renderSelector();

    const swap = screen.getByRole('button', { name: /swap/i });
    expect(swap).toBeInTheDocument();
  });

  it('shows inline error when from >= to', async () => {
    await renderSelector(3, 1);

    // Error message should be visible
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('does not show error when from < to', async () => {
    await renderSelector(1, 3);

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('swap button calls onChange with swapped values', async () => {
    const onChange = vi.fn();
    await renderSelector(1, 3, onChange);

    const swap = screen.getByRole('button', { name: /swap/i });
    fireEvent.click(swap);

    expect(onChange).toHaveBeenCalledWith(3, 1);
  });

  it('changing from dropdown calls onChange', async () => {
    const onChange = vi.fn();
    await renderSelector(1, 3, onChange);

    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0]!, { target: { value: '2' } });

    expect(onChange).toHaveBeenCalledWith(2, 3);
  });

  it('changing to dropdown calls onChange', async () => {
    const onChange = vi.fn();
    await renderSelector(1, 3, onChange);

    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[1]!, { target: { value: '2' } });

    expect(onChange).toHaveBeenCalledWith(1, 2);
  });
});
