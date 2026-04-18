import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { QuickActionMenu } from '@/components/clarification/quick-action-menu';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

// Mock API
vi.mock('@/lib/api/quick-actions', () => ({
  executeQuickAction: vi.fn(),
  undoQuickAction: vi.fn(),
}));

import { executeQuickAction, undoQuickAction } from '@/lib/api/quick-actions';

const mockedExecute = vi.mocked(executeQuickAction);
const mockedUndo = vi.mocked(undoQuickAction);

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('QuickActionMenu — section type filtering', () => {
  it('renders only generate_ac for acceptance_criteria section', () => {
    render(
      <QuickActionMenu
        workItemId="wi-1"
        section="acceptance_criteria"
        sectionContent="some content"
        onActionApplied={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /generate_ac/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /rewrite/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /expand/i })).not.toBeInTheDocument();
  });

  it('renders rewrite, concretize, expand, shorten for description section', () => {
    render(
      <QuickActionMenu
        workItemId="wi-1"
        section="description"
        sectionContent="some content"
        onActionApplied={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /rewrite/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /concretize/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /expand/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /shorten/i })).toBeInTheDocument();
  });

  it('renders rewrite, expand, shorten for other text sections', () => {
    render(
      <QuickActionMenu
        workItemId="wi-1"
        section="background"
        sectionContent="some content"
        onActionApplied={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /rewrite/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /expand/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /shorten/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /concretize/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /generate_ac/i })).not.toBeInTheDocument();
  });
});

describe('QuickActionMenu — empty content disables all actions', () => {
  it('disables all buttons when sectionContent is empty', () => {
    render(
      <QuickActionMenu
        workItemId="wi-1"
        section="description"
        sectionContent=""
        onActionApplied={vi.fn()}
      />,
    );
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });
});

describe('QuickActionMenu — loading spinner during execution', () => {
  it('shows spinner and disables buttons while executing', async () => {
    let resolveFn!: (value: { result: string; action_id: string }) => void;
    const pending = new Promise<{ result: string; action_id: string }>((r) => { resolveFn = r; });
    mockedExecute.mockReturnValue(pending);

    render(
      <QuickActionMenu
        workItemId="wi-1"
        section="description"
        sectionContent="original"
        onActionApplied={vi.fn()}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /rewrite/i }));
    });

    expect(screen.getByRole('status')).toBeInTheDocument(); // spinner

    // All action buttons replaced by spinner
    expect(screen.queryByRole('button', { name: /rewrite/i })).not.toBeInTheDocument();

    // Clean up
    await act(async () => {
      resolveFn({ result: 'new content', action_id: 'act-1' });
      await pending;
    });
  });
});

describe('QuickActionMenu — success flow with undo toast', () => {
  it('calls onActionApplied and shows undo toast on success', async () => {
    const onActionApplied = vi.fn();
    mockedExecute.mockResolvedValue({ result: 'new content', action_id: 'act-1' });

    render(
      <QuickActionMenu
        workItemId="wi-1"
        section="description"
        sectionContent="original"
        onActionApplied={onActionApplied}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /rewrite/i }));
    });

    expect(onActionApplied).toHaveBeenCalledWith('new content');
    expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument();
  });

  it('undo toast disappears after 10s', async () => {
    vi.useFakeTimers();
    mockedExecute.mockResolvedValue({ result: 'new content', action_id: 'act-1' });

    render(
      <QuickActionMenu
        workItemId="wi-1"
        section="description"
        sectionContent="original"
        onActionApplied={vi.fn()}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /rewrite/i }));
    });

    expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument();

    await act(async () => { vi.advanceTimersByTime(10000); });

    expect(screen.queryByRole('button', { name: /undo/i })).not.toBeInTheDocument();
  });

  it('calls undoQuickAction when undo clicked before countdown', async () => {
    mockedExecute.mockResolvedValue({ result: 'new content', action_id: 'act-1' });
    mockedUndo.mockResolvedValue(undefined);
    const onActionApplied = vi.fn();

    render(
      <QuickActionMenu
        workItemId="wi-1"
        section="description"
        sectionContent="original"
        onActionApplied={onActionApplied}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /rewrite/i }));
    });

    expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /undo/i }));
    });

    expect(mockedUndo).toHaveBeenCalledWith('wi-1', 'act-1');
    // Toast dismissed after undo
    expect(screen.queryByRole('button', { name: /undo/i })).not.toBeInTheDocument();
  });
});

describe('QuickActionMenu — error state', () => {
  it('shows inline error when executeQuickAction fails', async () => {
    mockedExecute.mockRejectedValue(new Error('Network error'));

    render(
      <QuickActionMenu
        workItemId="wi-1"
        section="description"
        sectionContent="original"
        onActionApplied={vi.fn()}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /rewrite/i }));
    });

    expect(screen.getByRole('alert')).toBeInTheDocument();
    // Content unchanged — action buttons restored
    expect(screen.getByRole('button', { name: /rewrite/i })).toBeInTheDocument();
  });
});

describe('QuickActionMenu — unmount cleanup', () => {
  it('clears setTimeout on unmount without state-update-after-unmount error', async () => {
    vi.useFakeTimers();
    mockedExecute.mockResolvedValue({ result: 'new content', action_id: 'act-1' });
    const consoleSpy = vi.spyOn(console, 'error');

    const { unmount } = render(
      <QuickActionMenu
        workItemId="wi-1"
        section="description"
        sectionContent="original"
        onActionApplied={vi.fn()}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /rewrite/i }));
    });

    expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument();

    unmount();
    await act(async () => { vi.advanceTimersByTime(10000); });

    // No React state-after-unmount errors
    expect(consoleSpy).not.toHaveBeenCalledWith(expect.stringContaining('unmounted'));
    consoleSpy.mockRestore();
  });
});
