'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { ChatPanel } from '@/components/clarification/chat-panel';
import { SplitViewContext } from './split-view-context';
import type { PendingSuggestion } from './split-view-context';

const LS_WIDTH_KEY = 'split-view:chat-width';
const DEFAULT_WIDTH = 40; // percent
const MIN_WIDTH = 20; // percent
const MAX_WIDTH = 70; // percent
const KEYBOARD_STEP = 5; // percent

function clamp(val: number, min: number, max: number): number {
  return Math.min(Math.max(val, min), max);
}

function readPersistedWidth(): number {
  try {
    const stored = localStorage.getItem(LS_WIDTH_KEY);
    if (stored !== null) {
      const parsed = parseFloat(stored);
      if (!isNaN(parsed)) return clamp(parsed, MIN_WIDTH, MAX_WIDTH);
    }
  } catch {
    // SSR or storage unavailable
  }
  return DEFAULT_WIDTH;
}

function collapseKey(workItemId: string): string {
  return `split-view:chat-collapsed:${workItemId}`;
}

function useCollapsedPersistence(workItemId: string) {
  const [collapsed, setCollapsed] = useState<boolean>(false);

  // Read on mount (and when workItemId changes)
  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(collapseKey(workItemId)) === '1');
    } catch {
      setCollapsed(false);
    }
  }, [workItemId]);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        if (next) {
          localStorage.setItem(collapseKey(workItemId), '1');
        } else {
          localStorage.removeItem(collapseKey(workItemId));
        }
      } catch {
        // ignore
      }
      return next;
    });
  }, [workItemId]);

  return { collapsed, toggle };
}

export interface WorkItemDetailLayoutProps {
  workItemId: string;
  children: React.ReactNode;
}

