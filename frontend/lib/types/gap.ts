/**
 * EP-03 — Gap detection types.
 * GET /api/v1/work-items/{id}/gaps is EP-04-owned; stub returns { findings: [] }.
 */

export type GapSeverity = 'blocking' | 'warning' | 'info';
export type GapSource = 'rule' | 'llm';

export interface GapFinding {
  dimension: string;
  severity: GapSeverity;
  message: string;
  source: GapSource;
}

export interface GapReport {
  work_item_id: string;
  findings: GapFinding[];
  /** Completeness score 0.0–1.0 */
  score: number;
}
