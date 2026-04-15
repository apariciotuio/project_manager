import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useKeyboardShortcut } from '@/hooks/use-keyboard-shortcut';

function simulateKey(key: string, options: Partial<KeyboardEventInit> = {}) {
  act(() => {
    document.dispatchEvent(new KeyboardEvent('keydown', { key, ...options, bubbles: true }));
  });
}

describe('useKeyboardShortcut', () => {
  it('calls handler on matching key', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut('k', handler, { meta: true }));
    simulateKey('k', { metaKey: true });
    expect(handler).toHaveBeenCalledOnce();
  });

  it('does not call handler on wrong key', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut('k', handler, { meta: true }));
    simulateKey('j', { metaKey: true });
    expect(handler).not.toHaveBeenCalled();
  });

  it('cleans up on unmount', () => {
    const handler = vi.fn();
    const { unmount } = renderHook(() => useKeyboardShortcut('k', handler));
    unmount();
    simulateKey('k');
    expect(handler).not.toHaveBeenCalled();
  });
});
