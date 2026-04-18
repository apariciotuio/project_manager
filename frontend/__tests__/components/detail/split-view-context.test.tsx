import { describe, it, expect } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import {
  SplitViewContext,
  useSplitView,
} from '@/components/detail/split-view-context';
import type { SplitViewContextValue, PendingSuggestion } from '@/components/detail/split-view-context';
import { useState } from 'react';

// Consumer helper — renders context fields as data-testid attributes
function Consumer() {
  const ctx = useSplitView();
  const suggestions = ctx.pendingSuggestions;
  const keys = Object.keys(suggestions).join(',');
  return (
    <div>
      <span data-testid="highlighted">{ctx.highlightedSectionId ?? 'null'}</span>
      <span data-testid="suggestion-keys">{keys}</span>
      <button
        data-testid="emit-btn"
        onClick={() =>
          ctx.emitSuggestion({
            section_type: 'problem_statement',
            proposed_content: 'Proposed content',
            rationale: 'Some rationale',
            received_at: 1000,
          })
        }
      >
        emit
      </button>
      <button
        data-testid="emit-replace-btn"
        onClick={() =>
          ctx.emitSuggestion({
            section_type: 'problem_statement',
            proposed_content: 'Replaced content',
            rationale: 'New rationale',
            received_at: 2000,
          })
        }
      >
        emit-replace
      </button>
      <button
        data-testid="clear-btn"
        onClick={() => ctx.clearSuggestion('problem_statement')}
      >
        clear
      </button>
      <button
        data-testid="highlight-btn"
        onClick={() => ctx.setHighlightedSectionId('sec-42')}
      >
        highlight
      </button>
    </div>
  );
}

// Stateful provider that owns pendingSuggestions + highlightedSectionId state
function TestProvider({ children }: { children: React.ReactNode }) {
  const [pendingSuggestions, setPendingSuggestions] = useState<
    Record<string, PendingSuggestion>
  >({});
  const [highlightedSectionId, setHighlightedSectionId] = useState<
    string | null
  >(null);

  const emitSuggestion = (sug: PendingSuggestion) => {
    setPendingSuggestions((prev) => ({ ...prev, [sug.section_type]: sug }));
  };

  const clearSuggestion = (section_type: string) => {
    setPendingSuggestions((prev) => {
      const next = { ...prev };
      delete next[section_type];
      return next;
    });
  };

  const value: SplitViewContextValue = {
    highlightedSectionId,
    setHighlightedSectionId,
    pendingSuggestions,
    emitSuggestion,
    clearSuggestion,
  };

  return (
    <SplitViewContext.Provider value={value}>
      {children}
    </SplitViewContext.Provider>
  );
}

describe('SplitViewContext — pendingSuggestions', () => {
  it('provides empty pendingSuggestions and safe emit/clear by default (no-op defaults)', () => {
    render(
      <SplitViewContext.Provider
        value={{
          highlightedSectionId: null,
          setHighlightedSectionId: () => undefined,
          pendingSuggestions: {},
          emitSuggestion: () => undefined,
          clearSuggestion: () => undefined,
        }}
      >
        <Consumer />
      </SplitViewContext.Provider>,
    );
    expect(screen.getByTestId('suggestion-keys').textContent).toBe('');
    // clicking emit/clear with no-op handlers should not crash
    fireEvent.click(screen.getByTestId('emit-btn'));
    fireEvent.click(screen.getByTestId('clear-btn'));
  });

  it('emitSuggestion stores a pending suggestion keyed by section_type', () => {
    render(
      <TestProvider>
        <Consumer />
      </TestProvider>,
    );
    fireEvent.click(screen.getByTestId('emit-btn'));
    expect(screen.getByTestId('suggestion-keys').textContent).toBe(
      'problem_statement',
    );
  });

  it('re-emit for same section_type replaces the previous entry', () => {
    render(
      <TestProvider>
        <Consumer />
      </TestProvider>,
    );
    fireEvent.click(screen.getByTestId('emit-btn'));
    fireEvent.click(screen.getByTestId('emit-replace-btn'));
    // Still only one key
    expect(screen.getByTestId('suggestion-keys').textContent).toBe(
      'problem_statement',
    );
  });

  it('clearSuggestion removes the entry', () => {
    render(
      <TestProvider>
        <Consumer />
      </TestProvider>,
    );
    fireEvent.click(screen.getByTestId('emit-btn'));
    fireEvent.click(screen.getByTestId('clear-btn'));
    expect(screen.getByTestId('suggestion-keys').textContent).toBe('');
  });

  it('highlightedSectionId still works independently of pendingSuggestions', () => {
    render(
      <TestProvider>
        <Consumer />
      </TestProvider>,
    );
    expect(screen.getByTestId('highlighted').textContent).toBe('null');
    fireEvent.click(screen.getByTestId('highlight-btn'));
    expect(screen.getByTestId('highlighted').textContent).toBe('sec-42');
    // suggestion state unchanged
    expect(screen.getByTestId('suggestion-keys').textContent).toBe('');
  });
});
