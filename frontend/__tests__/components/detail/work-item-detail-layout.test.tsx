import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { WorkItemDetailLayout } from '@/components/detail/work-item-detail-layout';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

// Mock ChatPanel so we don't need WS in these tests
vi.mock('@/components/clarification/chat-panel', () => ({
  ChatPanel: ({ workItemId }: { workItemId: string }) => (
    <div data-testid="chat-panel" data-work-item-id={workItemId}>
      ChatPanel
    </div>
  ),
}));

const BASE = 'http://localhost';

function setupThreadHandler() {
  server.use(
    http.get(`${BASE}/api/v1/threads`, () =>
      HttpResponse.json({ data: [] }),
    ),
  );
}

beforeEach(() => {
  setupThreadHandler();
  // Clear localStorage
  localStorage.clear();
  // Reset viewport to desktop default
  Object.defineProperty(window, 'innerWidth', { writable: true, value: 1024 });
});

afterEach(() => {
  localStorage.clear();
});

function renderLayout(props?: Partial<React.ComponentProps<typeof WorkItemDetailLayout>>) {
  return render(
    <WorkItemDetailLayout
      workItemId="wi-1"
      {...props}
    >
      <div data-testid="content-panel">Content Panel</div>
    </WorkItemDetailLayout>,
  );
}

describe('WorkItemDetailLayout — desktop (≥768px)', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1024 });
  });

  it('renders ChatPanel and content panel simultaneously on desktop', () => {
    renderLayout();
    expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
    expect(screen.getByTestId('content-panel')).toBeInTheDocument();
  });

  it('renders resizable divider on desktop', () => {
    renderLayout();
    expect(screen.getByTestId('resize-divider')).toBeInTheDocument();
  });

  it('persists width to localStorage after drag', () => {
    renderLayout();
    const divider = screen.getByTestId('resize-divider');

    fireEvent.mouseDown(divider, { clientX: 400 });
    fireEvent.mouseMove(document, { clientX: 500 });
    fireEvent.mouseUp(document);

    expect(localStorage.getItem('split-view:chat-width')).not.toBeNull();
  });

  it('reads persisted width from localStorage on mount', () => {
    localStorage.setItem('split-view:chat-width', '50');
    renderLayout();
    // The chat panel container should reflect saved width
    const chatContainer = screen.getByTestId('chat-panel').parentElement;
    expect(chatContainer).toBeTruthy();
    // Width check via style attribute — stored as percentage
    const style = chatContainer?.getAttribute('style') ?? '';
    expect(style).toContain('50');
  });
});

describe('WorkItemDetailLayout — mobile (<768px)', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 375 });
  });

  it('renders tab switcher on mobile', () => {
    renderLayout();
    expect(screen.getByRole('tab', { name: /chat/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /content/i })).toBeInTheDocument();
  });

  it('default active tab is Chat — shows ChatPanel, hides content panel', () => {
    renderLayout();
    expect(screen.getByTestId('chat-panel')).toBeVisible();
    expect(screen.queryByTestId('content-panel')).not.toBeVisible();
  });

  it('Content tab switches to content panel', () => {
    renderLayout();
    fireEvent.click(screen.getByRole('tab', { name: /content/i }));
    expect(screen.getByTestId('content-panel')).toBeVisible();
    expect(screen.queryByTestId('chat-panel')).not.toBeVisible();
  });

  it('does not render resizable divider on mobile', () => {
    renderLayout();
    expect(screen.queryByLabelText(/resize panels/i)).not.toBeInTheDocument();
  });
});

describe('ResizableDivider — keyboard support', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1024 });
  });

  it('ArrowRight increases chat width by 5%', () => {
    renderLayout();
    const divider = screen.getByTestId('resize-divider');

    fireEvent.focus(divider);
    fireEvent.keyDown(divider, { key: 'ArrowRight' });

    // Width stored in localStorage
    const stored = localStorage.getItem('split-view:chat-width');
    const width = stored !== null ? parseFloat(stored) : 40;
    expect(width).toBeGreaterThan(40);
  });

  it('ArrowLeft decreases chat width by 5%', () => {
    localStorage.setItem('split-view:chat-width', '50');
    renderLayout();
    const divider = screen.getByTestId('resize-divider');

    fireEvent.focus(divider);
    fireEvent.keyDown(divider, { key: 'ArrowLeft' });

    const stored = localStorage.getItem('split-view:chat-width');
    const width = stored !== null ? parseFloat(stored) : 50;
    expect(width).toBeLessThan(50);
  });
});
