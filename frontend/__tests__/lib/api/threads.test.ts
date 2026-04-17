import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { getThreads, createThread, getThreadHistory, archiveThread } from '@/lib/api/threads';
import type { ConversationThread, ConversationMessage } from '@/lib/types/conversation';

const BASE = 'http://localhost';

const mockThread: ConversationThread = {
  id: 'thread-1',
  work_item_id: 'wi-1',
  user_id: 'user-1',
  dundun_conversation_id: 'dundun-conv-1',
  last_message_preview: 'Hello',
  last_message_at: '2026-04-17T10:00:00Z',
  created_at: '2026-04-17T09:00:00Z',
};

const mockMessage: ConversationMessage = {
  id: 'msg-1',
  role: 'user',
  content: 'Hello Dundun',
  created_at: '2026-04-17T10:00:00Z',
};

describe('getThreads', () => {
  it('returns thread list', async () => {
    server.use(
      http.get(`${BASE}/api/v1/threads`, () =>
        HttpResponse.json({ data: [mockThread] }),
      ),
    );
    const result = await getThreads();
    expect(result).toHaveLength(1);
    expect(result[0]!.id).toBe('thread-1');
  });

  it('passes work_item_id as query param', async () => {
    let capturedUrl = '';
    server.use(
      http.get(`${BASE}/api/v1/threads`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ data: [mockThread] });
      }),
    );
    await getThreads('wi-1');
    expect(capturedUrl).toContain('work_item_id=wi-1');
  });
});

describe('createThread', () => {
  it('creates a thread and returns it', async () => {
    server.use(
      http.post(`${BASE}/api/v1/threads`, () =>
        HttpResponse.json({ data: mockThread }),
      ),
    );
    const result = await createThread({ work_item_id: 'wi-1' });
    expect(result.id).toBe('thread-1');
  });
});

describe('getThreadHistory', () => {
  it('returns message list', async () => {
    server.use(
      http.get(`${BASE}/api/v1/threads/thread-1/history`, () =>
        HttpResponse.json({ data: [mockMessage] }),
      ),
    );
    const result = await getThreadHistory('thread-1');
    expect(result).toHaveLength(1);
    expect(result[0]!.role).toBe('user');
  });

  it('returns empty array when history is empty', async () => {
    server.use(
      http.get(`${BASE}/api/v1/threads/thread-1/history`, () =>
        HttpResponse.json({ data: [] }),
      ),
    );
    const result = await getThreadHistory('thread-1');
    expect(result).toEqual([]);
  });
});

describe('archiveThread', () => {
  it('calls DELETE without throwing', async () => {
    server.use(
      http.delete(`${BASE}/api/v1/threads/thread-1`, () =>
        new HttpResponse(null, { status: 204 }),
      ),
    );
    await expect(archiveThread('thread-1')).resolves.toBeUndefined();
  });
});
