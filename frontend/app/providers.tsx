'use client';

import { NextIntlClientProvider } from 'next-intl';
import type { AbstractIntlMessages } from 'next-intl';
import type { ReactNode } from 'react';
import { ThemeProvider } from 'next-themes';
import { AuthProvider } from './providers/auth-provider';

interface ProvidersProps {
  children: ReactNode;
  locale: string;
  messages: AbstractIntlMessages;
}

export function Providers({ children, locale, messages }: ProvidersProps) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      themes={['light', 'dark', 'matrix']}
      value={{ light: 'light', dark: 'dark', matrix: 'matrix' }}
      disableTransitionOnChange
    >
      <NextIntlClientProvider locale={locale} messages={messages} timeZone="UTC">
        <AuthProvider>{children}</AuthProvider>
      </NextIntlClientProvider>
    </ThemeProvider>
  );
}
