'use client';

import { useEffect, useCallback } from 'react';

interface ShortcutOptions {
  /** Match Ctrl key (default: false) */
  ctrl?: boolean;
  /** Match Meta/Cmd key (default: false) */
  meta?: boolean;
  /** Match Shift key (default: false) */
  shift?: boolean;
  /** Match Alt key (default: false) */
  alt?: boolean;
  /** Whether to suppress in form fields (default: true) */
  suppressInInputs?: boolean;
}

const INPUT_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

/**
 * Register a global keyboard shortcut.
 * Cleans up on unmount. Suppresses in form fields by default.
 */
export function useKeyboardShortcut(
  key: string,
  handler: (e: KeyboardEvent) => void,
  options: ShortcutOptions = {}
) {
  const {
    ctrl = false,
    meta = false,
    shift = false,
    alt = false,
    suppressInInputs = true,
  } = options;

  const stableHandler = useCallback(handler, [handler]);

  useEffect(() => {
    function onKeydown(e: KeyboardEvent) {
      if (suppressInInputs) {
        const target = e.target as HTMLElement;
        if (
          INPUT_TAGS.has(target.tagName) ||
          target.isContentEditable
        ) {
          return;
        }
      }

      const keyMatch = e.key === key || e.key.toLowerCase() === key.toLowerCase();
      const ctrlMatch = ctrl ? e.ctrlKey : true;
      const metaMatch = meta ? e.metaKey : true;
      const shiftMatch = shift ? e.shiftKey : true;
      const altMatch = alt ? e.altKey : true;

      // When modifier is not required, we want it NOT to be pressed
      // (to avoid conflicting with browser shortcuts when not specified)
      const ctrlOk = ctrl ? e.ctrlKey : !e.ctrlKey || meta;
      const metaOk = meta ? e.metaKey : !e.metaKey || ctrl;
      const shiftOk = shift ? e.shiftKey : !e.shiftKey;
      const altOk = alt ? e.altKey : !e.altKey;

      if (keyMatch && ctrlMatch && metaMatch && shiftMatch && altMatch &&
          ctrlOk && metaOk && shiftOk && altOk) {
        e.preventDefault();
        stableHandler(e);
      }
    }

    document.addEventListener('keydown', onKeydown);
    return () => document.removeEventListener('keydown', onKeydown);
  }, [key, ctrl, meta, shift, alt, suppressInInputs, stableHandler]);
}
