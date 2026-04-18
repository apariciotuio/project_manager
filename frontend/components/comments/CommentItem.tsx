'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { OwnerAvatar } from '@/components/domain/owner-avatar';
import { RelativeTime } from '@/components/domain/relative-time';
import { cn } from '@/lib/utils';
import type { Comment } from '@/lib/types/versions';

export interface CommentItemProps {
  comment: Comment;
  currentUserId: string;
  authorName?: string | null;
  onEdit: (id: string, body: string) => void;
  onDelete: (id: string) => void;
  onReply: (parentId: string, body: string) => void;
  isReply?: boolean;
}

export function CommentItem({
  comment,
  currentUserId,
  authorName,
  onEdit,
  onDelete,
  onReply,
  isReply = false,
}: CommentItemProps) {
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState(comment.body);
  const [replying, setReplying] = useState(false);
  const [replyBody, setReplyBody] = useState('');

  const isOwn = comment.actor_id === currentUserId;
  const isAI = comment.actor_type === 'ai_suggestion';
  const isDeleted = comment.deleted_at !== null;
  const isOrphaned = comment.anchor_status === 'orphaned' && comment.anchor_section_id !== null;

  const displayName = authorName ?? comment.actor_id ?? 'Unknown';

  function handleEditSubmit() {
    const trimmed = editBody.trim();
    if (!trimmed) return;
    onEdit(comment.id, trimmed);
    setEditing(false);
  }

  function handleReplySubmit() {
    const trimmed = replyBody.trim();
    if (!trimmed) return;
    onReply(comment.id, trimmed);
    setReplyBody('');
    setReplying(false);
  }

  return (
    <div data-testid={isReply ? 'comment-reply' : 'comment-item'}>
      {isOrphaned && (
        <span className="inline-flex items-center gap-1 rounded bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700 mb-1">
          Anchor text no longer found
        </span>
      )}

      <div className="flex gap-3">
        <OwnerAvatar
          name={isAI ? 'AI' : displayName}
          size="sm"
          className="shrink-0 mt-0.5"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-medium text-foreground">{displayName}</span>
            <RelativeTime iso={comment.created_at} />
            {comment.is_edited && (
              <span className="text-xs text-muted-foreground">(editado)</span>
            )}
          </div>

          {isDeleted ? (
            <p className={cn('text-sm text-muted-foreground mt-1 italic')}>[deleted]</p>
          ) : editing ? (
            <div className="mt-2 flex flex-col gap-2">
              <Textarea
                value={editBody}
                onChange={(e) => setEditBody(e.target.value)}
                rows={3}
                className="resize-none text-sm"
                aria-label="Editar comentario"
              />
              <div className="flex gap-2 justify-end">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => { setEditing(false); setEditBody(comment.body); }}
                >
                  Cancelar
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={!editBody.trim()}
                  onClick={handleEditSubmit}
                >
                  Guardar
                </Button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-foreground mt-1 whitespace-pre-wrap">{comment.body}</p>
          )}

          {!isDeleted && !editing && (
            <div className="mt-1 flex items-center gap-1">
              {!isReply && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setReplying((v) => !v)}
                  className="h-6 px-1 text-xs text-muted-foreground"
                  aria-expanded={replying}
                >
                  Responder
                </Button>
              )}
              {isOwn && !isAI && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => { setEditing(true); setEditBody(comment.body); }}
                  className="h-6 px-1 text-xs text-muted-foreground"
                  aria-label="Editar comentario"
                >
                  Editar
                </Button>
              )}
              {isOwn && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDelete(comment.id)}
                  className="h-6 px-1 text-xs text-destructive hover:text-destructive"
                  aria-label="Eliminar comentario"
                >
                  Eliminar
                </Button>
              )}
            </div>
          )}

          {replying && (
            <div className="mt-2 flex flex-col gap-2">
              <Textarea
                value={replyBody}
                onChange={(e) => setReplyBody(e.target.value)}
                placeholder="Escribe una respuesta…"
                rows={2}
                className="resize-none text-sm"
                aria-label="Responder comentario"
              />
              <div className="flex gap-2 justify-end">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => { setReplying(false); setReplyBody(''); }}
                >
                  Cancelar
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={!replyBody.trim()}
                  onClick={handleReplySubmit}
                >
                  Comentar
                </Button>
              </div>
            </div>
          )}
        </div>

        {(comment.replies?.length ?? 0) > 0 && !replying && (
          <Badge variant="secondary" className="self-start text-xs shrink-0">
            {comment.replies.length}
          </Badge>
        )}
      </div>
    </div>
  );
}
