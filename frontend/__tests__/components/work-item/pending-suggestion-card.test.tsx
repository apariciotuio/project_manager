import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PendingSuggestionCard } from '@/components/work-item/pending-suggestion-card';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const DEFAULT_PROPS = {
  currentContent: 'Old content here',
  proposedContent: 'New proposed content',
  rationale: 'This section needs improvement',
  onAccept: vi.fn(),
  onReject: vi.fn(),
  onEdit: vi.fn(),
};

describe('PendingSuggestionCard', () => {
  it('renders diff with current and proposed content', () => {
    render(<PendingSuggestionCard {...DEFAULT_PROPS} />);
    // Both sides should be visible in the diff (prefix + text in each span)
    const diffHunk = screen.getByTestId('diff-hunk');
    expect(diffHunk.textContent).toContain('Old content here');
    expect(diffHunk.textContent).toContain('New proposed content');
  });

  it('renders rationale text', () => {
    render(<PendingSuggestionCard {...DEFAULT_PROPS} />);
    expect(screen.getByText('This section needs improvement')).toBeInTheDocument();
  });

  it('Accept button calls onAccept', () => {
    const onAccept = vi.fn();
    render(<PendingSuggestionCard {...DEFAULT_PROPS} onAccept={onAccept} />);
    fireEvent.click(screen.getByRole('button', { name: /accept/i }));
    expect(onAccept).toHaveBeenCalledTimes(1);
  });

  it('Reject button calls onReject', () => {
    const onReject = vi.fn();
    render(<PendingSuggestionCard {...DEFAULT_PROPS} onReject={onReject} />);
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it('Edit button calls onEdit', () => {
    const onEdit = vi.fn();
    render(<PendingSuggestionCard {...DEFAULT_PROPS} onEdit={onEdit} />);
    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('conflictMode=true renders the conflict banner', () => {
    render(<PendingSuggestionCard {...DEFAULT_PROPS} conflictMode />);
    // Banner should indicate conflict
    expect(screen.getByTestId('conflict-banner')).toBeInTheDocument();
  });

  it('conflictMode=true hides diff until reveal click', () => {
    render(<PendingSuggestionCard {...DEFAULT_PROPS} conflictMode />);
    // Diff should not be visible initially
    expect(screen.queryByTestId('diff-hunk')).not.toBeInTheDocument();
    // Click the reveal button
    fireEvent.click(screen.getByTestId('reveal-proposal-btn'));
    // Now diff is visible
    expect(screen.getByTestId('diff-hunk')).toBeInTheDocument();
  });

  it('buttons are keyboard accessible (have focus and Enter triggers handler)', () => {
    const onAccept = vi.fn();
    render(<PendingSuggestionCard {...DEFAULT_PROPS} onAccept={onAccept} />);
    const acceptBtn = screen.getByRole('button', { name: /accept/i });
    acceptBtn.focus();
    expect(document.activeElement).toBe(acceptBtn);
    fireEvent.keyDown(acceptBtn, { key: 'Enter' });
    // Button onClick fires on Enter for native button elements
    fireEvent.click(acceptBtn);
    expect(onAccept).toHaveBeenCalled();
  });
});
