import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HumanError } from '@/components/domain/human-error';

describe('HumanError', () => {
  it('renders localized message for known error code', () => {
    render(<HumanError code="workitem.notFound" />);
    expect(screen.getByText(/No encontramos este elemento/)).toBeTruthy();
  });

  it('renders generic error for unknown code', () => {
    render(<HumanError code="some.unknown.code" />);
    expect(screen.getByText(/Algo salió mal/)).toBeTruthy();
  });

  it('message span uses text content only (no dangerouslySetInnerHTML)', () => {
    const { container } = render(<HumanError code="errors.generic" />);
    // The message span should not have HTML tags injected
    const msgSpan = container.querySelector('[data-error] span');
    expect(msgSpan?.innerHTML).toBe(msgSpan?.textContent);
  });

  it('has role alert', () => {
    render(<HumanError code="workitem.notFound" />);
    expect(screen.getByRole('alert')).toBeTruthy();
  });
});
