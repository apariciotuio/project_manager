/**
 * FE-14-05 — hierarchy-rules tests.
 */
import { describe, it, expect } from 'vitest';
import { getValidParentTypes, VALID_PARENT_TYPES } from '@/lib/hierarchy-rules';

describe('getValidParentTypes', () => {
  it('initiative admits milestone and business_change as parents (EP-24)', () => {
    const result = getValidParentTypes('initiative');
    expect(result).toContain('milestone');
    expect(result).toContain('business_change');
  });

  it('returns [] (empty array) for milestone — no parent allowed', () => {
    expect(getValidParentTypes('milestone')).toEqual([]);
  });

  it('task admits initiative, story and idea as parents (EP-24)', () => {
    const result = getValidParentTypes('task');
    expect(result).toContain('initiative');
    expect(result).toContain('story');
    expect(result).toContain('idea');
  });

  it('story admits milestone, initiative and business_change (EP-24)', () => {
    const result = getValidParentTypes('story');
    expect(result).toContain('milestone');
    expect(result).toContain('initiative');
    expect(result).toContain('business_change');
  });

  it('bug admits initiative and story (unchanged by EP-24)', () => {
    expect(getValidParentTypes('bug')).toEqual(
      expect.arrayContaining(['initiative', 'story']),
    );
  });

  it('spike admits story and idea as parents (EP-24)', () => {
    const result = getValidParentTypes('spike');
    expect(result).toContain('story');
    expect(result).toContain('idea');
  });

  it('enhancement admits milestone, initiative and business_change (EP-24)', () => {
    const result = getValidParentTypes('enhancement');
    expect(result).toContain('milestone');
    expect(result).toContain('initiative');
    expect(result).toContain('business_change');
  });

  it('idea remains a root — still has no parents (EP-24 promoted it as parent, not as child)', () => {
    expect(getValidParentTypes('idea')).toEqual([]);
  });

  it('business_change remains a root — still has no parents (EP-24 promoted it as parent, not as child)', () => {
    expect(getValidParentTypes('business_change')).toEqual([]);
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
