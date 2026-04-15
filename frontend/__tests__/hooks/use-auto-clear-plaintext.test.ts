import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAutoClearPlaintext } from '@/hooks/use-auto-clear-plaintext';

describe('useAutoClearPlaintext', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('starts hidden', () => {
    const { result } = renderHook(() => useAutoClearPlaintext(5000));
    expect(result.current.revealed).toBe(false);
  });

  it('reveal() shows the value', () => {
    const { result } = renderHook(() => useAutoClearPlaintext(5000));
    act(() => result.current.reveal());
    expect(result.current.revealed).toBe(true);
  });

  it('auto-clears after ms', () => {
    const { result } = renderHook(() => useAutoClearPlaintext(3000));
    act(() => result.current.reveal());
    expect(result.current.revealed).toBe(true);
    act(() => vi.advanceTimersByTime(3001));
    expect(result.current.revealed).toBe(false);
  });

  it('hide() clears immediately', () => {
    const { result } = renderHook(() => useAutoClearPlaintext(5000));
    act(() => result.current.reveal());
    act(() => result.current.hide());
    expect(result.current.revealed).toBe(false);
  });
});
