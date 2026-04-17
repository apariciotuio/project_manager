import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { ApiError } from '@/lib/errors/api-error';
import { useFormErrors } from '@/lib/errors/use-form-errors';

// Mock the toast module
vi.mock('@/lib/errors/toast', () => ({
  showErrorToast: vi.fn(),
}));

import { showErrorToast } from '@/lib/errors/toast';

describe('useFormErrors', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('initially has no field errors', () => {
    const { result } = renderHook(() => useFormErrors());
    expect(result.current.fieldErrors).toEqual({});
  });

  describe('handleApiError — field mapping', () => {
    it('maps field to error message when field is present', () => {
      const { result } = renderHook(() => useFormErrors());
      const err = new ApiError(409, { code: 'TAG_NAME_TAKEN', message: 'Tag name is taken', field: 'name' });

      act(() => {
        result.current.handleApiError(err);
      });

      expect(result.current.fieldErrors).toEqual({ name: 'Tag name is taken' });
    });

    it('maps user_id field for team member error', () => {
      const { result } = renderHook(() => useFormErrors());
      const err = new ApiError(409, { code: 'TEAM_MEMBER_ALREADY_EXISTS', message: 'Already a member', field: 'user_id' });

      act(() => {
        result.current.handleApiError(err);
      });

      expect(result.current.fieldErrors).toEqual({ user_id: 'Already a member' });
    });

    it('does NOT call toast when field is present', () => {
      const { result } = renderHook(() => useFormErrors());
      const err = new ApiError(409, { code: 'TAG_NAME_TAKEN', message: 'taken', field: 'name' });

      act(() => {
        result.current.handleApiError(err);
      });

      expect(showErrorToast).not.toHaveBeenCalled();
    });
  });

  describe('handleApiError — toast fallback for non-field errors', () => {
    it('calls showErrorToast when no field', () => {
      const { result } = renderHook(() => useFormErrors());
      const err = new ApiError(500, { code: 'INTERNAL_ERROR', message: 'Something went wrong' });

      act(() => {
        result.current.handleApiError(err);
      });

      expect(showErrorToast).toHaveBeenCalledWith('INTERNAL_ERROR', 'Something went wrong');
    });

    it('does not set fieldErrors when no field', () => {
      const { result } = renderHook(() => useFormErrors());
      const err = new ApiError(500, { code: 'INTERNAL_ERROR', message: 'oops' });

      act(() => {
        result.current.handleApiError(err);
      });

      expect(result.current.fieldErrors).toEqual({});
    });

    it('shows toast with UNKNOWN code for legacy errors', () => {
      const { result } = renderHook(() => useFormErrors());
      const err = new ApiError(404, { code: 'UNKNOWN', message: 'Not found' });

      act(() => {
        result.current.handleApiError(err);
      });

      expect(showErrorToast).toHaveBeenCalledWith('UNKNOWN', 'Not found');
    });
  });

  describe('handleApiError — multiple field errors accumulate', () => {
    it('merges field errors across consecutive calls without clearing', () => {
      const { result } = renderHook(() => useFormErrors());
      const err1 = new ApiError(422, { code: 'VALIDATION_ERROR', message: 'Required', field: 'name' });
      const err2 = new ApiError(422, { code: 'VALIDATION_ERROR', message: 'Too short', field: 'description' });

      act(() => {
        result.current.handleApiError(err1);
      });
      act(() => {
        result.current.handleApiError(err2);
      });

      expect(result.current.fieldErrors).toEqual({
        name: 'Required',
        description: 'Too short',
      });
    });

    it('overwrites same field with latest message', () => {
      const { result } = renderHook(() => useFormErrors());
      const err1 = new ApiError(422, { code: 'VALIDATION_ERROR', message: 'First', field: 'name' });
      const err2 = new ApiError(422, { code: 'VALIDATION_ERROR', message: 'Second', field: 'name' });

      act(() => {
        result.current.handleApiError(err1);
      });
      act(() => {
        result.current.handleApiError(err2);
      });

      expect(result.current.fieldErrors).toEqual({ name: 'Second' });
    });
  });

  describe('clearErrors', () => {
    it('clears field errors', () => {
      const { result } = renderHook(() => useFormErrors());
      const err = new ApiError(409, { code: 'TAG_NAME_TAKEN', message: 'taken', field: 'name' });

      act(() => {
        result.current.handleApiError(err);
      });
      expect(result.current.fieldErrors).toEqual({ name: 'taken' });

      act(() => {
        result.current.clearErrors();
      });
      expect(result.current.fieldErrors).toEqual({});
    });
  });

  describe('non-ApiError passthrough', () => {
    it('calls toast for plain Error', () => {
      const { result } = renderHook(() => useFormErrors());
      const err = new Error('Network error');

      act(() => {
        result.current.handleApiError(err);
      });

      expect(showErrorToast).toHaveBeenCalledWith('ERROR', 'Network error');
    });
  });
});
