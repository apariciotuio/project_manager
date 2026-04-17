import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LogoutButton } from '@/components/auth/logout-button';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

// Shared state — reset in each test
let logoutCallCount = 0;
const pendingResolvers: Array<() => void> = [];

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    logout: () => {
      logoutCallCount++;
      return new Promise<void>((resolve) => {
        pendingResolvers.push(resolve);
      });
    },
  }),
}));

async function resolveAll() {
  await act(async () => {
    pendingResolvers.splice(0).forEach((r) => r());
  });
}

describe('LogoutButton', () => {
  it('calls logout once on click', async () => {
    logoutCallCount = 0;
    pendingResolvers.length = 0;
    render(<LogoutButton />);
    await userEvent.click(screen.getByRole('button'));
    expect(logoutCallCount).toBe(1);
    await resolveAll();
  });

  it('is disabled while logout is pending', async () => {
    logoutCallCount = 0;
    pendingResolvers.length = 0;
    render(<LogoutButton />);
    await userEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button')).toBeDisabled();
    await resolveAll();
    await waitFor(() =>
      expect(screen.getByRole('button')).not.toBeDisabled(),
    );
  });

  it('does not call logout a second time on double-click', async () => {
    logoutCallCount = 0;
    pendingResolvers.length = 0;
    render(<LogoutButton />);
    const button = screen.getByRole('button');
    await userEvent.click(button);
    // button is now disabled — second click is ignored
    await userEvent.click(button);
    expect(logoutCallCount).toBe(1);
    await resolveAll();
  });

  it('re-enables after logout resolves', async () => {
    logoutCallCount = 0;
    pendingResolvers.length = 0;
    render(<LogoutButton />);
    const button = screen.getByRole('button');
    await userEvent.click(button);
    expect(button).toBeDisabled();
    await resolveAll();
    await waitFor(() => expect(button).not.toBeDisabled());
  });
});
