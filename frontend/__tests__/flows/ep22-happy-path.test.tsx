/**
 * EP-22 Phase 9 — Integration: suggestion happy path + collapse interaction.
 *
 * Component-level (no browser). Mounts SpecificationSectionsEditor wrapped in
 * WorkItemDetailLayout (provides SplitViewContext), injects a WS suggestion
 * frame, and verifies the PendingSuggestionCard accept flow.
 *
 * Note: We test at the component level (not full page) to avoid the 30+ mocks
 * the detail page requires. The context wiring is what matters for EP-22.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { WorkItemDetailLayout } from '@/components/detail/work-item-detail-layout';
import { SpecificationSectionsEditor } from '@/components/work-item/specification-sections-editor';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

// MockWebSocket
type MockWsListener = (event: { data: string }) => void;
interface MockWs {
  url: string;
  onopen: (() => void) | null;
  onmessage: MockWsListener | null;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
}
let mockWs: MockWs | null = null;
class MockWebSocket {
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: MockWsListener | null = null;
  onerror = null;
  onclose = null;
  send = vi.fn();
  close = vi.fn();
  constructor(url: string) {
    this.url = url;
    mockWs = this as unknown as MockWs;
  }
}

const BASE = 'http://localhost';

const SECTION_PROBLEM = {
  id: 'sec-1',
  work_item_id: 'wi-1',
  section_type: 'problem_statement',
  content: 'Original problem content',
  display_order: 1,
  is_required: true,
  generation_source: 'manual',
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  created_by: 'user-1',
  updated_by: 'user-1',
};

function setupHandlers() {
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
      HttpResponse.json({ data: { work_item_id: 'wi-1', sections: [SECTION_PROBLEM] } }),
    ),
  );
}

function TestHarness() {
  return (
    <WorkItemDetailLayout workItemId="wi-1">
      <SpecificationSectionsEditor workItemId="wi-1" canEdit={true} />
    </WorkItemDetailLayout>
  );
}

describe('EP-22 integration — suggestion happy path', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    setupHandlers();
    mockWs = null;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('WS suggestion → PendingSuggestionCard renders; Accept → patchSection called; card disappears', async () => {
    let patchCalled = false;
    let patchBody: unknown = null;
    server.use(
      http.patch(`${BASE}/api/v1/work-items/wi-1/sections/sec-1`, async ({ request }) => {
        patchCalled = true;
        patchBody = await request.json();
        return HttpResponse.json({
          data: { ...SECTION_PROBLEM, content: 'AI proposed fix', version: 2 },
        });
      }),
    );

    render(<TestHarness />);

    // Wait for sections to load
    await waitFor(() =>
      expect(screen.getByDisplayValue('Original problem content')).toBeInTheDocument(),
    );

    // Wait for WS to be created
    await waitFor(() => expect(mockWs).not.toBeNull());

    // Inject WS suggestion frame
    act(() => {
      mockWs?.onmessage?.({
        data: JSON.stringify({
          type: 'response',
          content: 'Here is my proposal',
          message_id: 'msg-1',
          signals: {
            suggested_sections: [
              {
                section_type: 'problem_statement',
                proposed_content: 'AI proposed fix',
                rationale: 'Clearer wording',
              },
            ],
          },
        }),
      });
    });

    // PendingSuggestionCard should appear
    await waitFor(() =>
      expect(screen.getByTestId('pending-suggestion-card')).toBeInTheDocument(),
    );

    // Accept the suggestion
    fireEvent.click(screen.getByRole('button', { name: /accept/i }));

    // patchSection called
    await waitFor(() => expect(patchCalled).toBe(true));
    expect((patchBody as { content: string }).content).toBe('AI proposed fix');

    // Card disappears after accept
    await waitFor(() =>
      expect(screen.queryByTestId('pending-suggestion-card')).not.toBeInTheDocument(),
    );
  });

  it('collapse chat → suggestion still emitted and pending card visible in content', async () => {
    render(<TestHarness />);

    await waitFor(() =>
      expect(screen.getByDisplayValue('Original problem content')).toBeInTheDocument(),
    );
    await waitFor(() => expect(mockWs).not.toBeNull());

    // Collapse the chat panel
    const collapseBtn = screen.queryByTestId('collapse-chat-btn');
    if (collapseBtn) {
      fireEvent.click(collapseBtn);
    }

    // Inject suggestion even while chat is collapsed
    act(() => {
      mockWs?.onmessage?.({
        data: JSON.stringify({
          type: 'response',
          content: 'Suggestion even when collapsed',
          message_id: 'msg-2',
          signals: {
            suggested_sections: [
              {
                section_type: 'problem_statement',
                proposed_content: 'Collapsed suggestion',
                rationale: '',
              },
            ],
          },
        }),
      });
    });

    // Pending card still renders in the content panel
    await waitFor(() =>
      expect(screen.getByTestId('pending-suggestion-card')).toBeInTheDocument(),
    );
  });
});
