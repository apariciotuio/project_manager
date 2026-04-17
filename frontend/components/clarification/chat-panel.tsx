'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useThread } from '@/hooks/work-item/use-thread';
import type { ConversationMessage, WsFrame } from '@/lib/types/conversation';
import { cn } from '@/lib/utils';
import { Send, Loader2 } from 'lucide-react';

// Build WS URL: relative path upgraded to ws(s)://
function buildWsUrl(threadId: string): string {
  if (typeof window === 'undefined') return '';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${proto}//${host}/ws/conversations/${threadId}`;
}

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

  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [streaming, setStreaming] = useState<StreamingMessage | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [errors, setErrors] = useState<ErrorBubble[]>([]);
  const [input, setInput] = useState('');

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

      wsRef.current.send(JSON.stringify({ type: 'message', content: text }));
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
