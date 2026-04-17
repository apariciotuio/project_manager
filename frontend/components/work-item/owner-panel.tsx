'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { OwnerAvatar } from '@/components/domain/owner-avatar';
import { useWorkspaceMembers } from '@/hooks/use-workspace-members';
import { ReassignOwnerModal } from '@/components/work-item/reassign-owner-modal';
import type { WorkItemResponse } from '@/lib/types/work-item';

export interface OwnerPanelProps {
  workItem: WorkItemResponse;
  canReassign: boolean;
  onReassigned: (updated: WorkItemResponse) => void;
}

export function OwnerPanel({ workItem, canReassign, onReassigned }: OwnerPanelProps) {
  const t = useTranslations('workspace.itemDetail.reassign');
  const { members, isLoading } = useWorkspaceMembers();
  const [open, setOpen] = useState(false);

  const owner = members.find((m) => m.id === workItem.owner_id);

  return (
    <section className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-3">
        <h3 className="text-body-sm font-semibold text-foreground">{t('heading')}</h3>
        <div className="flex items-center gap-2">
          <OwnerAvatar name={owner?.full_name} avatarUrl={owner?.avatar_url} size="sm" />
          <span className="text-body-sm text-foreground">
            {isLoading ? t('loading') : owner?.full_name ?? t('unassigned')}
          </span>
        </div>
      </div>

      {canReassign && (
        <Button type="button" variant="outline" size="sm" onClick={() => setOpen(true)}>
          {t('button')}
        </Button>
      )}

      <ReassignOwnerModal
        open={open}
        workItem={workItem}
        onClose={() => setOpen(false)}
        onReassigned={(updated) => {
          setOpen(false);
          onReassigned(updated);
        }}
      />
    </section>
  );
}
