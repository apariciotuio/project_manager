import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CommentInput } from '@/components/comments/CommentInput';

describe('CommentInput', () => {
  it('renders textarea and submit button', () => {
    render(<CommentInput onSubmit={vi.fn()} />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /comentar/i })).toBeInTheDocument();
  });

  it('disables submit when body is empty', () => {
    render(<CommentInput onSubmit={vi.fn()} />);
    expect(screen.getByRole('button', { name: /comentar/i })).toBeDisabled();
  });

  it('enables submit when body is non-empty', async () => {
    render(<CommentInput onSubmit={vi.fn()} />);
    await userEvent.type(screen.getByRole('textbox'), 'Hello');
    expect(screen.getByRole('button', { name: /comentar/i })).toBeEnabled();
  });

  it('calls onSubmit with trimmed body', async () => {
    const onSubmit = vi.fn();
    render(<CommentInput onSubmit={onSubmit} />);
    await userEvent.type(screen.getByRole('textbox'), '  My comment  ');
    await userEvent.click(screen.getByRole('button', { name: /comentar/i }));
    expect(onSubmit).toHaveBeenCalledWith('My comment', undefined);
  });

  it('calls onSubmit via Ctrl+Enter', async () => {
    const onSubmit = vi.fn();
    render(<CommentInput onSubmit={onSubmit} />);
    const textarea = screen.getByRole('textbox');
    await userEvent.type(textarea, 'Keyboard submit');
    await userEvent.keyboard('{Control>}{Enter}{/Control}');
    expect(onSubmit).toHaveBeenCalledWith('Keyboard submit', undefined);
  });

  it('does not call onSubmit on Ctrl+Enter when body is empty', async () => {
    const onSubmit = vi.fn();
    render(<CommentInput onSubmit={onSubmit} />);
    await userEvent.keyboard('{Control>}{Enter}{/Control}');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('passes anchor data as second argument when provided', async () => {
    const onSubmit = vi.fn();
    const anchor = { section_id: 's-1', start: 0, end: 10, snapshot_text: 'hello' };
    render(<CommentInput onSubmit={onSubmit} anchor={anchor} />);
    await userEvent.type(screen.getByRole('textbox'), 'Anchored comment');
    await userEvent.click(screen.getByRole('button', { name: /comentar/i }));
    expect(onSubmit).toHaveBeenCalledWith('Anchored comment', anchor);
  });

  it('shows loading state when isLoading is true', () => {
    render(<CommentInput onSubmit={vi.fn()} isLoading />);
    expect(screen.getByRole('button', { name: /enviando/i })).toBeDisabled();
    expect(screen.getByRole('textbox')).toBeDisabled();
  });

  it('shows error message when error is set', () => {
    render(<CommentInput onSubmit={vi.fn()} error="Network error" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Network error');
  });

  it('clears body after successful submit', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<CommentInput onSubmit={onSubmit} />);
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    await userEvent.type(textarea, 'To be cleared');
    await userEvent.click(screen.getByRole('button', { name: /comentar/i }));
    // Wait for async onSubmit
    await vi.waitFor(() => expect(textarea.value).toBe(''));
  });

  it('renders disabled attachment button with EP-16 TODO', () => {
    render(<CommentInput onSubmit={vi.fn()} />);
    const attachBtn = screen.getByRole('button', { name: /adjuntar/i });
    expect(attachBtn).toBeDisabled();
  });
});
