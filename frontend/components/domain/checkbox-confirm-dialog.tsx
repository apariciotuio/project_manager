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
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

interface CheckboxConfirmDialogProps {
  title: string;
  description: string;
  checkboxLabel: string;
  onConfirm: () => void | Promise<void>;
  trigger: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

export function CheckboxConfirmDialog({
  title,
  description,
  checkboxLabel,
  onConfirm,
  trigger,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  destructive = false,
}: CheckboxConfirmDialogProps) {
  const [open, setOpen] = useState(false);
  const [checked, setChecked] = useState(false);
  const [pending, setPending] = useState(false);

  async function handleConfirm() {
    if (!checked) return;
    setPending(true);
    try {
      await onConfirm();
      setOpen(false);
    } finally {
      setPending(false);
      setChecked(false);
    }
  }

  function handleOpenChange(next: boolean) {
    if (!next) setChecked(false);
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

        <div className="flex items-start gap-2">
          <Checkbox
            id="checkbox-confirm"
            checked={checked}
            onCheckedChange={(v) => setChecked(v === true)}
          />
          <Label htmlFor="checkbox-confirm" className="cursor-pointer leading-relaxed">
            {checkboxLabel}
          </Label>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            {cancelLabel}
          </Button>
          <Button
            variant={destructive ? 'destructive' : 'default'}
            disabled={!checked || pending}
            onClick={handleConfirm}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
