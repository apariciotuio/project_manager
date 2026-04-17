'use client';

import { usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';
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
  const t = useTranslations('auth.sessionExpired');

  function goToLogin() {
    // Go straight to the OAuth entry point — if the Google session is still
    // alive, re-auth is one click. Otherwise the backend bounces to /login.
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
          <DialogTitle>{t('title')}</DialogTitle>
          <DialogDescription>{t('description')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={goToLogin}>{t('cta')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
