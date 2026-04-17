'use client';

import { useRouter } from 'next/navigation';
import { useNotifications } from '@/hooks/use-notifications';
import { Card } from '@/components/ui/card';
import { RelativeTime } from '@/components/domain/relative-time';
import {
  AtSign,
  UserCheck,
  RefreshCcw,
  MessageSquare,
  ClipboardCheck,
  Bell,
} from 'lucide-react';
import type { NotificationType } from '@/lib/types/api';
import { isSessionExpired } from '@/lib/types/auth';
import { PageContainer } from '@/components/layout/page-container';

const NOTIFICATION_ICONS: Record<NotificationType, React.ComponentType<{ className?: string }>> = {
  mention: AtSign,
  assignment: UserCheck,
  state_change: RefreshCcw,
  comment: MessageSquare,
  review_request: ClipboardCheck,
  system: Bell,
};

interface InboxPageProps {
  params: { slug: string };
}

export default function InboxPage({ params: { slug } }: InboxPageProps) {
  const router = useRouter();
  const { notifications, isLoading, error, markRead } = useNotifications();

  if (isLoading) {
    return (
      <PageContainer variant="narrow">
        <h1 className="mb-6 text-h2 font-semibold">Bandeja de entrada</h1>
        <p className="text-body-sm text-muted-foreground">Cargando...</p>
      </PageContainer>
    );
  }

  if (error) {
    // El modal global de sesión caducada cubre este caso — no duplicamos el error.
    if (isSessionExpired(error)) return null;
    return (
      <PageContainer variant="narrow">
        <h1 className="mb-6 text-h2 font-semibold">Bandeja de entrada</h1>
        <p className="text-body-sm text-destructive">
          No se pudo cargar la bandeja: {error.message}
        </p>
      </PageContainer>
    );
  }

  async function handleClick(id: string, deeplink: string | null) {
    await markRead(id);
    if (deeplink) {
      router.push(deeplink);
    }
  }

  return (
    <PageContainer variant="narrow">
      <h1 className="mb-6 text-h2 font-semibold">Bandeja de entrada</h1>

      {notifications.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
          <Bell className="h-10 w-10 opacity-30" />
          <p className="text-body">No tienes notificaciones</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {notifications.map((n) => {
            const Icon = NOTIFICATION_ICONS[n.type] ?? Bell;
            return (
              <Card
                key={n.id}
                className={`relative cursor-pointer p-4 transition-colors hover:bg-accent ${
                  !n.read ? 'border-primary/50 bg-primary/5' : ''
                }`}
                onClick={() => void handleClick(n.id, n.deeplink)}
                data-unread={!n.read}
              >
                <div className="flex items-start gap-3">
                  <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="text-body-sm font-medium text-foreground">{n.summary}</p>
                    {n.actor_name && (
                      <p className="text-body-sm text-muted-foreground">{n.actor_name}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <RelativeTime iso={n.created_at} />
                    {!n.read && (
                      <span className="h-2 w-2 rounded-full bg-primary" aria-label="No leída" />
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </PageContainer>
  );
}

