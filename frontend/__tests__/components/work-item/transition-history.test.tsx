import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { TransitionHistory } from '@/components/work-item/transition-history';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    const base = `${ns}.${key}`;
    if (params && typeof params === 'object') {
      const entries = Object.entries(params).map(([k, v]) => `${k}=${v}`).join(',');
      return `${base}(${entries})`;
    }
    return base;
  },
}));

const ROWS = [
  {
    id: 't1',
    work_item_id: 'wi-1',
    from_state: 'draft',
    to_state: 'in_clarification',
    actor_id: 'user-1',
    triggered_at: '2026-02-01T10:00:00Z',
    transition_reason: 'kicking off',
    is_override: false,
    override_justification: null,
  },
  {
    id: 't2',
    work_item_id: 'wi-1',
    from_state: 'in_review',
    to_state: 'ready',
    actor_id: 'user-2',
    triggered_at: '2026-02-05T10:00:00Z',
    transition_reason: null,
    is_override: true,
    override_justification: 'Demo today',
  },
];

describe('TransitionHistory', () => {
  it('shows empty-state when there are no transitions', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/transitions', () =>
        HttpResponse.json({ data: [] }),
      ),
    );
    render(<TransitionHistory workItemId="wi-1" />);
    await waitFor(() =>
      expect(
        screen.getByText(/workspace\.itemDetail\.audit\.transitions\.empty/i),
      ).toBeInTheDocument(),
    );
  });

  it('lists transitions with from→to, reason, and override badge', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/transitions', () =>
        HttpResponse.json({ data: ROWS }),
      ),
    );
    render(<TransitionHistory workItemId="wi-1" />);
    await waitFor(() => {
      expect(screen.getByText(/kicking off/)).toBeInTheDocument();
    });
    expect(
      screen.getByText(/workspace\.itemDetail\.audit\.transitions\.override/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Demo today/)).toBeInTheDocument();
  });

  it('surfaces an error when the API fails', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/transitions', () =>
        HttpResponse.json(
          { error: { code: 'INTERNAL_ERROR', message: 'boom' } },
          { status: 500 },
        ),
      ),
    );
    render(<TransitionHistory workItemId="wi-1" />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  });
});
