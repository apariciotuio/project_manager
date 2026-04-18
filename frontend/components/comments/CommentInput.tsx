'use client';

import { useState, useRef, useCallback, type KeyboardEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Paperclip } from 'lucide-react';

interface AnchorData {
  section_id: string;
  start: number;
  end: number;
  snapshot_text: string;
}

export interface CommentInputProps {
  onSubmit: (body: string, anchor?: AnchorData) => void | Promise<void>;
  placeholder?: string;
  initialBody?: string;
  anchor?: AnchorData;
  isLoading?: boolean;
  error?: string | null;
}

export function CommentInput({
  onSubmit,
  placeholder = 'Escribe un comentario…',
  initialBody = '',
  anchor,
  isLoading = false,
  error,
}: CommentInputProps) {
  const [body, setBody] = useState(initialBody);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isEmpty = !body.trim();

  const handleSubmit = useCallback(async () => {
    if (isEmpty || isLoading) return;
    const trimmed = body.trim();
    await onSubmit(trimmed, anchor);
    setBody('');
  }, [body, isEmpty, isLoading, onSubmit, anchor]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      void handleSubmit();
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Textarea
        ref={textareaRef}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isLoading}
        rows={3}
        aria-label="Comentario"
        className="resize-none text-sm"
      />

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="flex items-center gap-2 justify-end">
        {/* EP-16 attachment upload — not yet shipped, placeholder disabled */}
        {/* TODO(EP-16): wire upload flow when attachment API is available */}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled
          aria-label="Adjuntar archivo"
          className="text-muted-foreground"
        >
          <Paperclip className="h-4 w-4" aria-hidden />
        </Button>

        <Button
          type="button"
          size="sm"
          disabled={isEmpty || isLoading}
          onClick={() => void handleSubmit()}
        >
          {isLoading ? 'Enviando…' : 'Comentar'}
        </Button>
      </div>
    </div>
  );
}
