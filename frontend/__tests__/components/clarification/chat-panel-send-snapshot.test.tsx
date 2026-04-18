import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { ChatPanel, buildOutboundFrame } from '@/components/clarification/chat-panel';
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
  it('snapshot is an array of { section_type, content, is_empty } per US-224', () => {
    const sections: Section[] = [
      { ...SECTION_PROBLEM },
      { ...SECTION_PROBLEM, id: 'sec-2', section_type: 'acceptance_criteria', content: 'AC text' },
    ];
    const frame = buildOutboundFrame('hello', sections);

    expect(frame.type).toBe('message');
    expect(frame.content).toBe('hello');
    expect(frame.context.sections_snapshot).toEqual([
      { section_type: 'problem_statement', content: 'Current problem text', is_empty: false },
      { section_type: 'acceptance_criteria', content: 'AC text', is_empty: false },
    ]);
  });

  it('empty sections list → snapshot is [] (array, not absent)', () => {
    const frame = buildOutboundFrame('hello', []);
    expect(frame.context.sections_snapshot).toEqual([]);
    expect(frame.context).toHaveProperty('sections_snapshot');
  });

  it('empty content section → is_empty is true', () => {
    const emptySection = { ...SECTION_PROBLEM, content: '' };
    const frame = buildOutboundFrame('text', [emptySection]);
    expect(frame.context.sections_snapshot[0]).toMatchObject({
      section_type: 'problem_statement',
      content: '',
      is_empty: true,
    });
  });

  it('whitespace-only content → is_empty is true', () => {
    const wsSection = { ...SECTION_PROBLEM, content: '   ' };
    const frame = buildOutboundFrame('text', [wsSection]);
    expect(frame.context.sections_snapshot[0]?.is_empty).toBe(true);
  });

  it('frame shape is { type, content, context: { sections_snapshot } }', () => {
    const frame = buildOutboundFrame('text', [SECTION_PROBLEM]);
    expect(frame).toMatchObject({
      type: 'message',
      content: 'text',
      context: { sections_snapshot: expect.any(Array) },
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

    const sentRaw = mockWs!.send.mock.calls[0]![0] as string;
    const sent = JSON.parse(sentRaw) as {
      type: string;
      content: string;
      context: {
        sections_snapshot: Array<{ section_type: string; content: string; is_empty: boolean }>;
      };
    };
    expect(sent.type).toBe('message');
    expect(sent.content).toBe('My question');
    expect(sent.context).toBeDefined();
    expect(Array.isArray(sent.context.sections_snapshot)).toBe(true);
    // EP-22 v2: array shape { section_type, content, is_empty }
    const item = sent.context.sections_snapshot[0];
    expect(item).toHaveProperty('section_type', 'problem_statement');
    expect(item).toHaveProperty('content');
    expect(item).toHaveProperty('is_empty');
  });
});
