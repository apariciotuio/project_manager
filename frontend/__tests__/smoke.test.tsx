import { describe, it, expect, vi } from 'vitest';
import HomePage from '@/app/page';

const redirectMock = vi.fn();

vi.mock('next/navigation', () => ({
  redirect: (url: string) => {
    redirectMock(url);
    throw new Error('NEXT_REDIRECT');
  },
}));

describe('HomePage', () => {
  it('redirects to the workspace selector', () => {
    expect(() => HomePage()).toThrow('NEXT_REDIRECT');
    expect(redirectMock).toHaveBeenCalledWith('/workspace/select');
  });
});
