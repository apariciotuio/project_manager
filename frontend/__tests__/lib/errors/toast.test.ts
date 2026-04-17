import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { showErrorToast } from '@/lib/errors/toast';

describe('showErrorToast', () => {
  beforeEach(() => {
    // Clean up any leftover toast containers between tests
    document.body.innerHTML = '';
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = '';
  });

  it('renders a toast with the code and message', () => {
    showErrorToast('INTERNAL_ERROR', 'Something broke');
    const alert = document.querySelector('[role="alert"]');
    expect(alert).not.toBeNull();
    expect(alert?.textContent).toMatch(/INTERNAL_ERROR/);
    expect(alert?.textContent).toMatch(/Something broke/);
  });

  it('does not render duplicate toasts for the same code+message within window', () => {
    showErrorToast('NOT_FOUND', 'Resource not found');
    showErrorToast('NOT_FOUND', 'Resource not found');
    const alerts = document.querySelectorAll('[role="alert"]');
    expect(alerts).toHaveLength(1);
  });

  it('deduplicates toasts when message contains spaces and special chars', () => {
    const msg = 'Field "name" is required (cannot be empty)';
    showErrorToast('VALIDATION_ERROR', msg);
    showErrorToast('VALIDATION_ERROR', msg);
    const alerts = document.querySelectorAll('[role="alert"]');
    expect(alerts).toHaveLength(1);
  });

  it('deduplicates toasts when message contains non-ASCII characters', () => {
    const msg = 'El campo "nombre" es obligatorio — véalo aquí';
    showErrorToast('VALIDATION_ERROR', msg);
    showErrorToast('VALIDATION_ERROR', msg);
    const alerts = document.querySelectorAll('[role="alert"]');
    expect(alerts).toHaveLength(1);
  });

  it('shows two toasts when code+message differ', () => {
    showErrorToast('NOT_FOUND', 'Resource A not found');
    showErrorToast('NOT_FOUND', 'Resource B not found');
    const alerts = document.querySelectorAll('[role="alert"]');
    expect(alerts).toHaveLength(2);
  });

  it('auto-dismisses after 6 seconds', () => {
    showErrorToast('ERROR', 'Will vanish');
    expect(document.querySelectorAll('[role="alert"]')).toHaveLength(1);
    vi.advanceTimersByTime(6001);
    expect(document.querySelectorAll('[role="alert"]')).toHaveLength(0);
  });

  it('dismiss button removes the toast immediately', () => {
    showErrorToast('ERROR', 'Dismissible');
    const btn = document.querySelector('button[aria-label="Dismiss"]') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    btn.click();
    expect(document.querySelectorAll('[role="alert"]')).toHaveLength(0);
  });
});
