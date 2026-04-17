'use client';

import { useState, useCallback } from 'react';
import { ApiError } from './api-error';
import { showErrorToast } from './toast';

export interface UseFormErrorsResult {
  fieldErrors: Record<string, string>;
  handleApiError: (err: unknown) => void;
  clearErrors: () => void;
}

/**
 * Maps an ApiError to field-level UI errors or a toast notification.
 *
 * - If ApiError has a `field`, sets fieldErrors[field] = message.
 * - If ApiError has no field, fires showErrorToast(code, message).
 * - Plain Error falls back to toast with code "ERROR".
 */
export function useFormErrors(): UseFormErrorsResult {
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const handleApiError = useCallback((err: unknown): void => {
    if (err instanceof ApiError) {
      if (err.field) {
        setFieldErrors({ [err.field]: err.message });
      } else {
        showErrorToast(err.code, err.message);
      }
    } else if (err instanceof Error) {
      showErrorToast('ERROR', err.message);
    } else {
      showErrorToast('ERROR', String(err));
    }
  }, []);

  const clearErrors = useCallback((): void => {
    setFieldErrors({});
  }, []);

  return { fieldErrors, handleApiError, clearErrors };
}
