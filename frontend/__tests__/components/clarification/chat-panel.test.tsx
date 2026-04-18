import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { ChatPanel } from '@/components/clarification/chat-panel';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const BASE = 'http://localhost';

// Minimal WebSocket mock
type MockWsListener = (event: { data: string }) => void;

interface MockWs {
  url: string;
  readyState: number;
  onopen: (() => void) | null;
  onmessage: MockWsListener | null;
  onerror: ((e: Event) => void) | null;
  onclose: (() => void) | null;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
}

let mockWs: MockWs | null = null;

class MockWebSocket {
  url: string;
  readyState = 0; // CONNECTING
  onopen: (() => void) | null = null;
  onmessage: MockWsListener | null = null;
  onerror: ((e: Event) => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = 3;
  });

  constructor(url: string) {
    this.url = url;
    mockWs = this as unknown as MockWs;
  }
}

function setupHistoryHandler(messages: unknown[] = []) {
  server.use(
    http.get(`${BASE}/api/v1/threads/thread-1/history`, () =>
      HttpResponse.json({ data: messages }),
    ),
  );
}

describe('ChatPanel', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    server.use(
      http.get(`${BASE}/api/v1/threads`, () =>
        HttpResponse.json({
          data: [
            {
              id: 'thread-1',
              work_item_id: 'wi-1',
              user_id: 'user-1',
              dundun_conversation_id: 'dundun-1',
              last_message_preview: null,
              last_message_at: null,
              created_at: '2026-04-17T00:00:00Z',
            },
          ],
        }),
      ),
      http.get(`${BASE}/api/v1/work-items/wi-1/specification`, () =>
        HttpResponse.json({ data: { work_item_id: 'wi-1', sections: [] } }),
      ),
    );
    setupHistoryHandler([]);
    mockWs = null;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows empty state when no messages', async () => {
    render(<ChatPanel workItemId="wi-1" />);
    await waitFor(() => expect(screen.getByText('emptyChat')).toBeInTheDocument());
  });

  it('renders historical messages with correct roles', async () => {
    setupHistoryHandler([
      { id: 'msg-1', role: 'user', content: 'Hello', created_at: '2026-04-17T10:00:00Z' },
      { id: 'msg-2', role: 'assistant', content: 'Hi there', created_at: '2026-04-17T10:01:00Z' },
    ]);
    render(<ChatPanel workItemId="wi-1" />);
    await waitFor(() => expect(screen.getByText('Hello')).toBeInTheDocument());
    expect(screen.getByText('Hi there')).toBeInTheDocument();
  });

  it('sends message on form submit and shows optimistic message', async () => {
    render(<ChatPanel workItemId="wi-1" />);
    // Wait for WS to open
    await waitFor(() => expect(mockWs).not.toBeNull());
    act(() => { if (mockWs?.onopen) mockWs.onopen(); });

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'Test message' } });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() => expect(screen.getByText('Test message')).toBeInTheDocument());
    expect(mockWs?.send).toHaveBeenCalledWith(
      expect.stringContaining('Test message'),
    );
  });

  it('appends progress frames to assistant bubble', async () => {
    render(<ChatPanel workItemId="wi-1" />);
    await waitFor(() => expect(mockWs).not.toBeNull());
    act(() => { if (mockWs?.onopen) mockWs.onopen(); });

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'Question' } });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() => expect(screen.getByText('Question')).toBeInTheDocument());

    act(() => {
      mockWs?.onmessage?.({ data: JSON.stringify({ type: 'progress', content: 'Thinking' }) });
    });
    await waitFor(() => expect(screen.getByText(/Thinking/)).toBeInTheDocument());

    act(() => {
      mockWs?.onmessage?.({ data: JSON.stringify({ type: 'progress', content: ' more' }) });
    });
    await waitFor(() => expect(screen.getByText(/Thinking more/)).toBeInTheDocument());
  });

  it('finalizes message on response frame', async () => {
    render(<ChatPanel workItemId="wi-1" />);
    await waitFor(() => expect(mockWs).not.toBeNull());
    act(() => { if (mockWs?.onopen) mockWs.onopen(); });

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'Question' } });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() => expect(screen.getByText('Question')).toBeInTheDocument());

    act(() => {
      mockWs?.onmessage?.({ data: JSON.stringify({ type: 'progress', content: 'Final answer' }) });
    });
    act(() => {
      mockWs?.onmessage?.({ data: JSON.stringify({ type: 'response', content: 'Final answer', message_id: 'msg-2' }) });
    });

    // Textarea should be re-enabled after response
    await waitFor(() => {
      const textarea = screen.getByRole('textbox');
      expect(textarea).not.toBeDisabled();
    });
  });

  it('disables composer while streaming', async () => {
    render(<ChatPanel workItemId="wi-1" />);
    await waitFor(() => expect(mockWs).not.toBeNull());
    act(() => { if (mockWs?.onopen) mockWs.onopen(); });

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'Question' } });
    fireEvent.submit(textarea.closest('form')!);

    // After send, while waiting for response, composer should be disabled
    await waitFor(() => expect(screen.getByText('Question')).toBeInTheDocument());
    act(() => {
      mockWs?.onmessage?.({ data: JSON.stringify({ type: 'progress', content: 'Thinking...' }) });
    });

    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeDisabled();
  });

  it('shows error banner on WS error frame', async () => {
    render(<ChatPanel workItemId="wi-1" />);
    await waitFor(() => expect(mockWs).not.toBeNull());
    act(() => { if (mockWs?.onopen) mockWs.onopen(); });

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'Question' } });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() => expect(screen.getByText('Question')).toBeInTheDocument());

    act(() => {
      mockWs?.onmessage?.({ data: JSON.stringify({ type: 'error', code: 'DUNDUN_ERR', message: 'Something failed' }) });
    });

    await waitFor(() => expect(screen.getByText(/Something failed/)).toBeInTheDocument());
  });

  it('closes WebSocket on unmount', async () => {
    const { unmount } = render(<ChatPanel workItemId="wi-1" />);
    await waitFor(() => expect(mockWs).not.toBeNull());
    act(() => { if (mockWs?.onopen) mockWs.onopen(); });

    unmount();
    expect(mockWs?.close).toHaveBeenCalled();
  });
});
