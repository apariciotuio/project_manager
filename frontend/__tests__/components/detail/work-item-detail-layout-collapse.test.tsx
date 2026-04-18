import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { WorkItemDetailLayout } from '@/components/detail/work-item-detail-layout';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock('@/components/clarification/chat-panel', () => ({
  ChatPanel: ({ workItemId }: { workItemId: string }) => (
    <div data-testid="chat-panel" data-work-item-id={workItemId}>
      ChatPanel
    </div>
  ),
}));

function collapseKey(id: string) {
  return `split-view:chat-collapsed:${id}`;
}

function renderLayout(workItemId = 'wi-1') {
  return render(
    <WorkItemDetailLayout workItemId={workItemId} threadId="thread-1">
      <div data-testid="content-panel">Content</div>
    </WorkItemDetailLayout>,
  );
}

describe('WorkItemDetailLayout — collapse persistence', () => {
  beforeEach(() => {
    // Force desktop viewport
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1024 });
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('collapse button is present on desktop', () => {
    renderLayout();
    expect(screen.getByTestId('collapse-chat-btn')).toBeInTheDocument();
  });

  it('click collapse → chat panel hidden, content expands', () => {
    renderLayout();
    const btn = screen.getByTestId('collapse-chat-btn');
    fireEvent.click(btn);
    const chatPanel = screen.getByTestId('chat-panel').parentElement;
    // The chat container should have display:none or hidden attribute when collapsed
    expect(
      chatPanel?.getAttribute('data-collapsed') === 'true' ||
        chatPanel?.style.display === 'none' ||
        chatPanel?.hidden === true,
    ).toBe(true);
  });

  it('persists collapsed state to localStorage with per-workItemId key', () => {
    renderLayout('wi-abc');
    const btn = screen.getByTestId('collapse-chat-btn');
    fireEvent.click(btn);
    expect(localStorage.getItem(collapseKey('wi-abc'))).toBe('1');
  });

  it('second mount with same workItemId starts collapsed', () => {
    localStorage.setItem(collapseKey('wi-abc'), '1');
    renderLayout('wi-abc');
    const chatPanel = screen.getByTestId('chat-panel').parentElement;
    expect(
      chatPanel?.getAttribute('data-collapsed') === 'true' ||
        chatPanel?.style.display === 'none' ||
        chatPanel?.hidden === true,
    ).toBe(true);
  });

  it('second mount with different workItemId starts expanded (not inheriting collapsed state)', () => {
    localStorage.setItem(collapseKey('wi-abc'), '1');
    renderLayout('wi-xyz');
    const chatPanel = screen.getByTestId('chat-panel').parentElement;
    // Should be expanded — data-collapsed not true, not hidden
    const isCollapsed =
      chatPanel?.getAttribute('data-collapsed') === 'true' ||
      chatPanel?.style.display === 'none' ||
      chatPanel?.hidden === true;
    expect(isCollapsed).toBe(false);
  });
});
