/**
 * EP-22 v2 — ChatPanel kind-switch tests against real MorpheoResponse contract.
 * Frame shape: { type: 'response', response: '<JSON-string>', signals: { conversation_ended: bool } }
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { ChatPanel } from '@/components/clarification/chat-panel';
import { SplitViewContext } from '@/components/detail/split-view-context';
import type { SplitViewContextValue } from '@/components/detail/split-view-context';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

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
    http.get(`${BASE}/api/v1/work-items/wi-1/specification`, () =>
      HttpResponse.json({
        data: {
          work_item_id: 'wi-1',
          sections: [
            {
              id: 'sec-1',
              work_item_id: 'wi-1',
              section_type: 'objectives',
              content: 'existing objectives',
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
              section_type: 'scope',
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

/** Build a response WsFrame with given MorpheoResponse envelope. */
function responseFrame(envelope: unknown, conversationEnded = false) {
  return JSON.stringify({
    type: 'response',
    response: JSON.stringify(envelope),
    signals: { conversation_ended: conversationEnded },
  });
}

describe('ChatPanel kind-switch — question', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    setupBaseHandlers();
    mockWs = null;
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('question frame → ClarificationPrompt rendered, no emitSuggestion', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: responseFrame({
          kind: 'question',
          message: 'What is the target user?',
          clarifications: [{ field: 'target_user', question: 'B2C or B2B?' }],
        }),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId('clarification-prompt')).toBeInTheDocument(),
    );
    expect(ctx.emitSuggestion).not.toHaveBeenCalled();
  });

  it('question frame without clarifications → ClarificationPrompt still renders with message only', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: responseFrame({
          kind: 'question',
          message: 'Please clarify the scope.',
        }),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId('clarification-prompt')).toBeInTheDocument(),
    );
    expect(screen.getByText('Please clarify the scope.')).toBeInTheDocument();
  });
});

describe('ChatPanel kind-switch — section_suggestion', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    setupBaseHandlers();
    mockWs = null;
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('section_suggestion frame → emitSuggestion called per item, scroll triggered', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: responseFrame({
          kind: 'section_suggestion',
          message: 'Here are suggestions',
          suggested_sections: [
            { section_type: 'objectives', proposed_content: 'New objectives', rationale: 'clearer' },
            { section_type: 'scope', proposed_content: 'New scope', rationale: 'needed' },
          ],
        }),
      });
    });

    await waitFor(() => expect(ctx.emitSuggestion).toHaveBeenCalledTimes(2));
    expect(ctx.emitSuggestion).toHaveBeenCalledWith(
      expect.objectContaining({ section_type: 'objectives', proposed_content: 'New objectives', rationale: 'clearer' }),
    );
    expect(ctx.emitSuggestion).toHaveBeenCalledWith(
      expect.objectContaining({ section_type: 'scope', proposed_content: 'New scope' }),
    );
    // First section should be highlighted
    expect(ctx.setHighlightedSectionId).toHaveBeenCalledWith('sec-1');
  });

  it('section_suggestion with envelope.message → intro bubble rendered', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: responseFrame({
          kind: 'section_suggestion',
          message: 'I have some section proposals.',
          suggested_sections: [
            { section_type: 'objectives', proposed_content: 'Better objectives', rationale: '' },
          ],
        }),
      });
    });

    await waitFor(() =>
      expect(screen.getByText('I have some section proposals.')).toBeInTheDocument(),
    );
  });

  it('section_suggestion with coexisting clarifications → intro bubble + ClarificationPrompt', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: responseFrame({
          kind: 'section_suggestion',
          message: 'I suggested some sections and also have a question.',
          suggested_sections: [
            { section_type: 'objectives', proposed_content: 'Obj content', rationale: '' },
          ],
          clarifications: [{ field: 'rollback_plan', question: 'What is the rollback plan?' }],
        }),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId('clarification-prompt')).toBeInTheDocument(),
    );
    expect(screen.getByText('I suggested some sections and also have a question.')).toBeInTheDocument();
    expect(ctx.emitSuggestion).toHaveBeenCalledTimes(1);
  });
});

describe('ChatPanel kind-switch — po_review', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    setupBaseHandlers();
    mockWs = null;
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('po_review frame → PoReviewPanel rendered with score and verdict', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: responseFrame({
          kind: 'po_review',
          message: 'Review complete.',
          po_review: {
            score: 62,
            verdict: 'needs_work',
            agents_consulted: ['product', 'architect'],
            per_dimension: [
              {
                dimension: 'product',
                score: 55,
                verdict: 'needs_work',
                findings: [{ severity: 'high', title: 'Missing metric', description: 'No KPI defined.' }],
                missing_info: [{ field: 'success_metric', question: 'What is success?' }],
              },
            ],
            action_items: [
              { priority: 'critical', title: 'Add KPIs', description: 'Define measurable KPIs.', owner: 'PO' },
            ],
          },
          comments: ['Overall looks incomplete.'],
          clarifications: [],
        }),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId('po-review-panel')).toBeInTheDocument(),
    );
    // Score visible
    expect(screen.getByText('62')).toBeInTheDocument();
    // Verdict
    expect(screen.getByText(/needs_work/i)).toBeInTheDocument();
  });
});

describe('ChatPanel kind-switch — error', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    setupBaseHandlers();
    mockWs = null;
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('error frame → ChatErrorBanner rendered', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: responseFrame({ kind: 'error', message: 'synthesis_failed' }),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId('chat-error-banner')).toBeInTheDocument(),
    );
    expect(screen.getByText('synthesis_failed')).toBeInTheDocument();
  });
});

describe('ChatPanel kind-switch — malformed / invalid', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    setupBaseHandlers();
    mockWs = null;
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('malformed JSON in frame.response → ChatErrorBanner with malformed_response', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: JSON.stringify({
          type: 'response',
          response: '{not valid json',
          signals: { conversation_ended: false },
        }),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId('chat-error-banner')).toBeInTheDocument(),
    );
    expect(screen.getByText('malformed_response')).toBeInTheDocument();
  });

  it('invalid shape (unknown kind) → ChatErrorBanner with malformed_response', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: responseFrame({ kind: 'unknown_kind', message: 'something' }),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId('chat-error-banner')).toBeInTheDocument(),
    );
    expect(screen.getByText('malformed_response')).toBeInTheDocument();
  });

  it('valid JSON but missing required fields → ChatErrorBanner with malformed_response', async () => {
    const ctx = buildContext();
    renderWithContext(ctx);
    await waitFor(() => expect(mockWs).not.toBeNull());

    act(() => {
      mockWs?.onmessage?.({
        data: responseFrame({ kind: 'section_suggestion' /* missing suggested_sections */ }),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId('chat-error-banner')).toBeInTheDocument(),
    );
  });
});
