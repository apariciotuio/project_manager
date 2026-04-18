/**
 * EP-22 Phase 8 — Primer message UX verification (US-221).
 *
 * The `original_input` is sent as a real user message to Dundun via the BE
 * subscriber (EP-22-full). On the FE, it arrives in the thread history as a
 * normal { role: "user", content: "..." } entry. These tests confirm there is
 * no accidental branding regression — the message renders as a plain user
 * bubble with no "(primer)" or "(system)" label.
 *
 * NO FE code change expected (design §8.1) — tests are verification only.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { ChatPanel } from '@/components/clarification/chat-panel';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const BASE = 'http://localhost';

class MockWebSocket {
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  constructor(url: string) {
    this.url = url;
  }
}

function setupThreadHandler(messages: unknown[] = []) {
  server.use(
    http.get(`${BASE}/api/v1/threads`, () =>
      HttpResponse.json({
        data: [
          {
            id: 'thread-1',
            work_item_id: 'wi-primer',
            user_id: 'user-1',
            dundun_conversation_id: 'd-1',
            last_message_preview: null,
            last_message_at: null,
            created_at: '2026-04-17T00:00:00Z',
          },
        ],
      }),
    ),
    http.get(`${BASE}/api/v1/threads/thread-1/history`, () =>
      HttpResponse.json({ data: messages }),
    ),
  );
}

describe('ChatPanel — primer message UX (Phase 8)', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('original_input message (role=user) renders as a standard user bubble', async () => {
    setupThreadHandler([
      {
        id: 'msg-primer',
        role: 'user',
        content: 'Necesito una pantalla de login con MFA',
        created_at: '2026-04-17T09:00:00Z',
      },
    ]);

    render(<ChatPanel workItemId="wi-primer" />);

    await waitFor(() =>
      expect(
        screen.getByText('Necesito una pantalla de login con MFA'),
      ).toBeInTheDocument(),
    );
  });

  it('no "(primer)" or "(system)" label is rendered alongside the user message', async () => {
    setupThreadHandler([
      {
        id: 'msg-primer',
        role: 'user',
        content: 'Necesito una pantalla de login con MFA',
        created_at: '2026-04-17T09:00:00Z',
      },
    ]);

    render(<ChatPanel workItemId="wi-primer" />);

    await waitFor(() =>
      expect(
        screen.getByText('Necesito una pantalla de login con MFA'),
      ).toBeInTheDocument(),
    );

    // No primer/system label anywhere in the DOM
    expect(screen.queryByText(/primer/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/system/i)).not.toBeInTheDocument();
  });

  it('empty history renders the empty-state placeholder, not a bubble', async () => {
    setupThreadHandler([]);

    render(<ChatPanel workItemId="wi-primer" />);

    await waitFor(() =>
      expect(screen.getByText('emptyChat')).toBeInTheDocument(),
    );

    // Confirm no phantom bubble
    expect(screen.queryByText('Necesito una pantalla de login con MFA')).not.toBeInTheDocument();
  });
});
