/**
 * PageContainer — semantic layout wrapper.
 *
 * variant="wide"   → max-w-screen-2xl (1536px), used by data-heavy pages
 *                    (items list, item detail, admin, teams)
 * variant="narrow" → max-w-4xl  (56rem), kept for form-shaped pages
 *                    (new item, inbox) where readability > horizontal space.
 *
 * Mobile: always px-4. Wide monitors (≥1536px): 2xl:px-16 (4rem) each side.
 */

import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

interface PageContainerProps {
  variant: 'wide' | 'narrow';
  children: ReactNode;
  className?: string;
}

const BASE = 'mx-auto w-full px-4 py-8';

const VARIANTS: Record<PageContainerProps['variant'], string> = {
  wide: 'max-w-screen-2xl 2xl:px-16',
  narrow: 'max-w-4xl',
};

export function PageContainer({ variant, children, className }: PageContainerProps) {
  return (
    <div className={cn(BASE, VARIANTS[variant], className)}>
      {children}
    </div>
  );
}
