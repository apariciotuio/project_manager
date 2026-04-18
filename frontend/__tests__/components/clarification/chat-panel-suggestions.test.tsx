import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { ChatPanel } from '@/components/clarification/chat-panel';
import { SplitViewContext } from '@/components/detail/split-view-context';
import type { SplitViewContextValue, PendingSuggestion } from '@/components/detail/split-view-context';

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

function setupBaseHandlers() {
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
    // sections for snapshot — two known sections
    http.get(`${BASE}/api/v1/work-items/wi-1/specification`, () =>
      HttpResponse.json({
        data: {
          work_item_id: 'wi-1',
          sections: [
            {
              id: 'sec-1',
              work_item_id: 'wi-1',
              section_type: 'problem_statement',
              content: 'existing content',
              display_order: 1,
              is_required: true,
              generation_source: 'manual',
              version: 1,
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              created_by: 'user-1',
              updated_by: 'user-1',
            },
            {
              id: 'sec-2',
              work_item_id: 'wi-1',
              section_type: 'acceptance_criteria',
              content: '',
              display_order: 2,
              is_required: true,
              generation_source: 'manual',
              version: 1,
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              created_by: 'user-1',
              updated_by: 'user-1',
            },
          ],
        },
      }),
    ),
  );
}

function buildContext(overrides: Partial<SplitViewContextValue> = {}): SplitViewContextValue {
  return {
    highlightedSectionId: null,
    setHighlightedSectionId: vi.fn(),
    pendingSuggestions: {},
    emitSuggestion: vi.fn(),
    clearSuggestion: vi.fn(),
    ...overrides,
  };
}

function renderWithContext(ctx: SplitViewContextValue) {
  return render(
    <SplitViewContext.Provider value={ctx}>
      <ChatPanel workItemId="wi-1" />
    </SplitViewContext.Provider>,
  );
}

describe('ChatPanel suggestion interception', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    setupBaseHandlers();
    mockWs = null;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('response frame with one valid suggestion → emitSuggestion called once with correct shape', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: JSON.stringify({
          type: 'response',
          content: 'Here is my suggestion',
          message_id: 'msg-1',
          signals: {
            suggested_sections: [
              {
                section_type: 'problem_statement',
                proposed_content: 'New problem content',
                rationale: 'Because it was unclear',
              },
            ],
          },
        }),
      });
    });

    expect(ctx.emitSuggestion).toHaveBeenCalledTimes(1);
    expect(ctx.emitSuggestion).toHaveBeenCalledWith(
      expect.objectContaining({
        section_type: 'problem_statement',
        proposed_content: 'New problem content',
        rationale: 'Because it was unclear',
      }),
    );
  });

  it('response frame with multiple suggestions → emitSuggestion called once per entry', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: JSON.stringify({
          type: 'response',
          content: 'Here are suggestions',
          message_id: 'msg-2',
          signals: {
            suggested_sections: [
              { section_type: 'problem_statement', proposed_content: 'A', rationale: 'r1' },
              { section_type: 'acceptance_criteria', proposed_content: 'B', rationale: 'r2' },
            ],
          },
        }),
      });
    });

    expect(ctx.emitSuggestion).toHaveBeenCalledTimes(2);
  });

  it('response frame with suggested_sections absent → no emit', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: JSON.stringify({
          type: 'response',
          content: 'plain answer',
          message_id: 'msg-3',
          // no signals
        }),
      });
    });

    expect(ctx.emitSuggestion).not.toHaveBeenCalled();
  });

  it('response frame with suggested_sections empty array → no emit', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: JSON.stringify({
          type: 'response',
          content: 'plain answer',
          message_id: 'msg-4',
          signals: { suggested_sections: [] },
        }),
      });
    });

    expect(ctx.emitSuggestion).not.toHaveBeenCalled();
  });

  it('unknown section_type not in sections cache → dropped silently, no emit for it', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: JSON.stringify({
          type: 'response',
          content: 'answer',
          message_id: 'msg-5',
          signals: {
            suggested_sections: [
              // unknown_xyz is not in the sections (only problem_statement is)
              { section_type: 'unknown_xyz', proposed_content: 'Dropped', rationale: '' },
              // problem_statement IS known — should emit
              { section_type: 'problem_statement', proposed_content: 'Valid', rationale: 'ok' },
            ],
          },
        }),
      });
    });

    expect(ctx.emitSuggestion).toHaveBeenCalledTimes(1);
    expect(ctx.emitSuggestion).toHaveBeenCalledWith(
      expect.objectContaining({ section_type: 'problem_statement' }),
    );
  });

  it('highlightedSectionId set to the first suggestion\'s section id', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: JSON.stringify({
          type: 'response',
          content: 'answer',
          message_id: 'msg-6',
          signals: {
            suggested_sections: [
              { section_type: 'problem_statement', proposed_content: 'P', rationale: '' },
            ],
          },
        }),
      });
    });

    // First suggestion maps to sec-1 (problem_statement → sec-1)
    expect(ctx.setHighlightedSectionId).toHaveBeenCalledWith('sec-1');
  });
});
