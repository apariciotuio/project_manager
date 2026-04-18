'use client';

import { useState, useRef, useCallback } from 'react';
import { UploadCloud } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';

const ALLOWED_MIME_TYPES = ['image/', 'application/pdf', 'text/plain'];
const MAX_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

function isMimeAllowed(type: string): boolean {
  return ALLOWED_MIME_TYPES.some((prefix) =>
    prefix.endsWith('/') ? type.startsWith(prefix) : type === prefix,
  );
}

interface ValidationError {
  type: 'size' | 'mime';
  message: string;
}

function validateFile(file: File): ValidationError | null {
  if (file.size > MAX_SIZE_BYTES) {
    return { type: 'size', message: `File too large — maximum 20 MB allowed.` };
  }
  if (!isMimeAllowed(file.type)) {
    return { type: 'mime', message: `File type not allowed. Accepted: images, PDF, plain text.` };
  }
  return null;
}

interface AttachmentDropZoneProps {
  disabled?: boolean;
  className?: string;
}

export function AttachmentDropZone({ disabled = false, className }: AttachmentDropZoneProps) {
  const { toast } = useToast();
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      setValidationError(null);

      const file = files[0];
      const error = validateFile(file!);
      if (error) {
        setValidationError(error.message);
        return;
      }

      // Valid file — upload is blocked, show informational toast
      toast({
        title: 'Upload not yet available — backend endpoint pending',
        description: `${file!.name} was selected but cannot be uploaded yet.`,
      });
    },
    [toast],
  );

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    if (disabled) return;
    e.preventDefault();
    setIsDragOver(true);
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    if (disabled) return;
    e.preventDefault();
    setIsDragOver(false);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    if (disabled) return;
    e.preventDefault();
    setIsDragOver(false);
    handleFiles(e.dataTransfer.files);
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    handleFiles(e.target.files);
    // Reset so the same file can be re-selected
    e.target.value = '';
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (disabled) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      inputRef.current?.click();
    }
  }

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <div
        data-testid="attachment-drop-zone"
        data-dragover={String(isDragOver)}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Drag and drop files or select file to attach"
        aria-disabled={String(disabled)}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onKeyDown={handleKeyDown}
        onClick={() => !disabled && inputRef.current?.click()}
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 text-center transition-colors cursor-pointer select-none',
          isDragOver && !disabled
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-muted-foreground/50',
          disabled && 'pointer-events-none opacity-50 cursor-not-allowed',
        )}
      >
        <UploadCloud className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium text-foreground">
            Drag &amp; drop files here, or{' '}
            <span className="text-primary underline-offset-2 hover:underline">select file</span>
          </p>
          <p className="text-xs text-muted-foreground">
            Images, PDF, plain text — max 20 MB
          </p>
          <p className="text-xs text-amber-600 font-medium">
            Upload pending backend support
          </p>
        </div>
        <input
          ref={inputRef}
          data-testid="attachment-file-input"
          type="file"
          accept="image/*,application/pdf,text/plain"
          className="sr-only"
          aria-hidden="true"
          tabIndex={-1}
          disabled={disabled}
          onChange={handleInputChange}
        />
      </div>

      {validationError && (
        <p role="alert" className="text-sm text-destructive">
          {validationError}
        </p>
      )}
    </div>
  );
}
