'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useThread } from '@/hooks/work-item/use-thread';
import { useSections } from '@/hooks/work-item/use-sections';
import { useSplitView } from '@/components/detail/split-view-context';
import type { ConversationMessage, WsFrame, SuggestedSection, ConversationSignals } from '@/lib/types/conversation';
import type { PendingSuggestion, SplitViewContextValue } from '@/components/detail/split-view-context';
import type { Section } from '@/lib/types/specification';
import { cn } from '@/lib/utils';
import { Send, Loader2 } from 'lucide-react';

// Build WS URL: relative path upgraded to ws(s)://
function buildWsUrl(threadId: string): string {
  if (typeof window === 'undefined') return '';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${proto}//${host}/ws/conversations/${threadId}`;
}

// ---------------------------------------------------------------------------
// Pure helpers (unit-testable in isolation)
// ---------------------------------------------------------------------------

export interface OutboundFrame {
  type: 'message';
  content: string;
  context: { sections_snapshot: Record<string, string> };
}

/** Build the WS send frame from user text + current sections. */
export function buildOutboundFrame(text: string, sections: Section[]): OutboundFrame {
  const sections_snapshot: Record<string, string> = {};
  for (const s of sections) {
    sections_snapshot[s.section_type] = s.content;
  }
  return { type: 'message', content: text, context: { sections_snapshot } };
}

/**
 * Route incoming suggested_sections to the SplitViewContext.
 *
 * - Drops entries whose section_type is not in sectionsByType.
 * - Sets highlightedSectionId to the first resolvable section's id.
 */
export function routeSuggestedSections(
  signals: ConversationSignals,
  sectionsByType: Map<string, Section>,
  splitView: Pick<SplitViewContextValue, 'emitSuggestion' | 'setHighlightedSectionId'>,
): void {
  const list = signals.suggested_sections;
  if (!list || list.length === 0) return;

  let firstSectionId: string | null = null;

  for (const sug of list) {
    const section = sectionsByType.get(sug.section_type);
    if (!section) continue; // unknown section_type — drop silently

    const pending: PendingSuggestion = {
      section_type: sug.section_type,
      proposed_content: sug.proposed_content,
      rationale: sug.rationale,
      received_at: Date.now(),
    };
    splitView.emitSuggestion(pending);

    if (firstSectionId === null) {
      firstSectionId = section.id;
    }
  }

  if (firstSectionId !== null) {
    splitView.setHighlightedSectionId(firstSectionId);
  }
}

// ---------------------------------------------------------------------------

interface StreamingMessage {
  id: string | null;
  role: 'assistant';
  content: string;
}

interface ErrorBubble {
  code: string;
  message: string;
}

interface ChatPanelProps {
  workItemId: string;
}

export function ChatPanel({ workItemId }: ChatPanelProps) {
  const t = useTranslations('workspace.itemDetail.clarification');
  const { thread, messages: initialMessages, isLoading } = useThread(workItemId);
  const { sections } = useSections(workItemId);
  const splitView = useSplitView();

  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [streaming, setStreaming] = useState<StreamingMessage | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [errors, setErrors] = useState<ErrorBubble[]>([]);
  const [input, setInput] = useState('');

  // Keep a ref to sections so handleSend always uses latest without re-subscribing WS
  const sectionsRef = useRef<Section[]>(sections);
  useEffect(() => {
    sectionsRef.current = sections;
  }, [sections]);

  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  // Sync messages when history loads
  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming]);

  // WS lifecycle
  useEffect(() => {
    if (!thread) return;

    const ws = new WebSocket(buildWsUrl(thread.id));
    wsRef.current = ws;

    ws.onmessage = (event: MessageEvent<string>) => {
      if (!mounted.current) return;
      try {
        const frame = JSON.parse(event.data) as WsFrame;

        if (frame.type === 'progress') {
          setIsStreaming(true);
          setStreaming((prev) =>
            prev
              ? { ...prev, content: prev.content + frame.content }
              : { id: null, role: 'assistant', content: frame.content },
          );
        } else if (frame.type === 'response') {
          setIsStreaming(false);
          setStreaming(null);
          setMessages((prev) => [
            ...prev,
            {
              id: frame.message_id,
              role: 'assistant',
              content: frame.content,
              created_at: new Date().toISOString(),
            },
          ]);

          // EP-22: route suggested_sections to SplitViewContext
          if (frame.signals) {
            const sectionsByType = new Map(
              sectionsRef.current.map((s) => [s.section_type, s]),
            );
            routeSuggestedSections(frame.signals, sectionsByType, splitView);
          }
        } else if (frame.type === 'error') {
          setIsStreaming(false);
          setStreaming(null);
          setErrors((prev) => [...prev, { code: frame.code, message: frame.message }]);
        }
      } catch {
        // Malformed frame — ignore
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
    // splitView intentionally excluded — we don't want WS to reconnect on every context change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thread]);

  const handleSend = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const text = input.trim();
      if (!text || isStreaming || !wsRef.current) return;

      // Optimistic user message
      const optimistic: ConversationMessage = {
        id: `opt-${Date.now()}`,
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimistic]);
      setInput('');
      setIsStreaming(true);

      // EP-22: include sections_snapshot in outbound frame
      const frame = buildOutboundFrame(text, sectionsRef.current);
      wsRef.current.send(JSON.stringify(frame));
    },
    [input, isStreaming],
  );

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2 p-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-16 w-3/4" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  const allMessages = messages;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        {allMessages.length === 0 && !streaming && (
          <p className="text-sm text-muted-foreground text-center mt-8">{t('emptyChat')}</p>
        )}

        {allMessages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {streaming && (
          <div
            className={cn(
              'max-w-[80%] rounded-lg px-3 py-2 text-sm',
              'bg-muted self-start',
            )}
          >
            {streaming.content}
            <Loader2 className="inline ml-1 h-3 w-3 animate-spin" />
          </div>
        )}

        {/* Error bubbles */}
        {errors.map((err, i) => (
          <div key={i} className="rounded-lg px-3 py-2 text-sm bg-destructive/10 text-destructive self-start max-w-[80%]">
            {err.message}
          </div>
        ))}

        {isStreaming && !streaming && (
          <p className="text-xs text-muted-foreground">{t('typing')}</p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <form
        onSubmit={handleSend}
        className="border-t p-3 flex gap-2 items-end shrink-0"
      >
        <textarea
          className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm min-h-[40px] max-h-32 focus:outline-none focus:ring-2 focus:ring-ring"
          rows={1}
          placeholder={t('chatPlaceholder')}
          value={input}
          disabled={isStreaming}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              handleSend(e as unknown as React.FormEvent);
            }
          }}
          aria-label={t('chatPlaceholder')}
        />
        <Button
          type="submit"
          size="sm"
          aria-label={t('sendAria')}
          disabled={isStreaming || !input.trim()}
        >
          <Send className="h-4 w-4" />
          <span className="sr-only">{t('sendAria')}</span>
        </Button>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: ConversationMessage }) {
  const isUser = message.role === 'user';
  return (
    <div
      className={cn(
        'max-w-[80%] rounded-lg px-3 py-2 text-sm',
        isUser ? 'bg-primary text-primary-foreground self-end ml-auto' : 'bg-muted self-start',
      )}
    >
      {message.content}
    </div>
  );
}
