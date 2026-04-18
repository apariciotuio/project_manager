'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useAdminMembers } from '@/hooks/use-admin';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import type { AdminMember, MemberState } from '@/lib/types/api';

const STATE_VARIANT: Record<MemberState, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  active: 'default',
  invited: 'outline',
  suspended: 'secondary',
  deleted: 'destructive',
};

function MemberStateBadge({ state }: { state: MemberState }) {
  return <Badge variant={STATE_VARIANT[state]}>{state}</Badge>;
}

function ChipList({ items, testIdPrefix }: { items: string[]; testIdPrefix: string }) {
  if (items.length === 0) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((item) => (
        <span
          key={item}
          data-testid={`${testIdPrefix}-${item}`}
          className="rounded-full bg-muted px-2 py-0.5 text-xs"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

function ConfirmDialog({ open, title, description, onConfirm, onClose }: ConfirmDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setLoading(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {error && (
          <p role="alert" className="text-body-sm text-destructive">{error}</p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant="destructive" disabled={loading} onClick={() => void handleConfirm()}>
            {loading ? 'Processing...' : 'Confirm'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface InviteMemberModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (email: string) => Promise<void>;
}

function InviteMemberModal({ open, onClose, onSubmit }: InviteMemberModalProps) {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await onSubmit(email.trim());
      setEmail('');
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg.includes('already exists') || msg.includes('already_active') ? 'A member with this email already exists' : msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) { onClose(); setError(null); } }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite member</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {error && (
            <p role="alert" className="text-body-sm text-destructive">{error}</p>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="invite-email">Email *</Label>
            <Input
              id="invite-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={!email.trim() || loading}>
              {loading ? 'Sending...' : 'Send invite'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function MembersTabEnhanced() {
  const _t = useTranslations('workspace.admin.members');
  const { members, isLoading, error, inviteMember, updateMember } = useAdminMembers();

  const [suspendTarget, setSuspendTarget] = useState<AdminMember | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);

  if (isLoading) {
    return (
      <div data-testid="admin-members-skeleton" className="space-y-3 animate-pulse">
        {[1, 2, 3].map((n) => <div key={n} className="h-12 rounded-md bg-muted" />)}
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="admin-members-error" role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-body-sm text-destructive">
        Failed to load members: {error.message}
      </div>
    );
  }

  if (members.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setInviteOpen(true)}>Invite member</Button>
        </div>
        <p data-testid="admin-members-empty" className="py-8 text-center text-muted-foreground">
          No members in this workspace.
        </p>
        <InviteMemberModal
          open={inviteOpen}
          onClose={() => setInviteOpen(false)}
          onSubmit={async (email) => { await inviteMember({ email }); }}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setInviteOpen(true)}>Invite member</Button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-body-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 pr-4 font-medium">Name</th>
              <th className="pb-2 pr-4 font-medium">Email</th>
              <th className="pb-2 pr-4 font-medium">State</th>
              <th className="pb-2 pr-4 font-medium">Capabilities</th>
              <th className="pb-2 pr-4 font-medium">Labels</th>
              <th className="pb-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id} className="border-b last:border-0">
                <td className="py-2 pr-4 font-medium">{m.display_name}</td>
                <td className="py-2 pr-4 text-muted-foreground">{m.email}</td>
                <td className="py-2 pr-4">
                  <MemberStateBadge state={m.state} />
                </td>
                <td className="py-2 pr-4">
                  <ChipList items={m.capabilities} testIdPrefix="cap" />
                </td>
                <td className="py-2 pr-4">
                  <ChipList items={m.context_labels} testIdPrefix="label" />
                </td>
                <td className="py-2">
                  {m.state === 'active' && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs"
                      onClick={() => setSuspendTarget(m)}
                    >
                      Suspend
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={!!suspendTarget}
        title="Suspend member"
        description={`Suspend ${suspendTarget?.display_name ?? ''}? They will lose access immediately.`}
        onConfirm={async () => {
          if (suspendTarget) await updateMember(suspendTarget.id, { state: 'suspended' });
        }}
        onClose={() => setSuspendTarget(null)}
      />

      <InviteMemberModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onSubmit={async (email) => { await inviteMember({ email }); }}
      />
    </div>
  );
}
