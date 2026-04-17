/**
 * EP-01 Phase 6 — State machine helper tests.
 * 14 valid edges from design.md. Pure function, parametrized.
 */
import { describe, it, expect } from 'vitest';
import {
  getAvailableTransitions,
  isValidTransition,
  VALID_TRANSITIONS,
} from '@/lib/state-machine';
import type { WorkItemState } from '@/lib/types/work-item';

describe('VALID_TRANSITIONS', () => {
  it('contains exactly 14 edges', () => {
    expect(VALID_TRANSITIONS.size).toBe(14);
  });
});

describe('isValidTransition', () => {
  const validEdges: Array<[WorkItemState, WorkItemState]> = [
    ['draft', 'in_clarification'],
    ['in_clarification', 'in_review'],
    ['in_clarification', 'changes_requested'],
    ['in_clarification', 'partially_validated'],
    ['in_clarification', 'ready'],
    ['in_review', 'changes_requested'],
    ['in_review', 'partially_validated'],
    ['in_review', 'in_clarification'],
    ['changes_requested', 'in_clarification'],
    ['changes_requested', 'in_review'],
    ['partially_validated', 'in_review'],
    ['partially_validated', 'ready'],
    ['ready', 'exported'],
    ['ready', 'in_clarification'],
  ];

  it.each(validEdges)(
    'returns true for %s → %s',
    (from, to) => {
      expect(isValidTransition(from, to)).toBe(true);
    },
  );

  const invalidEdges: Array<[WorkItemState, WorkItemState]> = [
    ['draft', 'ready'],
    ['draft', 'exported'],
    ['exported', 'draft'],
    ['exported', 'in_clarification'],
    ['ready', 'draft'],
    ['changes_requested', 'ready'],
  ];

  it.each(invalidEdges)(
    'returns false for %s → %s',
    (from, to) => {
      expect(isValidTransition(from, to)).toBe(false);
    },
  );
});

describe('getAvailableTransitions', () => {
  it('draft → [in_clarification] only', () => {
    const result = getAvailableTransitions('draft');
    expect(result).toEqual(['in_clarification']);
  });

  it('in_clarification → 4 targets', () => {
    const result = getAvailableTransitions('in_clarification');
    expect(result).toHaveLength(4);
    expect(result).toContain('in_review');
    expect(result).toContain('changes_requested');
    expect(result).toContain('partially_validated');
    expect(result).toContain('ready');
  });

  it('in_review → 3 targets', () => {
    const result = getAvailableTransitions('in_review');
    expect(result).toHaveLength(3);
    expect(result).toContain('changes_requested');
    expect(result).toContain('partially_validated');
    expect(result).toContain('in_clarification');
  });

  it('changes_requested → [in_clarification, in_review]', () => {
    const result = getAvailableTransitions('changes_requested');
    expect(result).toHaveLength(2);
    expect(result).toContain('in_clarification');
    expect(result).toContain('in_review');
  });

  it('partially_validated → [in_review, ready]', () => {
    const result = getAvailableTransitions('partially_validated');
    expect(result).toHaveLength(2);
    expect(result).toContain('in_review');
    expect(result).toContain('ready');
  });

  it('ready → [exported, in_clarification]', () => {
    const result = getAvailableTransitions('ready');
    expect(result).toHaveLength(2);
    expect(result).toContain('exported');
    expect(result).toContain('in_clarification');
  });

  it('exported → [] (terminal state)', () => {
    expect(getAvailableTransitions('exported')).toEqual([]);
  });
});
