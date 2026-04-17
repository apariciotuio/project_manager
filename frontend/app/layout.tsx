import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import type { AbstractIntlMessages } from 'next-intl';
import { cookies } from 'next/headers';
import { Inter } from 'next/font/google';
import { Providers } from './providers';
import './globals.css';

const SUPPORTED_LOCALES = new Set(['es', 'en']);
const LOCALE_COOKIE = 'tuio-locale';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

// Load messages server-side so they can be passed to the client provider
async function getMessages(locale: string): Promise<AbstractIntlMessages> {
  try {
    return (await import(`../locales/${locale}.json`)).default as AbstractIntlMessages;
  } catch {
    return (await import('../locales/es.json')).default as AbstractIntlMessages;
  }
}

export const metadata: Metadata = {
  title: 'Work Maturation Platform',
  description: 'Internal work maturation platform for Tuio',
};

interface RootLayoutProps {
  children: ReactNode;
}

export default async function RootLayout({ children }: RootLayoutProps) {
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get(LOCALE_COOKIE)?.value;
  const envDefault = process.env['NEXT_PUBLIC_DEFAULT_LOCALE'] ?? 'es';
  const locale =
    cookieLocale && SUPPORTED_LOCALES.has(cookieLocale) ? cookieLocale : envDefault;
  const messages = await getMessages(locale);

  return (
    <html lang={locale} suppressHydrationWarning className={inter.variable}>
      <body>
        <Providers locale={locale} messages={messages}>
          {children}
        </Providers>
      </body>
    </html>
  );
}
