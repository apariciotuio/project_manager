'use client';

import { useState, type ReactNode } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface TypedConfirmDialogProps {
  title: string;
  description: string;
  expected: string;
  onConfirm: () => void | Promise<void>;
  trigger: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

export function TypedConfirmDialog({
  title,
  description,
  expected,
  onConfirm,
  trigger,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  destructive = true,
}: TypedConfirmDialogProps) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [pending, setPending] = useState(false);

  const canConfirm = value === expected;

  async function handleConfirm() {
    if (!canConfirm) return;
    setPending(true);
    try {
      await onConfirm();
      setOpen(false);
    } finally {
      setPending(false);
      setValue('');
    }
  }

  function handleOpenChange(next: boolean) {
    if (!next) setValue('');
    setOpen(next);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <span onClick={() => setOpen(true)} style={{ cursor: 'pointer', display: 'contents' }}>
        {trigger}
      </span>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="confirm-input">
            Escribe <strong>{expected}</strong> para confirmar
          </Label>
          <Input
            id="confirm-input"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={expected}
            autoComplete="off"
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            {cancelLabel}
          </Button>
          <Button
            variant={destructive ? 'destructive' : 'default'}
            disabled={!canConfirm || pending}
            onClick={handleConfirm}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
