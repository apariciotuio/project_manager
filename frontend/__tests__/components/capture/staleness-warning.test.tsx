import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// next-intl mock — returns `${ns}.${key}` so tests assert against translation keys
vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${ns}.${key}:${JSON.stringify(params)}`;
    return `${ns}.${key}`;
  },
}));

import { StalenessWarning } from '@/components/capture/staleness-warning';

const LAST_UPDATE = new Date(Date.now() - 2 * 60_000).toISOString(); // 2 minutes ago

describe('StalenessWarning', () => {
  it('renders the conflict banner text', () => {
    render(
      <StalenessWarning
        onOverwrite={vi.fn()}
        onKeepMine={vi.fn()}
        lastServerUpdate={LAST_UPDATE}
      />,
    );
    expect(screen.getByText(/workspace\.newItem\.conflict\.banner/)).toBeTruthy();
  });

  it('renders Overwrite button', () => {
    render(
      <StalenessWarning
        onOverwrite={vi.fn()}
        onKeepMine={vi.fn()}
        lastServerUpdate={LAST_UPDATE}
      />,
    );
    expect(screen.getByText('workspace.newItem.conflict.overwriteButton')).toBeTruthy();
  });

  it('renders Keep mine button', () => {
    render(
      <StalenessWarning
        onOverwrite={vi.fn()}
        onKeepMine={vi.fn()}
        lastServerUpdate={LAST_UPDATE}
      />,
    );
    expect(screen.getByText('workspace.newItem.conflict.keepMineButton')).toBeTruthy();
  });

  it('calls onOverwrite when Overwrite button is clicked', async () => {
    const onOverwrite = vi.fn();
    render(
      <StalenessWarning
        onOverwrite={onOverwrite}
        onKeepMine={vi.fn()}
        lastServerUpdate={LAST_UPDATE}
      />,
    );
    await userEvent.click(screen.getByText('workspace.newItem.conflict.overwriteButton'));
    expect(onOverwrite).toHaveBeenCalledOnce();
  });

  it('calls onKeepMine when Keep mine button is clicked', async () => {
    const onKeepMine = vi.fn();
    render(
      <StalenessWarning
        onOverwrite={vi.fn()}
        onKeepMine={onKeepMine}
        lastServerUpdate={LAST_UPDATE}
      />,
    );
    await userEvent.click(screen.getByText('workspace.newItem.conflict.keepMineButton'));
    expect(onKeepMine).toHaveBeenCalledOnce();
  });

  it('shows relative time for lastServerUpdate', () => {
    render(
      <StalenessWarning
        onOverwrite={vi.fn()}
        onKeepMine={vi.fn()}
        lastServerUpdate={LAST_UPDATE}
      />,
    );
    // The lastServerUpdate key is rendered with time param
    expect(screen.getByText(/workspace\.newItem\.conflict\.lastServerUpdate/)).toBeTruthy();
  });
});
