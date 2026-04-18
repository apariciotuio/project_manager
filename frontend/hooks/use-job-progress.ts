'use client';

import { useCallback, useRef, useState } from 'react';
import { useSSE, type SSEStatus } from './use-sse';

export type JobStatus = 'connecting' | 'open' | 'running' | 'complete' | 'error';

export interface JobProgressState {
  status: JobStatus;
  percent?: number;
  message?: string;
  result?: unknown;
  errorMessage?: string;
}

/**
 * useJobProgress — streams job execution progress from the backend.
 * Wraps useSSE targeting GET /api/v1/jobs/{jobId}/progress.
 *
 * SSE frame types:
 *   - 'message' → { status: 'running', percent, message }
 *   - 'done'    → { result: {...} }
 *   - 'error'   → { message: string }
 */
export function useJobProgress(jobId: string): JobProgressState {
  const [state, setState] = useState<JobProgressState>({ status: 'connecting' });
  const url = `/api/v1/jobs/${jobId}/progress`;
  const closeRef = useRef<(() => void) | null>(null);

  const handleEvent = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data as string) as Record<string, unknown>;

      if (event.type === 'done') {
        setState({ status: 'complete', result: data['result'] });
        closeRef.current?.();
        return;
      }

      if (event.type === 'error') {
        setState({
          status: 'error',
          errorMessage: (data['message'] as string | undefined) ?? 'Job failed',
        });
        return;
      }

      // Plain 'message' — progress update
      setState((prev) => ({
        ...prev,
        status: 'running',
        percent: data['percent'] as number | undefined,
        message: data['message'] as string | undefined,
      }));
    } catch {
      // ignore malformed frames
    }
  }, []);

  const { status: sseStatus, close } = useSSE(url, handleEvent, {
    maxRetries: 3,
    baseDelay: 1000,
    extraEvents: ['done', 'error'],
  });
  closeRef.current = close;

  // Named terminal states override the SSE infrastructure status
  const effectiveStatus: JobStatus =
    state.status === 'running' || state.status === 'complete' || state.status === 'error'
      ? state.status
      : (sseStatus as JobStatus);

  return { ...state, status: effectiveStatus };
}
