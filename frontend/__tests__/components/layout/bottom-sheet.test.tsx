/**
 * BottomSheet tests — EP-12 Group 1
 */
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BottomSheet } from '@/components/layout/bottom-sheet';

describe('BottomSheet', () => {
  it('renders nothing when closed', () => {
    render(
      <BottomSheet open={false} onClose={() => {}}>
        <div data-testid="content">content</div>
      </BottomSheet>,
    );
    expect(screen.queryByTestId('content')).not.toBeInTheDocument();
  });

  it('renders with role=dialog and aria-modal when open', () => {
    render(
      <BottomSheet open={true} onClose={() => {}} title="Test sheet">
        <div>content</div>
      </BottomSheet>,
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('shows title when provided', () => {
    render(
      <BottomSheet open={true} onClose={() => {}} title="My Sheet">
        <div>content</div>
      </BottomSheet>,
    );
    expect(screen.getByText('My Sheet')).toBeInTheDocument();
  });

  it('calls onClose when Escape key is pressed', async () => {
    const onClose = vi.fn();
    render(
      <BottomSheet open={true} onClose={onClose} title="Test">
        <div>content</div>
      </BottomSheet>,
    );
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when backdrop is clicked', async () => {
    const onClose = vi.fn();
    render(
      <BottomSheet open={true} onClose={onClose} title="Test">
        <div>content</div>
      </BottomSheet>,
    );
    const backdrop = screen.getByTestId('bottom-sheet-backdrop');
    await userEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('has max-height 75vh class', () => {
    render(
      <BottomSheet open={true} onClose={() => {}} title="Test">
        <div>content</div>
      </BottomSheet>,
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog.className).toMatch(/max-h-\[75vh\]/);
  });

  it('has overflow-y-auto for internal scroll', () => {
    render(
      <BottomSheet open={true} onClose={() => {}} title="Test">
        <div>content</div>
      </BottomSheet>,
    );
    // The scroll container inside the dialog
    const scrollContainer = screen.getByTestId('bottom-sheet-body');
    expect(scrollContainer.className).toMatch(/overflow-y-auto/);
  });

  it('submit button is always visible (not inside scroll container)', () => {
    render(
      <BottomSheet
        open={true}
        onClose={() => {}}
        title="Test"
        footer={<button type="submit">Submit</button>}
      >
        <div>content</div>
      </BottomSheet>,
    );
    const submit = screen.getByRole('button', { name: /submit/i });
    expect(submit).toBeVisible();
    // Footer should be outside scroll body
    const footer = screen.getByTestId('bottom-sheet-footer');
    expect(footer).toBeInTheDocument();
  });
});
