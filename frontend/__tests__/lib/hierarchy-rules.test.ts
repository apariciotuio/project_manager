/**
 * FE-14-05 — hierarchy-rules tests.
 */
import { describe, it, expect } from 'vitest';
import { getValidParentTypes, VALID_PARENT_TYPES } from '@/lib/hierarchy-rules';

describe('getValidParentTypes', () => {
  it('returns ["milestone"] for initiative', () => {
    expect(getValidParentTypes('initiative')).toEqual(['milestone']);
  });

  it('returns [] (empty array) for milestone — no parent allowed', () => {
    expect(getValidParentTypes('milestone')).toEqual([]);
  });

  it('returns null for task — no type restriction', () => {
    expect(getValidParentTypes('task')).toBeNull();
  });

  it('returns ["initiative"] for story', () => {
    const result = getValidParentTypes('story');
    expect(result).not.toBeNull();
    expect(result).toContain('initiative');
  });

  it('returns null for bug — no type restriction', () => {
    expect(getValidParentTypes('bug')).toBeNull();
  });

  it('returns null for idea — no type restriction', () => {
    expect(getValidParentTypes('idea')).toBeNull();
  });

  it('VALID_PARENT_TYPES keys cover all WorkItemTypes', () => {
    const keys = Object.keys(VALID_PARENT_TYPES);
    expect(keys).toContain('milestone');
    expect(keys).toContain('story');
    expect(keys).toContain('initiative');
    expect(keys).toContain('task');
    expect(keys).toContain('bug');
  });
});
