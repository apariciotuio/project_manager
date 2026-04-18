'use client';

import { useSplitView } from '@/components/detail/split-view-context';
import type { PendingSuggestion } from '@/components/detail/split-view-context';

/**
 * EP-22: Returns the pending suggestion for a given section_type (or undefined),
 * plus the clearSuggestion function. Keeps SectionRow clean.
 */
export function usePendingSuggestion(sectionType: string): {
  suggestion: PendingSuggestion | undefined;
  clear: () => void;
} {
  const { pendingSuggestions, clearSuggestion } = useSplitView();
  return {
    suggestion: pendingSuggestions[sectionType],
    clear: () => clearSuggestion(sectionType),
  };
}
