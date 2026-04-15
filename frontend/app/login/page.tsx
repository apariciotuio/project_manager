'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useAuth } from '@/app/providers/auth-provider';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertCircle } from 'lucide-react';

const KNOWN_ERRORS = new Set([
  'oauth_failed',
  'session_expired',
  'invalid_state',
  'cancelled',
  'no_workspace',
]);

export default function LoginPage() {
  const t = useTranslations('auth');
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLoading, isAuthenticated, user } = useAuth();

  const errorParam = searchParams.get('error');
  const knownError =
    errorParam && KNOWN_ERRORS.has(errorParam) ? errorParam : null;

  useEffect(() => {
    if (!isAuthenticated || !user) return;
    // user with no active workspace goes to picker; bootstrap path
    router.replace(
      user.workspace_slug
        ? `/workspace/${user.workspace_slug}`
        : '/workspace/select',
    );
  }, [isAuthenticated, user, router]);

  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div
          data-testid="loading-spinner"
          role="status"
          aria-label="Cargando"
          className="flex items-center justify-center"
        >
          <Skeleton className="h-8 w-8 rounded-full" />
        </div>
      </main>
    );
  }

  if (isAuthenticated) {
    // Redirect in progress via useEffect — render nothing to avoid flash
    return null;
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-h1">Work Maturation Platform</h1>

      {knownError && (
        <div
          role="alert"
          className="flex w-full max-w-sm items-start gap-2 rounded-md bg-destructive/10 p-4 text-body-sm text-destructive ring-1 ring-destructive/30"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {t(`errors.${knownError}` as Parameters<typeof t>[0])}
        </div>
      )}

      <Button asChild variant="outline" className="gap-3">
        <a href="/api/v1/auth/google">
          {t('signInWithGoogle')}
        </a>
      </Button>
    </main>
  );
}
