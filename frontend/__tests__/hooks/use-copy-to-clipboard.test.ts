import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCopyToClipboard } from '@/hooks/use-copy-to-clipboard';

describe('useCopyToClipboard', () => {
  it('starts with copied=false', () => {
    const { result } = renderHook(() => useCopyToClipboard());
    expect(result.current.copied).toBe(false);
  });

  it('sets copied=true after copy', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    const { result } = renderHook(() => useCopyToClipboard());
    await act(async () => {
      await result.current.copy('test value');
    });
    expect(result.current.copied).toBe(true);
  });

  it('returns error on clipboard failure', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    });
    const { result } = renderHook(() => useCopyToClipboard());
    await act(async () => {
      await result.current.copy('test value');
    });
    expect(result.current.error).toBeInstanceOf(Error);
  });
});
