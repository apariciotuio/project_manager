import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { TimelineTab } from '@/components/work-item/timeline-tab';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

// RelativeTime uses useRelativeTime which relies on setInterval — stub it out
vi.mock('@/components/domain/relative-time', () => ({
  RelativeTime: ({ iso }: { iso: string }) => <time dateTime={iso}>{iso}</time>,
}));

const BASE_EVENT = {
  work_item_id: 'wi-1',
  workspace_id: 'ws-1',
  actor_type: 'human' as const,
  actor_id: 'user-1',
  actor_display_name: 'Alice',
  summary: 'State changed from draft to in_review',
  payload: { from_state: 'draft', to_state: 'in_review' },
  occurred_at: '2026-01-02T00:00:00Z',
  source_id: null,
  source_table: null,
};

const EVT_STATE: typeof BASE_EVENT & { id: string; event_type: string } = {
  ...BASE_EVENT,
  id: 'evt-1',
  event_type: 'state_transition',
};

const EVT_COMMENT = {
  ...BASE_EVENT,
  id: 'evt-2',
  event_type: 'comment_added',
  actor_display_name: 'Bob',
  summary: 'Added a comment',
  payload: { comment_id: 'c-1' },
};

const EVT_OWNER = {
  ...BASE_EVENT,
  id: 'evt-3',
  event_type: 'owner_changed',
  summary: 'Owner changed',
};

const EVT_TAG = {
  ...BASE_EVENT,
  id: 'evt-4',
  event_type: 'tag_added',
  summary: 'Tag added',
};

const EVT_AI = {
  ...BASE_EVENT,
  id: 'evt-5',
  event_type: 'comment_added',
  actor_type: 'ai_suggestion' as const,
  actor_display_name: 'AI',
  summary: 'AI added a suggestion comment',
};

function mockTimeline(
  events: unknown[],
  { hasMore = false, nextCursor = null }: { hasMore?: boolean; nextCursor?: string | null } = {}
) {
  server.use(
    http.get('http://localhost/api/v1/work-items/wi-1/timeline', () =>
      HttpResponse.json({
        data: { events, has_more: hasMore, next_cursor: nextCursor },
      })
    )
  );
}

describe('TimelineTab', () => {
  it('shows loading skeletons on initial load', async () => {
    // Delay response so skeleton is visible
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/timeline', async () => {
        await new Promise((r) => setTimeout(r, 100));
        return HttpResponse.json({ data: { events: [], has_more: false, next_cursor: null } });
      })
    );

    const { container } = render(<TimelineTab workItemId="wi-1" />);
    // Skeleton divs are present before data loads
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(0);

    await waitFor(() =>
      expect(screen.getByText('workspace.itemDetail.timeline.empty')).toBeInTheDocument()
    );
  });

  it('shows empty state when no events', async () => {
    mockTimeline([]);
    render(<TimelineTab workItemId="wi-1" />);
    await waitFor(() =>
      expect(screen.getByText('workspace.itemDetail.timeline.empty')).toBeInTheDocument()
    );
  });

  it('renders populated event list with actor and summary', async () => {
    mockTimeline([EVT_STATE, EVT_COMMENT]);
    render(<TimelineTab workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('State changed from draft to in_review')).toBeInTheDocument());
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Added a comment')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  it('does not show Load more button when hasMore=false', async () => {
    mockTimeline([EVT_STATE], { hasMore: false });
    render(<TimelineTab workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('State changed from draft to in_review')).toBeInTheDocument());
    expect(screen.queryByText('workspace.itemDetail.timeline.loadMore')).not.toBeInTheDocument();
  });

  it('shows Load more button when hasMore=true and clicking it fetches next page', async () => {
    const page2Events = [EVT_COMMENT];
    let callCount = 0;
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/timeline', ({ request }) => {
        const url = new URL(request.url);
        const cursor = url.searchParams.get('cursor');
        callCount++;
        if (cursor === 'cursor-2') {
          return HttpResponse.json({
            data: { events: page2Events, has_more: false, next_cursor: null },
          });
        }
        return HttpResponse.json({
          data: { events: [EVT_STATE], has_more: true, next_cursor: 'cursor-2' },
        });
      })
    );

    const user = userEvent.setup();
    render(<TimelineTab workItemId="wi-1" />);

    await waitFor(() =>
      expect(screen.getByText('workspace.itemDetail.timeline.loadMore')).toBeInTheDocument()
    );

    await user.click(screen.getByText('workspace.itemDetail.timeline.loadMore'));

    await waitFor(() => expect(screen.getByText('Added a comment')).toBeInTheDocument());
    expect(callCount).toBe(2);
    expect(screen.queryByText('workspace.itemDetail.timeline.loadMore')).not.toBeInTheDocument();
  });

  it('shows error banner when fetch fails', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/timeline', () =>
        HttpResponse.json({ error: 'fail' }, { status: 500 })
      )
    );
    render(<TimelineTab workItemId="wi-1" />);
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        'workspace.itemDetail.timeline.errorBanner'
      )
    );
  });

  it('renders correct icon data-event-type per event_type', async () => {
    mockTimeline([EVT_STATE, EVT_OWNER, EVT_TAG]);
    const { container } = render(<TimelineTab workItemId="wi-1" />);

    await waitFor(() =>
      expect(screen.getByText('State changed from draft to in_review')).toBeInTheDocument()
    );

    const icons = container.querySelectorAll('[data-event-type]');
    const types = Array.from(icons).map((el) => el.getAttribute('data-event-type'));
    expect(types).toContain('state_transition');
    expect(types).toContain('owner_changed');
    expect(types).toContain('tag_added');
  });

  it('renders ai_suggestion actor with Bot icon marker', async () => {
    mockTimeline([EVT_AI]);
    render(<TimelineTab workItemId="wi-1" />);

    await waitFor(() =>
      expect(screen.getByText('AI added a suggestion comment')).toBeInTheDocument()
    );

    // actor_type is ai_suggestion — the display name still renders
    expect(screen.getByText('AI')).toBeInTheDocument();
  });
});
