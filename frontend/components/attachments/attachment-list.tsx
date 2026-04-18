'use client';

import { useState } from 'react';
import { Trash2, FileDown } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { EmptyState } from '@/components/layout/empty-state';
import { useAttachments } from '@/hooks/work-item/use-attachments';
import type { AttachmentResponse } from '@/lib/types/attachment';

interface AttachmentListProps {
  workItemId: string;
  /** canEdit = owner of work item or superadmin — controls delete visibility */
  canEdit: boolean;
  currentUserId: string;
  isSuperadmin?: boolean;
}

interface DeleteDialogProps {
  attachment: AttachmentResponse | null;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}

function DeleteDialog({ attachment, onConfirm, onCancel, isDeleting }: DeleteDialogProps) {
  return (
    <Dialog open={attachment !== null} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete attachment</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Are you sure you want to delete{' '}
          <span className="font-medium text-foreground">{attachment?.filename}</span>?
          This action cannot be undone.
        </p>
        <DialogFooter>
          <Button variant="ghost" onClick={onCancel} disabled={isDeleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function canDelete(
  attachment: AttachmentResponse,
  currentUserId: string,
  isSuperadmin: boolean,
): boolean {
  return isSuperadmin || attachment.uploaded_by === currentUserId;
}

function AttachmentRow({
  attachment,
  currentUserId,
  isSuperadmin,
  onDeleteClick,
}: {
  attachment: AttachmentResponse;
  currentUserId: string;
  isSuperadmin: boolean;
  onDeleteClick: (a: AttachmentResponse) => void;
}) {
  const showDelete = canDelete(attachment, currentUserId, isSuperadmin);

  return (
    <li className="flex items-center justify-between gap-4 rounded-md border border-border px-4 py-3">
      <div className="flex items-center gap-3 min-w-0">
        <FileDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">{attachment.filename}</p>
          <p className="text-xs text-muted-foreground">
            {attachment.size_human_readable} &middot; {attachment.uploaded_by_name}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <a
          href={attachment.download_url}
          download={attachment.filename}
          className="text-xs text-primary hover:underline"
          aria-label={`Download ${attachment.filename}`}
        >
          Download
        </a>
        {showDelete && (
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Delete ${attachment.filename}`}
            onClick={() => onDeleteClick(attachment)}
            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
        )}
      </div>
    </li>
  );
}

export function AttachmentList({
  workItemId,
  currentUserId,
  isSuperadmin = false,
}: AttachmentListProps) {
  const { attachments, isLoading, error, deleteOne } = useAttachments(workItemId);
  const [pendingDelete, setPendingDelete] = useState<AttachmentResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  async function handleConfirmDelete() {
    if (!pendingDelete) return;
    setIsDeleting(true);
    try {
      await deleteOne(pendingDelete.id);
      setPendingDelete(null);
    } finally {
      setIsDeleting(false);
    }
  }

  if (isLoading) {
    return (
      <div role="status" aria-label="Loading attachments" className="flex flex-col gap-2">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <p role="alert" className="text-sm text-destructive">
        Error loading attachments: {error.message}
      </p>
    );
  }

  if (attachments.length === 0) {
    return (
      <EmptyState
        variant="custom"
        heading="No attachments"
        body="Files attached to this item will appear here."
      />
    );
  }

  return (
    <>
      <ul className="flex flex-col gap-2" aria-label="Attachments">
        {attachments.map((a) => (
          <AttachmentRow
            key={a.id}
            attachment={a}
            currentUserId={currentUserId}
            isSuperadmin={isSuperadmin}
            onDeleteClick={setPendingDelete}
          />
        ))}
      </ul>

      <DeleteDialog
        attachment={pendingDelete}
        onConfirm={() => void handleConfirmDelete()}
        onCancel={() => setPendingDelete(null)}
        isDeleting={isDeleting}
      />
    </>
  );
}
