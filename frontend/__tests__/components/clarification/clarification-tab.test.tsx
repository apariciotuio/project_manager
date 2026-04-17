import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { ClarificationTab } from '@/components/clarification/clarification-tab';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const BASE = 'http://localhost';

// Minimal WebSocket stub
class MockWebSocket {
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  constructor(url: string) { this.url = url; }
}

describe('ClarificationTab', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    server.use(
      http.get(`${BASE}/api/v1/threads`, () =>
        HttpResponse.json({
          data: [{
            id: 'thread-1', work_item_id: 'wi-1', user_id: 'user-1',
            dundun_conversation_id: 'd-1', last_message_preview: null,
            last_message_at: null, created_at: '2026-04-17T00:00:00Z',
          }],
        }),
      ),
      http.get(`${BASE}/api/v1/threads/thread-1/history`, () =>
        HttpResponse.json({ data: [] }),
      ),
      http.get(`${BASE}/api/v1/work-items/wi-1/gaps`, () =>
        HttpResponse.json({ data: { work_item_id: 'wi-1', findings: [], score: 1.0 } }),
      ),
      http.get(`${BASE}/api/v1/work-items/wi-1/suggestion-sets`, () =>
        HttpResponse.json({ data: [] }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders the chat panel', async () => {
    render(<ClarificationTab workItemId="wi-1" workItemVersion={1} canEdit />);
    await waitFor(() => expect(screen.getByText('emptyChat')).toBeInTheDocument());
  });

  it('renders the gap panel', async () => {
    render(<ClarificationTab workItemId="wi-1" workItemVersion={1} canEdit />);
    await waitFor(() => expect(screen.getByText('100%')).toBeInTheDocument());
  });

  it('renders Get Suggestions button when canEdit', async () => {
    render(<ClarificationTab workItemId="wi-1" workItemVersion={1} canEdit />);
    expect(screen.getByRole('button', { name: /generateButton/i })).toBeInTheDocument();
  });

  it('does not render Get Suggestions button when canEdit is false', async () => {
    render(<ClarificationTab workItemId="wi-1" workItemVersion={1} canEdit={false} />);
    expect(screen.queryByRole('button', { name: /generateButton/i })).not.toBeInTheDocument();
  });
});
