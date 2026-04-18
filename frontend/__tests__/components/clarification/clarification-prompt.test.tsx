import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ClarificationPrompt } from '@/components/clarification/clarification-prompt';

describe('ClarificationPrompt', () => {
  it('renders message text', () => {
    render(<ClarificationPrompt message="What is the target user?" clarifications={[]} />);
    expect(screen.getByText('What is the target user?')).toBeInTheDocument();
  });

  it('renders each clarification field and question', () => {
    render(
      <ClarificationPrompt
        message="Please clarify:"
        clarifications={[
          { field: 'target_user', question: 'B2C or B2B?' },
          { field: 'budget', question: 'What is the budget?' },
        ]}
      />,
    );
    expect(screen.getByText('B2C or B2B?')).toBeInTheDocument();
    expect(screen.getByText('What is the budget?')).toBeInTheDocument();
  });

  it('renders empty clarifications without crashing', () => {
    render(<ClarificationPrompt message="No questions." clarifications={[]} />);
    expect(screen.getByText('No questions.')).toBeInTheDocument();
  });

  it('renders with no clarifications prop', () => {
    render(<ClarificationPrompt message="Just a message." />);
    expect(screen.getByText('Just a message.')).toBeInTheDocument();
  });

  it('has accessible role for assistive technologies', () => {
    render(
      <ClarificationPrompt
        message="Clarification needed."
        clarifications={[{ field: 'foo', question: 'Bar?' }]}
      />,
    );
    // Should have data-testid for test targeting
    expect(screen.getByTestId('clarification-prompt')).toBeInTheDocument();
  });

  it('field label is visible alongside question', () => {
    render(
      <ClarificationPrompt
        message="Msg"
        clarifications={[{ field: 'rollback_plan', question: 'What is the rollback plan?' }]}
      />,
    );
    expect(screen.getByText(/rollback_plan/)).toBeInTheDocument();
    expect(screen.getByText('What is the rollback plan?')).toBeInTheDocument();
  });
});
