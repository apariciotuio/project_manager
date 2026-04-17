import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// next-intl mock — returns `${ns}.${key}` so tests assert against translation keys
vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      return `${ns}.${key}:${JSON.stringify(params)}`;
    }
    return `${ns}.${key}`;
  },
}));

import { DraftResumeBanner } from '@/components/capture/draft-resume-banner';
import type { DraftData } from '@/hooks/use-pre-creation-draft';

const DRAFT: DraftData & { updated_at: string } = {
  title: 'Unsaved draft title',
  type: 'task',
  updated_at: new Date(Date.now() - 5 * 60_000).toISOString(), // 5 minutes ago
};

describe('DraftResumeBanner', () => {
  it('renders when pendingDraft is provided', () => {
    render(
      <DraftResumeBanner
        pendingDraft={DRAFT}
        onResume={vi.fn()}
        onDiscard={vi.fn()}
      />,
    );
    // Body text uses the i18n key
    expect(screen.getByText(/workspace\.newItem\.draft\.resumeBody/)).toBeTruthy();
  });

  it('does not render when pendingDraft is null', () => {
    const { container } = render(
      <DraftResumeBanner
        pendingDraft={null}
        onResume={vi.fn()}
        onDiscard={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('calls onResume when Resume button is clicked', async () => {
    const onResume = vi.fn();
    render(
      <DraftResumeBanner
        pendingDraft={DRAFT}
        onResume={onResume}
        onDiscard={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByText('workspace.newItem.draft.resumeButton'));
    expect(onResume).toHaveBeenCalledOnce();
  });

  it('calls onDiscard when Discard button is clicked', async () => {
    const onDiscard = vi.fn();
    render(
      <DraftResumeBanner
        pendingDraft={DRAFT}
        onResume={vi.fn()}
        onDiscard={onDiscard}
      />,
    );
    await userEvent.click(screen.getByText('workspace.newItem.draft.discardButton'));
    expect(onDiscard).toHaveBeenCalledOnce();
  });

  it('renders both Resume and Discard buttons', () => {
    render(
      <DraftResumeBanner
        pendingDraft={DRAFT}
        onResume={vi.fn()}
        onDiscard={vi.fn()}
      />,
    );
    expect(screen.getByText('workspace.newItem.draft.resumeButton')).toBeTruthy();
    expect(screen.getByText('workspace.newItem.draft.discardButton')).toBeTruthy();
  });
});
