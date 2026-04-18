import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReviewRespondDialog } from '@/components/work-item/review-respond-dialog';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

// Helper to set window.innerWidth and trigger the effect
function setViewport(width: number) {
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: width });
  window.dispatchEvent(new Event('resize'));
}

const defaultProps = {
  reviewRequestId: 'req-1',
  open: true,
  onSuccess: vi.fn(),
  onClose: vi.fn(),
};

describe('ReviewRespondDialog — mobile (< 640px)', () => {
  beforeEach(() => {
    setViewport(375);
  });

  afterEach(() => {
    setViewport(1024);
  });

  it('[RED] renders BottomSheet (role=dialog with bottom-sheet-body) on mobile', () => {
    render(<ReviewRespondDialog {...defaultProps} />);
    // BottomSheet renders data-testid="bottom-sheet-body"
    expect(screen.getByTestId('bottom-sheet-body')).toBeInTheDocument();
  });

  it('[RED] submit button is always visible — rendered in BottomSheet footer (bottom-sheet-footer)', () => {
    render(<ReviewRespondDialog {...defaultProps} />);
    const footer = screen.getByTestId('bottom-sheet-footer');
    expect(footer).toBeInTheDocument();
    // submit button must be inside the footer, never inside the scrollable body
    expect(footer).toContainElement(screen.getByTestId('submit-btn'));
  });
});

describe('ReviewRespondDialog — desktop (>= 640px)', () => {
  beforeEach(() => {
    setViewport(1024);
  });

  it('[RED] renders shadcn Dialog (not BottomSheet) on desktop', () => {
    render(<ReviewRespondDialog {...defaultProps} />);
    // BottomSheet body should NOT be present
    expect(screen.queryByTestId('bottom-sheet-body')).not.toBeInTheDocument();
    // shadcn Dialog renders role=dialog
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
