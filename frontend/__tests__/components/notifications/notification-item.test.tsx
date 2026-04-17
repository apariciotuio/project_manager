import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NotificationItem } from '@/components/notifications/notification-item';
import type { NotificationV2 } from '@/lib/types/api';

const baseNotification: NotificationV2 = {
  id: 'n1',
  workspace_id: 'ws1',
  recipient_id: 'u1',
  type: 'mention',
  state: 'unread',
  actor_id: 'actor1',
  subject_type: 'work_item',
  subject_id: 'wi1',
  deeplink: '/workspace/acme/items/wi1',
  quick_action: null,
  extra: { summary: 'Alice mentioned you', actor_name: 'Alice' },
  created_at: '2026-04-16T10:00:00Z',
  read_at: null,
  actioned_at: null,
};

describe('NotificationItem', () => {
  it('renders summary from extra.summary', () => {
    render(
      <NotificationItem
        notification={baseNotification}
        onMarkRead={vi.fn()}
      />
    );
    expect(screen.getByText('Alice mentioned you')).toBeTruthy();
  });

  it('renders actor_name from extra.actor_name', () => {
    render(
      <NotificationItem
        notification={baseNotification}
        onMarkRead={vi.fn()}
      />
    );
    expect(screen.getByText('Alice')).toBeTruthy();
  });

  it('unread item has bold text class and blue dot', () => {
    render(
      <NotificationItem
        notification={baseNotification}
        onMarkRead={vi.fn()}
      />
    );
    const dot = screen.getByLabelText('Unread');
    expect(dot).toBeTruthy();
  });

  it('read item has no unread dot', () => {
    const readNotification: NotificationV2 = { ...baseNotification, state: 'read' };
    render(
      <NotificationItem
        notification={readNotification}
        onMarkRead={vi.fn()}
      />
    );
    expect(screen.queryByLabelText('Unread')).toBeNull();
  });

  it('actioned item shows checkmark, no action button', () => {
    const notification: NotificationV2 = {
      ...baseNotification,
      state: 'actioned',
      quick_action: {
        action: 'Approve',
        endpoint: '/api/v1/reviews/r1/approve',
        method: 'POST',
        payload_schema: {},
      },
    };
    render(
      <NotificationItem
        notification={notification}
        onMarkRead={vi.fn()}
      />
    );
    expect(screen.getByLabelText('Actioned')).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('quick_action present shows action button with action label', () => {
    const notification: NotificationV2 = {
      ...baseNotification,
      state: 'unread',
      quick_action: {
        action: 'Approve',
        endpoint: '/api/v1/reviews/r1/approve',
        method: 'POST',
        payload_schema: {},
      },
    };
    const onExecuteAction = vi.fn();
    render(
      <NotificationItem
        notification={notification}
        onMarkRead={vi.fn()}
        onExecuteAction={onExecuteAction}
      />
    );
    expect(screen.getByRole('button', { name: 'Approve' })).toBeTruthy();
  });

  it('clicking action button calls onExecuteAction', async () => {
    const quickAction = {
      action: 'Approve',
      endpoint: '/api/v1/reviews/r1/approve',
      method: 'POST' as const,
      payload_schema: {},
    };
    const notification: NotificationV2 = {
      ...baseNotification,
      state: 'unread',
      quick_action: quickAction,
    };
    const onExecuteAction = vi.fn();
    render(
      <NotificationItem
        notification={notification}
        onMarkRead={vi.fn()}
        onExecuteAction={onExecuteAction}
      />
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Approve' }));
    expect(onExecuteAction).toHaveBeenCalledWith('n1', quickAction);
  });

  it('hovering unread item calls onMarkRead', async () => {
    const onMarkRead = vi.fn();
    render(
      <NotificationItem
        notification={baseNotification}
        onMarkRead={onMarkRead}
      />
    );

    const user = userEvent.setup();
    const container = document.querySelector('[data-notification-id="n1"]')!;
    await user.hover(container);
    expect(onMarkRead).toHaveBeenCalledWith('n1');
  });

  it('hovering read item does not call onMarkRead', async () => {
    const onMarkRead = vi.fn();
    const readNotification: NotificationV2 = { ...baseNotification, state: 'read' };
    render(
      <NotificationItem
        notification={readNotification}
        onMarkRead={onMarkRead}
      />
    );

    const user = userEvent.setup();
    const container = document.querySelector('[data-notification-id="n1"]')!;
    await user.hover(container);
    expect(onMarkRead).not.toHaveBeenCalled();
  });
});