export function WorkItemDetailLayout({
  workItemId,
  children,
}: WorkItemDetailLayoutProps) {
  const t = useTranslations('workspace.itemDetail.splitView');

  // Responsive: detect mobile on client
  const [isMobile, setIsMobile] = useState(false);
  const [mobileTab, setMobileTab] = useState<'chat' | 'content'>('chat');
  const [chatWidthPct, setChatWidthPct] = useState<number>(DEFAULT_WIDTH);
  const [highlightedSectionId, setHighlightedSectionId] = useState<string | null>(null);
  const [pendingSuggestions, setPendingSuggestions] = useState<Record<string, PendingSuggestion>>({});

  const { collapsed, toggle: toggleCollapsed } = useCollapsedPersistence(workItemId);

  const emitSuggestion = useCallback((sug: PendingSuggestion) => {
    setPendingSuggestions((prev) => ({ ...prev, [sug.section_type]: sug }));
  }, []);

  const clearSuggestion = useCallback((section_type: string) => {
    setPendingSuggestions((prev) => {
      const next = { ...prev };
      delete next[section_type];
      return next;
    });
  }, []);

  const containerRef = useRef<HTMLDivElement>(null);

  // Determine mobile on mount and window resize
  useEffect(() => {
    function check() {
      setIsMobile(window.innerWidth < 768);
    }
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // Read persisted width on mount
  useEffect(() => {
    setChatWidthPct(readPersistedWidth());
  }, []);

  const persistWidth = useCallback((pct: number) => {
    try {
      localStorage.setItem(LS_WIDTH_KEY, String(pct));
    } catch {
      // ignore
    }
  }, []);

  // Drag logic
  const dragging = useRef(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(DEFAULT_WIDTH);

  const handleDividerMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      dragging.current = true;
      dragStartX.current = e.clientX;
      dragStartWidth.current = chatWidthPct;

      function onMouseMove(ev: MouseEvent) {
        if (!dragging.current || !containerRef.current) return;
        const containerWidth = containerRef.current.offsetWidth;
        const delta = ev.clientX - dragStartX.current;
        const deltaPct = (delta / containerWidth) * 100;
        const newWidth = clamp(dragStartWidth.current + deltaPct, MIN_WIDTH, MAX_WIDTH);
        setChatWidthPct(newWidth);
        persistWidth(newWidth);
      }

      function onMouseUp() {
        dragging.current = false;
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
      }

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    },
    [chatWidthPct, persistWidth],
  );

  const handleDividerKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowRight') {
        const next = clamp(chatWidthPct + KEYBOARD_STEP, MIN_WIDTH, MAX_WIDTH);
        setChatWidthPct(next);
        persistWidth(next);
      } else if (e.key === 'ArrowLeft') {
        const next = clamp(chatWidthPct - KEYBOARD_STEP, MIN_WIDTH, MAX_WIDTH);
        setChatWidthPct(next);
        persistWidth(next);
      }
    },
    [chatWidthPct, persistWidth],
  );

  const contextValue = {
    highlightedSectionId,
    setHighlightedSectionId,
    pendingSuggestions,
    emitSuggestion,
    clearSuggestion,
  };

  if (isMobile) {
    return (
      <SplitViewContext.Provider value={contextValue}>
        <div className="flex flex-col h-full min-h-0">
          {/* Tab switcher */}
          <div role="tablist" className="flex border-b shrink-0">
            <button
              role="tab"
              aria-selected={mobileTab === 'chat'}
              aria-controls="mobile-chat-panel"
              className={`flex-1 py-2 text-sm font-medium ${mobileTab === 'chat' ? 'border-b-2 border-primary text-primary' : 'text-muted-foreground'}`}
              onClick={() => setMobileTab('chat')}
            >
              {t('chatTab')}
            </button>
            <button
              role="tab"
              aria-selected={mobileTab === 'content'}
              aria-controls="mobile-content-panel"
              className={`flex-1 py-2 text-sm font-medium ${mobileTab === 'content' ? 'border-b-2 border-primary text-primary' : 'text-muted-foreground'}`}
              onClick={() => setMobileTab('content')}
            >
              {t('contentTab')}
            </button>
          </div>

          {/* Chat panel */}
          <div
            id="mobile-chat-panel"
            role="tabpanel"
            hidden={mobileTab !== 'chat'}
            className="flex-1 min-h-0 overflow-hidden"
            style={{ display: mobileTab === 'chat' ? undefined : 'none' }}
          >
            <ChatPanel workItemId={workItemId} />
          </div>

          {/* Content panel */}
          <div
            id="mobile-content-panel"
            role="tabpanel"
            hidden={mobileTab !== 'content'}
            className="flex-1 min-h-0 overflow-auto"
            style={{ display: mobileTab === 'content' ? undefined : 'none' }}
          >
            {children}
          </div>
        </div>
      </SplitViewContext.Provider>
    );
  }

  // Desktop split view
  return (
    <SplitViewContext.Provider value={contextValue}>
      <div ref={containerRef} className="flex h-full min-h-0" style={{ minHeight: '400px' }}>
        {/* Left: Chat panel — hidden when collapsed */}
        <div
          className="flex flex-col min-h-0 overflow-hidden"
          data-collapsed={collapsed ? 'true' : 'false'}
          style={{
            width: collapsed ? 0 : `${chatWidthPct}%`,
            minWidth: collapsed ? 0 : '280px',
            display: collapsed ? 'none' : undefined,
          }}
        >
          <ChatPanel workItemId={workItemId} />
        </div>

        {/* Collapse/expand toggle button */}
        <button
          type="button"
          data-testid="collapse-chat-btn"
          aria-label={collapsed ? t('expandChatAria') : t('collapseChatAria')}
          aria-expanded={!collapsed}
          onClick={toggleCollapsed}
          className="shrink-0 flex items-center justify-center w-5 bg-muted hover:bg-muted/80 border-x border-border text-muted-foreground focus:outline-none focus-visible:ring-2"
        >
          {collapsed ? '›' : '‹'}
        </button>

        {/* Resizable divider — only when expanded */}
        {!collapsed && (
          <ResizableDivider
            onMouseDown={handleDividerMouseDown}
            onKeyDown={handleDividerKeyDown}
            label={t('resizeAria')}
          />
        )}

        {/* Right: Content panel */}
        <div className="flex-1 min-h-0 overflow-auto">
          {children}
        </div>
      </div>
    </SplitViewContext.Provider>
  );
}

interface ResizableDividerProps {
  onMouseDown: (e: React.MouseEvent) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  label: string;
}

function ResizableDivider({ onMouseDown, onKeyDown, label }: ResizableDividerProps) {
  return (
    <div
      role="separator"
      aria-label={label}
      data-testid="resize-divider"
      tabIndex={0}
      className="w-1 bg-border hover:bg-primary/20 cursor-col-resize shrink-0 focus:outline-none focus:bg-primary/30"
      onMouseDown={onMouseDown}
      onKeyDown={onKeyDown}
    />
  );
}
