'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { LogOut } from 'lucide-react';
import { useAuth } from '@/app/providers/auth-provider';
import { Button } from '@/components/ui/button';

interface LogoutButtonProps {
  className?: string;
}

export function LogoutButton({ className }: LogoutButtonProps) {
  const t = useTranslations('auth');
  const { logout } = useAuth();
  const [isPending, setIsPending] = useState(false);

  async function handleClick() {
    if (isPending) return;
    setIsPending(true);
    try {
      await logout();
    } finally {
      setIsPending(false);
    }
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => void handleClick()}
      disabled={isPending}
      className={className}
    >
      <LogOut className="h-4 w-4" aria-hidden />
      {t('logout')}
    </Button>
  );
}
