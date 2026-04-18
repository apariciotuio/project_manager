/**
 * EP-03 — Conversation / thread types.
 * Thread pointer to Dundun; message history fetched on demand.
 */

export type MessageType = 'progress' | 'response' | 'error';
export type AuthorRole = 'user' | 'assistant' | 'system';

export interface ConversationThread {
  id: string;
  work_item_id: string | null;
  user_id: string;
  dundun_conversation_id: string;
  last_message_preview: string | null;
  last_message_at: string | null;
  created_at: string;
}

export interface ConversationMessage {
  id: string;
  role: AuthorRole;
  content: string;
  created_at: string;
}

/** EP-22 v2 — signals block in a response frame (real Dundun-Morpheo contract) */
export interface ConversationSignals {
  conversation_ended?: boolean;
}

/** Frames forwarded verbatim from Dundun over WebSocket */
export type WsFrame =
  | { type: 'progress'; content: string }
  | { type: 'response'; response: string; signals?: ConversationSignals }
  | { type: 'error'; code: string; message: string };

// ---------------------------------------------------------------------------
// EP-22 v2 — MorpheoResponse discriminated union (real contract)
// ---------------------------------------------------------------------------

export type MorpheoQuestion = {
  kind: 'question';
  message: string;
  clarifications?: Array<{ field: string; question: string }>;
};

export type MorpheoSectionSuggestion = {
  kind: 'section_suggestion';
  message: string;
  suggested_sections: Array<{
    section_type: string;
    proposed_content: string;
    rationale?: string;
  }>;
  clarifications?: Array<{ field: string; question: string }>;
};

export type MorpheoPoReview = {
  kind: 'po_review';
  message: string;
  po_review: {
    score: number;
    verdict: 'approved' | 'needs_work' | 'rejected';
    agents_consulted: string[];
    per_dimension: Array<{
      dimension: string;
      score: number;
      verdict: 'approved' | 'needs_work' | 'rejected';
      findings: Array<{
        severity: 'low' | 'medium' | 'high' | 'critical';
        title: string;
        description: string;
      }>;
      missing_info: Array<{ field: string; question: string }>;
    }>;
    action_items: Array<{
      priority: 'low' | 'medium' | 'high' | 'critical';
      title: string;
      description: string;
      owner: string;
    }>;
  };
  comments?: string[];
  clarifications?: Array<{ field: string; question: string }>;
};

export type MorpheoError = { kind: 'error'; message: string };

export type MorpheoResponse =
  | MorpheoQuestion
  | MorpheoSectionSuggestion
  | MorpheoPoReview
  | MorpheoError;
