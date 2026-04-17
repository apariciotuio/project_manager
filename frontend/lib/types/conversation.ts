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

/** Frames forwarded verbatim from Dundun over WebSocket */
export type WsFrame =
  | { type: 'progress'; content: string }
  | { type: 'response'; content: string; message_id: string }
  | { type: 'error'; code: string; message: string };
