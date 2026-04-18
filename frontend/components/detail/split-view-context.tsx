'use client';

import { createContext, useContext } from 'react';

export interface PendingSuggestion {
  section_type: string;
  proposed_content: string;
  rationale: string;
  /** ms since epoch, used for de-dup / replace semantics */
  received_at: number;
}

export interface SplitViewContextValue {
  /** Section ID to highlight; null when no highlight active */
  highlightedSectionId: string | null;
  setHighlightedSectionId: (id: string | null) => void;

  /**
   * Pending suggestions keyed by section_type.
   *
   * TODO(EP-22-full): ChatPanel populates this map once the Dundun cross-repo
   * changes (PR #1 ConversationSignals + PR #2 prompt update) are merged.
   * Until then the map is always empty — the context API exists so EP-22-full
   * can wire it in without touching this file or WorkItemDetailLayout.
   */
  pendingSuggestions: Record<string, PendingSuggestion>;

  /** Upsert a pending suggestion for a section_type (latest wins). */
  emitSuggestion: (sug: PendingSuggestion) => void;

  /** Remove the pending suggestion for a section_type. */
  clearSuggestion: (section_type: string) => void;
}

export const SplitViewContext = createContext<SplitViewContextValue>({
  highlightedSectionId: null,
  setHighlightedSectionId: () => undefined,
  pendingSuggestions: {},
  emitSuggestion: () => undefined,
  clearSuggestion: () => undefined,
});

export function useSplitView() {
  return useContext(SplitViewContext);
}
