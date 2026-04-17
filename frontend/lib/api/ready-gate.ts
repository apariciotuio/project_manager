/**
 * EP-06 — Ready gate API client.
 * Endpoint: GET /api/v1/work-items/:id/ready-gate
 */
import { apiGet } from '../api-client';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ReadyGateBlocker {
  code: string;
  rule_id: string;
  label: string;
  status: string;
}

export interface ReadyGateResult {
  ok: boolean;
  blockers: ReadyGateBlocker[];
}

// ─── Envelope ────────────────────────────────────────────────────────────────

interface Envelope {
  data: ReadyGateResult;
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function getReadyGate(workItemId: string): Promise<ReadyGateResult> {
  const res = await apiGet<Envelope>(`/api/v1/work-items/${workItemId}/ready-gate`);
  return res.data;
}
