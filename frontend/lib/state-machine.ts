/**
 * EP-01 — Frontend state machine helper.
 * Mirrors backend VALID_TRANSITIONS exactly (14 edges from design.md).
 * Pure functions — no side effects, no imports from React.
 */
import type { WorkItemState } from './types/work-item';

// 14 edges from domain/state_machine.py
// Key format: "${from}:${to}"
export const VALID_TRANSITIONS: ReadonlySet<string> = new Set([
  'draft:in_clarification',
  'in_clarification:in_review',
  'in_clarification:changes_requested',
  'in_clarification:partially_validated',
  'in_clarification:ready',
  'in_review:changes_requested',
  'in_review:partially_validated',
  'in_review:in_clarification',
  'changes_requested:in_clarification',
  'changes_requested:in_review',
  'partially_validated:in_review',
  'partially_validated:ready',
  'ready:exported',
  'ready:in_clarification',
]);

export function isValidTransition(from: WorkItemState, to: WorkItemState): boolean {
  return VALID_TRANSITIONS.has(`${from}:${to}`);
}

export function getAvailableTransitions(currentState: WorkItemState): WorkItemState[] {
  const prefix = `${currentState}:`;
  const results: WorkItemState[] = [];
  for (const edge of VALID_TRANSITIONS) {
    if (edge.startsWith(prefix)) {
      results.push(edge.slice(prefix.length) as WorkItemState);
    }
  }
  return results;
}
