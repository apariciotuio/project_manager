/**
 * EP-07 Group 3a — VersionDiffViewer with new VersionDiff type.
 *
 * Tests:
 * - change_type=modified: hunks rendered
 * - change_type=added: full proposed content as green hunk
 * - change_type=removed: full deleted content as red hunk (no "no changes" placeholder)
 * - change_type=reordered: "Reordered" badge; no diff hunks
 * - change_type=unchanged: collapsed by default
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { VersionDiff } from '@/lib/types/versions';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock('@/hooks/work-item/use-versions', () => ({
  useDiffVsPrevious: vi.fn(),
}));

async function renderViewer(diff: VersionDiff | null, isLoading = false, error: Error | null = null) {
  const { useDiffVsPrevious } = await import('@/hooks/work-item/use-versions');
  (useDiffVsPrevious as ReturnType<typeof vi.fn>).mockReturnValue({ diff, isLoading, error });

  const { VersionDiffViewer } = await import(
    '@/components/work-item/VersionDiffViewer'
  );
  return render(<VersionDiffViewer workItemId="wi-1" fromVersion={1} toVersion={2} />);
}

describe('VersionDiffViewer — change_type rendering', () => {
  it('renders hunks for modified section', async () => {
    const diff: VersionDiff = {
      from_version: 1,
      to_version: 2,
      metadata_diff: {},
      sections: [
        {
          section_type: 'summary',
          change_type: 'modified',
          hunks: [
            { type: 'removed', lines: ['Old line'] },
            { type: 'added', lines: ['New line'] },
          ],
        },
      ],
    };

    await renderViewer(diff);

    expect(screen.getByText(/Old line/)).toBeInTheDocument();
    expect(screen.getByText(/New line/)).toBeInTheDocument();
  });

  it('renders green hunk for added section', async () => {
    const diff: VersionDiff = {
      from_version: 1,
      to_version: 2,
      metadata_diff: {},
      sections: [
        {
          section_type: 'acceptance_criteria',
          change_type: 'added',
          hunks: [{ type: 'added', lines: ['AC line 1', 'AC line 2'] }],
        },
      ],
    };

    await renderViewer(diff);

    expect(screen.getByText(/AC line 1/)).toBeInTheDocument();
    expect(screen.getByText(/AC line 2/)).toBeInTheDocument();
    // "no changes" placeholder must NOT appear
    expect(screen.queryByText('diffEmpty')).not.toBeInTheDocument();
  });

  it('renders red hunk for removed section and suppresses no-changes placeholder', async () => {
    const diff: VersionDiff = {
      from_version: 1,
      to_version: 2,
      metadata_diff: {},
      sections: [
        {
          section_type: 'context',
          change_type: 'removed',
          hunks: [{ type: 'removed', lines: ['Deleted line'] }],
        },
      ],
    };

    await renderViewer(diff);

    expect(screen.getByText(/Deleted line/)).toBeInTheDocument();
    expect(screen.queryByText('diffEmpty')).not.toBeInTheDocument();
  });

  it('renders Reordered badge for reordered section without diff hunks', async () => {
    const diff: VersionDiff = {
      from_version: 1,
      to_version: 2,
      metadata_diff: {},
      sections: [
        {
          section_type: 'tasks',
          change_type: 'reordered',
          hunks: [],
        },
      ],
    };

    await renderViewer(diff);

    // Badge must be present
    expect(screen.getByText(/reordered/i)).toBeInTheDocument();
    // No line-level diff rendered (hunks empty and component must not render hunk container)
    expect(screen.queryByRole('code')).not.toBeInTheDocument();
  });

  it('collapses unchanged section by default', async () => {
    const diff: VersionDiff = {
      from_version: 1,
      to_version: 2,
      metadata_diff: {},
      sections: [
        {
          section_type: 'description',
          change_type: 'unchanged',
          hunks: [{ type: 'context', lines: ['Same line'] }],
        },
      ],
    };

    await renderViewer(diff);

    // The hunk content should not be visible until expanded
    expect(screen.queryByText('Same line')).not.toBeInTheDocument();
  });
});
