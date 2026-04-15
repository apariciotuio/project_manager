'use client';

import { useState, useEffect, useRef } from 'react';

/**
 * Hook for managing plaintext reveal with auto-clear.
 * SECURITY: no writes to any storage medium.
 */
export function useAutoClearPlaintext(ms: number) {
  const [revealed, setRevealed] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (revealed && ms > 0) {
      timerRef.current = setTimeout(() => setRevealed(false), ms);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [revealed, ms]);

  function reveal() {
    setRevealed(true);
  }

  function hide() {
    if (timerRef.current) clearTimeout(timerRef.current);
    setRevealed(false);
  }

  return { revealed, reveal, hide };
}
