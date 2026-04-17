'use client';

import { usePathname } from 'next/navigation';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

interface SessionExpiredModalProps {
  open: boolean;
}

export function SessionExpiredModal({ open }: SessionExpiredModalProps) {
  const pathname = usePathname();

  function goToLogin() {
    // Redirige directo al flujo OAuth de Google — evita el paso extra por /login
    // y la doble interacción. Si la sesión de Google sigue viva, es un solo clic.
    const returnTo = pathname && pathname !== '/login' ? pathname : '/';
    window.location.href = `/api/v1/auth/google?return_to=${encodeURIComponent(returnTo)}`;
  }

  return (
    <Dialog open={open}>
      <DialogContent
        onEscapeKeyDown={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>Tu sesión ha caducado</DialogTitle>
          <DialogDescription>
            Por seguridad, necesitas iniciar sesión de nuevo. Los cambios sin guardar
            podrían perderse.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={goToLogin}>Iniciar sesión</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
