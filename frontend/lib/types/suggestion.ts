/**
 * EP-03 — Suggestion set / item types.
 */

export type SuggestionStatus =
  | 'pending'
  | 'partially_applied'
  | 'fully_applied'
  | 'rejected'
  | 'expired';

export type SuggestionItemStatus = 'pending' | 'accepted' | 'rejected';

export interface SuggestionItem {
  id: string;
  section: string;
  current_content: string;
  proposed_content: string;
  rationale: string | null;
  status: SuggestionItemStatus;
}

export interface SuggestionSet {
  id: string;
  work_item_id: string;
  status: SuggestionStatus;
  created_at: string;
  expires_at: string;
  items: SuggestionItem[];
}

export interface ApplySuggestionsResult {
  new_version: number;
  applied_sections: string[];
}
