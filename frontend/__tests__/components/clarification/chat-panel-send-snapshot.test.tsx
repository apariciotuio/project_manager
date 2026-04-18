import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { ChatPanel } from '@/components/clarification/chat-panel';
import { buildOutboundFrame } from '@/components/clarification/chat-panel';
import type { Section } from '@/lib/types/specification';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

// MockWebSocket
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
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: MockWsListener | null = null;
  onerror: ((e: Event) => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  constructor(url: string) {
    this.url = url;
    mockWs = this as unknown as MockWs;
  }
}

const BASE = 'http://localhost';

const SECTION_PROBLEM: Section = {
  id: 'sec-1',
  work_item_id: 'wi-1',
  section_type: 'problem_statement',
  content: 'Current problem text',
  display_order: 1,
  is_required: true,
  generation_source: 'manual',
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  created_by: 'user-1',
  updated_by: 'user-1',
};

function setupHandlers(sections: Section[] = [SECTION_PROBLEM]) {
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
            created_at: '2026-04-18T00:00:00Z',
          },
        ],
      }),
    ),
    http.get(`${BASE}/api/v1/threads/thread-1/history`, () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get(`${BASE}/api/v1/work-items/wi-1/specification`, () =>
      HttpResponse.json({ data: { work_item_id: 'wi-1', sections } }),
    ),
  );
}

// ---------------------------------------------------------------------------
// Pure helper unit tests
// ---------------------------------------------------------------------------

describe('buildOutboundFrame', () => {
  it('snapshot present and keyed by section_type', () => {
    const sections: Section[] = [
      { ...SECTION_PROBLEM },
      { ...SECTION_PROBLEM, id: 'sec-2', section_type: 'acceptance_criteria', content: 'AC text' },
    ];
    const frame = buildOutboundFrame('hello', sections);

    expect(frame.type).toBe('message');
    expect(frame.content).toBe('hello');
    expect(frame.context.sections_snapshot).toEqual({
      problem_statement: 'Current problem text',
      acceptance_criteria: 'AC text',
    });
  });

  it('empty sections list → snapshot is {} (object, not absent)', () => {
    const frame = buildOutboundFrame('hello', []);
    expect(frame.context.sections_snapshot).toEqual({});
    expect(frame.context).toHaveProperty('sections_snapshot');
  });

  it('frame shape is { type, content, context: { sections_snapshot } }', () => {
    const frame = buildOutboundFrame('text', [SECTION_PROBLEM]);
    expect(frame).toMatchObject({
      type: 'message',
      content: 'text',
      context: { sections_snapshot: expect.any(Object) },
    });
  });
});

// ---------------------------------------------------------------------------
// Integration: ChatPanel sends snapshot on send
// ---------------------------------------------------------------------------

describe('ChatPanel outbound sections_snapshot', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    mockWs = null;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('WS send payload contains context.sections_snapshot keyed by section_type', async () => {
    setupHandlers([SECTION_PROBLEM]);
    render(<ChatPanel workItemId="wi-1" />);
    await waitFor(() => expect(mockWs).not.toBeNull());
    // Wait for sections to load
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument());

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'My question' } });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() => expect(mockWs?.send).toHaveBeenCalled());

    const sentRaw = mockWs!.send.mock.calls[0][0] as string;
    const sent = JSON.parse(sentRaw);
    expect(sent.type).toBe('message');
    expect(sent.content).toBe('My question');
    expect(sent.context).toBeDefined();
    expect(sent.context.sections_snapshot).toBeDefined();
    expect(sent.context.sections_snapshot).toHaveProperty('problem_statement');
  });
});
