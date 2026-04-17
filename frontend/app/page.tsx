'use client';

import { useTranslations } from 'next-intl';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { HealthIndicator } from '@/components/health-indicator';

export default function HomePage() {
  const t = useTranslations();

  return (
    <main className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-6 rounded-xl border border-muted/30 bg-background p-10 shadow-lg">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          {t('app.title')}
        </h1>
        <div className="flex items-center gap-4">
          <ThemeToggle />
          <HealthIndicator />
        </div>
      </div>
    </main>
  );
}
