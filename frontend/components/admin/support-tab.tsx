'use client';

import { useState } from 'react';
import { useSupportTools } from '@/hooks/use-admin';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { ConfigBlockedReason } from '@/lib/types/api';

const BLOCKING_REASON_LABEL: Record<ConfigBlockedReason, string> = {
  suspended_owner: 'Suspended owner',
  deleted_team_in_rule: 'Deleted team in rule',
  archived_project: 'Archived project',
};

function SectionHeader({ title, count }: { title: string; count: number }) {
  return (
    <div className="flex items-center gap-2">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <Badge variant="secondary">{count}</Badge>
    </div>
  );
}

export function SupportTab() {
  const {
    orphanedItems,
    pendingInvitations,
    failedExports,
    configBlockedItems,
    isLoading,
    error,
    retryAllExports,
  } = useSupportTools();

  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  async function handleRetryAll() {
    setRetrying(true);
    setRetryError(null);
    try {
      await retryAllExports();
    } catch (err) {
      setRetryError(err instanceof Error ? err.message : String(err));
    } finally {
      setRetrying(false);
    }
  }

  if (isLoading) {
    return (
      <div data-testid="support-skeleton" className="space-y-3 animate-pulse">
        {[1, 2, 3, 4].map((n) => <div key={n} className="h-16 rounded-md bg-muted" />)}
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="support-error" role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-body-sm text-destructive">
        Failed to load support data: {error.message}
      </div>
    );
  }

  // Group config-blocked items by reason
  const blockedByReason = configBlockedItems.reduce<Record<string, typeof configBlockedItems>>(
    (acc, item) => {
      const key = item.blocking_reason;
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    },
    {}
  );

  return (
    <div className="space-y-8">
      {/* Orphaned work items */}
      <div className="space-y-3">
        <SectionHeader title="Orphaned work items" count={orphanedItems.length} />
        {orphanedItems.length === 0 ? (
          <p className="text-body-sm text-muted-foreground">No orphaned items.</p>
        ) : (
          <div className="space-y-2">
            {orphanedItems.map((item) => (
              <div key={item.id} className="flex items-center justify-between rounded border p-3">
                <div>
                  <p className="text-body-sm font-medium">{item.title}</p>
                  <p className={`text-xs text-muted-foreground ${item.owner_state === 'deleted' || item.owner_state === 'suspended' ? 'line-through' : ''}`}>
                    {item.owner_display}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pending invitations */}
      <div className="space-y-3">
        <SectionHeader title="Pending invitations" count={pendingInvitations.length} />
        {pendingInvitations.length === 0 ? (
          <p className="text-body-sm text-muted-foreground">No pending invitations.</p>
        ) : (
          <div className="space-y-2">
            {pendingInvitations.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between rounded border p-3">
                <p className="text-body-sm">{inv.email}</p>
                {inv.expiring_soon && (
                  <Badge variant="secondary">Expiring soon</Badge>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Failed exports */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <SectionHeader title="Failed exports" count={failedExports.length} />
          {failedExports.length > 0 && (
            <Button
              size="sm"
              variant="outline"
              disabled={retrying}
              onClick={() => void handleRetryAll()}
            >
              {retrying ? 'Retrying...' : 'Retry all'}
            </Button>
          )}
        </div>
        {retryError && (
          <p role="alert" className="text-body-sm text-destructive">{retryError}</p>
        )}
        {failedExports.length === 0 ? (
          <p className="text-body-sm text-muted-foreground">No failed exports.</p>
        ) : (
          <div className="space-y-2">
            {failedExports.map((exp) => (
              <div key={exp.id} className="flex items-center justify-between rounded border p-3">
                <div>
                  <p className="text-body-sm font-medium">{exp.work_item_title}</p>
                  <p className="text-xs text-muted-foreground">
                    {exp.error_code} · {exp.attempt_count} attempt{exp.attempt_count !== 1 ? 's' : ''}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Config-blocked work items */}
      <div className="space-y-3">
        <SectionHeader title="Config-blocked work items" count={configBlockedItems.length} />
        {configBlockedItems.length === 0 ? (
          <p className="text-body-sm text-muted-foreground">No config-blocked items.</p>
        ) : (
          <div className="space-y-4">
            {Object.entries(blockedByReason).map(([reason, items]) => (
              <div key={reason} className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {BLOCKING_REASON_LABEL[reason as ConfigBlockedReason] ?? reason}
                </p>
                {items.map((item) => (
                  <div key={item.id} className="rounded border p-3">
                    <p className="text-body-sm">{item.title}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
