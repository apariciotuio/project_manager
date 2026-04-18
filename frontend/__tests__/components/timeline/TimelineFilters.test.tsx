import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TimelineFilters } from '@/components/timeline/TimelineFilters';
import type { TimelineEventType, ActorType } from '@/lib/types/versions';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

const EMPTY_FILTERS = {
  eventTypes: [] as TimelineEventType[],
  actorTypes: [] as ActorType[],
  dateRange: { from: null, to: null },
};

describe('TimelineFilters', () => {
  it('renders an event-type checkbox for every TimelineEventType', () => {
    render(<TimelineFilters {...EMPTY_FILTERS} onChange={vi.fn()} />);
    const labels = [
      'state_transition',
      'comment_added',
      'comment_deleted',
      'version_created',
      'review_submitted',
      'export_triggered',
    ];
    for (const label of labels) {
      expect(
        screen.getByRole('checkbox', { name: new RegExp(label, 'i') }),
      ).toBeInTheDocument();
    }
  });

  it('renders an actor-type checkbox for every ActorType', () => {
    render(<TimelineFilters {...EMPTY_FILTERS} onChange={vi.fn()} />);
    for (const label of ['human', 'ai_suggestion', 'system']) {
      expect(
        screen.getByRole('checkbox', { name: new RegExp(label, 'i') }),
      ).toBeInTheDocument();
    }
  });

  it('renders from and to date inputs and a Reset button', () => {
    render(<TimelineFilters {...EMPTY_FILTERS} onChange={vi.fn()} />);
    expect(screen.getByLabelText(/fromLabel/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/toLabel/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /resetLabel/i })).toBeInTheDocument();
  });

  it('toggling an event-type checkbox emits onChange with the updated eventTypes array', async () => {
    const onChange = vi.fn();
    render(<TimelineFilters {...EMPTY_FILTERS} onChange={onChange} />);
    await userEvent.click(
      screen.getByRole('checkbox', { name: /state_transition/i }),
    );
    expect(onChange).toHaveBeenCalledWith({
      eventTypes: ['state_transition'],
      actorTypes: [],
      dateRange: { from: null, to: null },
    });
  });

  it('toggling an actor-type checkbox emits onChange with the updated actorTypes array', async () => {
    const onChange = vi.fn();
    render(<TimelineFilters {...EMPTY_FILTERS} onChange={onChange} />);
    await userEvent.click(
      screen.getByRole('checkbox', { name: /ai_suggestion/i }),
    );
    expect(onChange).toHaveBeenCalledWith({
      eventTypes: [],
      actorTypes: ['ai_suggestion'],
      dateRange: { from: null, to: null },
    });
  });

  it('changing the from date emits onChange with the new dateRange', async () => {
    const onChange = vi.fn();
    render(<TimelineFilters {...EMPTY_FILTERS} onChange={onChange} />);
    const from = screen.getByLabelText(/fromLabel/i);
    await userEvent.type(from, '2026-04-01');
    expect(onChange).toHaveBeenLastCalledWith({
      eventTypes: [],
      actorTypes: [],
      dateRange: { from: '2026-04-01', to: null },
    });
  });

  it('Reset clears all selected filters in a single onChange call', async () => {
    const onChange = vi.fn();
    render(
      <TimelineFilters
        eventTypes={['state_transition', 'comment_added']}
        actorTypes={['human']}
        dateRange={{ from: '2026-04-01', to: '2026-04-15' }}
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /resetLabel/i }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({
      eventTypes: [],
      actorTypes: [],
      dateRange: { from: null, to: null },
    });
  });

  it('unchecking an event-type checkbox removes it from eventTypes', async () => {
    const onChange = vi.fn();
    render(
      <TimelineFilters
        eventTypes={['state_transition', 'comment_added']}
        actorTypes={[]}
        dateRange={{ from: null, to: null }}
        onChange={onChange}
      />,
    );
    await userEvent.click(
      screen.getByRole('checkbox', { name: /state_transition/i }),
    );
    expect(onChange).toHaveBeenCalledWith({
      eventTypes: ['comment_added'],
      actorTypes: [],
      dateRange: { from: null, to: null },
    });
  });
});
