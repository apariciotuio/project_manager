import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TimelineFilters } from '@/components/timeline/TimelineFilters';
import type { TimelineEventType, TimelineActorType } from '@/lib/types/work-item-detail';

const DEFAULT_PROPS = {
  eventTypes: [] as TimelineEventType[],
  actorTypes: [] as TimelineActorType[],
  dateRange: { from: null, to: null },
  onChange: vi.fn(),
};

describe('TimelineFilters', () => {
  it('renders event type checkboxes for each known event type', () => {
    render(<TimelineFilters {...DEFAULT_PROPS} />);
    // Fieldset or group for event types
    expect(screen.getByRole('group', { name: /event type/i })).toBeInTheDocument();
    // At least state_transition and comment_added checkboxes
    expect(screen.getByRole('checkbox', { name: /state.transition/i })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /comment.added/i })).toBeInTheDocument();
  });

  it('renders actor type checkboxes', () => {
    render(<TimelineFilters {...DEFAULT_PROPS} />);
    expect(screen.getByRole('group', { name: /actor type/i })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /human/i })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /ai/i })).toBeInTheDocument();
  });

  it('renders date range inputs', () => {
    render(<TimelineFilters {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText(/from/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/to/i)).toBeInTheDocument();
  });

  it('checks checkboxes matching current eventTypes prop', () => {
    render(
      <TimelineFilters
        {...DEFAULT_PROPS}
        eventTypes={['state_transition']}
      />
    );
    expect(screen.getByRole('checkbox', { name: /state.transition/i })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /comment.added/i })).not.toBeChecked();
  });

  it('calls onChange with toggled event type when checkbox clicked', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <TimelineFilters
        {...DEFAULT_PROPS}
        eventTypes={[]}
        onChange={onChange}
      />
    );

    await user.click(screen.getByRole('checkbox', { name: /state.transition/i }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ eventTypes: ['state_transition'] })
    );
  });

  it('calls onChange removing event type when already-checked checkbox clicked', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <TimelineFilters
        {...DEFAULT_PROPS}
        eventTypes={['state_transition', 'comment_added']}
        onChange={onChange}
      />
    );

    await user.click(screen.getByRole('checkbox', { name: /state.transition/i }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ eventTypes: ['comment_added'] })
    );
  });

  it('calls onChange with updated dateRange when from date changes', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<TimelineFilters {...DEFAULT_PROPS} onChange={onChange} />);

    const fromInput = screen.getByLabelText(/from/i);
    await user.clear(fromInput);
    await user.type(fromInput, '2026-01-01');

    // onChange called with new from value
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        dateRange: expect.objectContaining({ from: '2026-01-01' }),
      })
    );
  });

  it('Reset filters button calls onChange with empty state', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <TimelineFilters
        {...DEFAULT_PROPS}
        eventTypes={['state_transition']}
        actorTypes={['human']}
        dateRange={{ from: '2026-01-01', to: null }}
        onChange={onChange}
      />
    );

    await user.click(screen.getByRole('button', { name: /reset/i }));
    expect(onChange).toHaveBeenCalledWith({
      eventTypes: [],
      actorTypes: [],
      dateRange: { from: null, to: null },
    });
  });

  it('has accessible fieldset/legend structure for a11y', () => {
    const { container } = render(<TimelineFilters {...DEFAULT_PROPS} />);
    const fieldsets = container.querySelectorAll('fieldset');
    expect(fieldsets.length).toBeGreaterThanOrEqual(2);
    const legends = container.querySelectorAll('legend');
    expect(legends.length).toBeGreaterThanOrEqual(2);
  });
});
