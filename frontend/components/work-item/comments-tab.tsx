'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { OwnerAvatar } from '@/components/domain/owner-avatar';
import { RelativeTime } from '@/components/domain/relative-time';
import { useComments } from '@/hooks/work-item/use-comments';
import type { Comment, CreateCommentRequest } from '@/lib/types/versions';

function actorDisplay(comment: Comment): string {
  if (comment.actor_type === 'ai_suggestion') return 'AI';
  if (comment.actor_type === 'system') return 'System';
  return comment.actor_id ?? 'Unknown';
}

interface CommentFormProps {
  onSubmit: (req: CreateCommentRequest) => Promise<void>;
  parentCommentId?: string | null;
  onCancel?: () => void;
  placeholder?: string;
}

function CommentForm({ onSubmit, parentCommentId, onCancel, placeholder }: CommentFormProps) {
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit({ body: body.trim(), parent_comment_id: parentCommentId ?? null });
      setBody('');
      onCancel?.();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <Textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder={placeholder ?? 'Escribe un comentario…'}
        disabled={submitting}
        rows={3}
        aria-label="Comentario"
        className="resize-none text-sm"
      />
      <div className="flex items-center gap-2 justify-end">
        {onCancel && (
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            Cancelar
          </Button>
        )}
        <Button type="submit" size="sm" disabled={submitting || !body.trim()}>
          {submitting ? 'Enviando…' : 'Comentar'}
        </Button>
      </div>
    </form>
  );
}

interface CommentItemProps {
  comment: Comment;
  onReply: (req: CreateCommentRequest) => Promise<void>;
  isReply?: boolean;
}

function CommentItem({ comment, onReply, isReply = false }: CommentItemProps) {
  const [replying, setReplying] = useState(false);
  const display = actorDisplay(comment);

  return (
    <div className={isReply ? 'pl-10' : undefined}>
      <div className="flex gap-3">
        <OwnerAvatar
          name={display}
          size="sm"
          className="shrink-0 mt-0.5"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-medium text-foreground">{display}</span>
            <RelativeTime iso={comment.created_at} />
            {comment.anchor_status === 'orphaned' && (
              <span
                role="status"
                className="text-xs px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-900 border border-yellow-300"
              >
                Anchor perdido
              </span>
            )}
          </div>
          <p className="text-sm text-foreground mt-1 whitespace-pre-wrap">
            {comment.deleted_at ? (
              <span className="italic text-muted-foreground">[eliminado]</span>
            ) : (
              comment.body
            )}
          </p>
          {!isReply && !comment.deleted_at && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setReplying((v) => !v)}
              className="mt-1 h-6 px-1 text-xs text-muted-foreground"
              aria-expanded={replying}
            >
              Responder
            </Button>
          )}
          {replying && (
            <div className="mt-2">
              <CommentForm
                onSubmit={onReply}
                parentCommentId={comment.id}
                onCancel={() => setReplying(false)}
                placeholder="Escribe una respuesta…"
              />
            </div>
          )}
        </div>
      </div>

      {(comment.replies?.length ?? 0) > 0 && (
        <div className="mt-3 flex flex-col gap-3">
          {comment.replies?.map((reply) => (
            <CommentItem key={reply.id} comment={reply} onReply={onReply} isReply />
          ))}
        </div>
      )}
    </div>
  );
}

interface CommentsTabProps {
  workItemId: string;
}

export function CommentsTab({ workItemId }: CommentsTabProps) {
  const { comments, isLoading, addComment } = useComments(workItemId);

  return (
    <div className="flex flex-col gap-6">
      {isLoading ? (
        Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex gap-3">
            <Skeleton className="h-8 w-8 rounded-full shrink-0" />
            <div className="flex-1 flex flex-col gap-1.5">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-12 w-full" />
            </div>
          </div>
        ))
      ) : (
        <>
          <div className="flex flex-col gap-5">
            {comments.length === 0 ? (
              <p className="text-sm text-muted-foreground">Sin comentarios todavía.</p>
            ) : (
              comments.map((comment) => (
                <CommentItem key={comment.id} comment={comment} onReply={addComment} />
              ))
            )}
          </div>

          <div className="border-t border-border pt-4">
            <h4 className="text-sm font-medium text-foreground mb-3">Añadir comentario</h4>
            <CommentForm onSubmit={addComment} />
          </div>
        </>
      )}
    </div>
  );
}
