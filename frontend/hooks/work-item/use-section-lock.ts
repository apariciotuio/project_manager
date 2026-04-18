'use client';

/**
 * EP-17 — Manages acquire/heartbeat/release for a single section lock.
 *
 * Usage:
 *   const { isHolder, lockLost, acquireLock, releaseLock } = useSectionLock(sectionId);
 *
 * - acquireLock(): call when user enters edit mode. Returns the lock or throws.
 * - releaseLock(): call on cancel / save / unmount.
 * - Heartbeat fires every LOCK_HEARTBEAT_INTERVAL_MS (default 30 000).
 * - 404/403 heartbeat → sets lockLost=true, stops interval.
 * - 503 heartbeat → toast only, interval continues.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  acquireSectionLock,
  heartbeatSectionLock,
  releaseSectionLock,
} from '@/lib/api/lock-api';
import type { SectionLockDTO } from '@/lib/types/lock';

export const LOCK_HEARTBEAT_INTERVAL_MS = 30_000;

export type LockLostReason = 'expired' | 'conflict' | 'connection';

export interface UseSectionLockReturn {
  lock: SectionLockDTO | null;
  isHolder: boolean;
  lockLost: boolean;
  lockLostReason: LockLostReason | null;
  acquireLock: () => Promise<SectionLockDTO>;
  releaseLock: () => Promise<void>;
}

export function useSectionLock(sectionId: string): UseSectionLockReturn {
  const [lock, setLock] = useState<SectionLockDTO | null>(null);
  const [isHolder, setIsHolder] = useState(false);
  const [lockLost, setLockLost] = useState(false);
  const [lockLostReason, setLockLostReason] = useState<LockLostReason | null>(null);

  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isHolderRef = useRef(false);
  const lockLostRef = useRef(false);

  // Keep refs in sync for cleanup closure
  isHolderRef.current = isHolder;
  lockLostRef.current = lockLost;

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current !== null) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatRef.current = setInterval(async () => {
      try {
        const updated = await heartbeatSectionLock(sectionId);
        setLock(updated);
      } catch (err: unknown) {
        const status = (err as { status?: number })?.status;
        if (status === 404 || status === 403) {
          stopHeartbeat();
          setLockLost(true);
          setLockLostReason('expired');
          setIsHolder(false);
        }
        // 503 / other: leave interval running, caller should surface connection toast
      }
    }, LOCK_HEARTBEAT_INTERVAL_MS);
  }, [sectionId, stopHeartbeat]);

  const acquireLock = useCallback(async (): Promise<SectionLockDTO> => {
    const acquired = await acquireSectionLock(sectionId);
    setLock(acquired);
    setIsHolder(true);
    setLockLost(false);
    setLockLostReason(null);
    startHeartbeat();
    return acquired;
  }, [sectionId, startHeartbeat]);

  const releaseLock = useCallback(async (): Promise<void> => {
    stopHeartbeat();
    if (!isHolderRef.current || lockLostRef.current) return;
    try {
      await releaseSectionLock(sectionId);
    } finally {
      setLock(null);
      setIsHolder(false);
    }
  }, [sectionId, stopHeartbeat]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopHeartbeat();
      // Best-effort fire-and-forget release on unmount
      if (isHolderRef.current && !lockLostRef.current) {
        void releaseSectionLock(sectionId).catch(() => {
          // ignore unmount errors — the TTL will expire naturally
        });
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sectionId]);

  return { lock, isHolder, lockLost, lockLostReason, acquireLock, releaseLock };
}
