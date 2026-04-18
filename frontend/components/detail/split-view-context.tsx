'use client';

import { createContext, useContext } from 'react';

export interface SplitViewContextValue {
  /** Section ID to highlight; null when no highlight active */
  highlightedSectionId: string | null;
  setHighlightedSectionId: (id: string | null) => void;
}

export const SplitViewContext = createContext<SplitViewContextValue>({
  highlightedSectionId: null,
  setHighlightedSectionId: () => undefined,
});

export function useSplitView() {
  return useContext(SplitViewContext);
}
