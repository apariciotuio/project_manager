/**
 * API client CSRF + Correlation-ID tests — EP-12 Group 2
 */
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api-client';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';

describe('API client — X-Correlation-ID', () => {
  it('sends X-Correlation-ID header on GET request', async () => {
    let capturedHeader: string | null = null;
    server.use(
      http.get('http://localhost/api/v1/test', ({ request }) => {
        capturedHeader = request.headers.get('X-Correlation-Id');
        return HttpResponse.json({ data: 'ok' });
      }),
    );
    await apiGet('/api/v1/test');
    expect(capturedHeader).toBeTruthy();
    // UUID v4 format
    expect(capturedHeader).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
  });

  it('sends X-Correlation-ID header on POST request', async () => {
    let capturedHeader: string | null = null;
    server.use(
      http.post('http://localhost/api/v1/test', ({ request }) => {
        capturedHeader = request.headers.get('X-Correlation-Id');
        return HttpResponse.json({ data: 'ok' });
      }),
    );
    await apiPost('/api/v1/test', {});
    expect(capturedHeader).toBeTruthy();
  });

  it('generates a different correlation ID per request', async () => {
    const ids: string[] = [];
    server.use(
      http.get('http://localhost/api/v1/test', ({ request }) => {
        const id = request.headers.get('X-Correlation-Id');
        if (id) ids.push(id);
        return HttpResponse.json({ data: 'ok' });
      }),
    );
    await apiGet('/api/v1/test');
    await apiGet('/api/v1/test');
    expect(ids).toHaveLength(2);
    expect(ids[0]).not.toBe(ids[1]);
  });
});

describe('API client — X-CSRF-Token', () => {
  beforeEach(() => {
    // Set csrf_token cookie
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: 'csrf_token=test-csrf-value-123',
    });
  });

  afterEach(() => {
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: '',
    });
  });

  it('does NOT send X-CSRF-Token on GET requests', async () => {
    let capturedHeader: string | null | undefined = undefined;
    server.use(
      http.get('http://localhost/api/v1/test', ({ request }) => {
        capturedHeader = request.headers.get('X-CSRF-Token');
        return HttpResponse.json({ data: 'ok' });
      }),
    );
    await apiGet('/api/v1/test');
    expect(capturedHeader).toBeNull();
  });

  it('sends X-CSRF-Token on POST requests', async () => {
    let capturedHeader: string | null = null;
    server.use(
      http.post('http://localhost/api/v1/test', ({ request }) => {
        capturedHeader = request.headers.get('X-CSRF-Token');
        return HttpResponse.json({ data: 'ok' });
      }),
    );
    await apiPost('/api/v1/test', {});
    expect(capturedHeader).toBe('test-csrf-value-123');
  });

  it('sends X-CSRF-Token on PATCH requests', async () => {
    let capturedHeader: string | null = null;
    server.use(
      http.patch('http://localhost/api/v1/test', ({ request }) => {
        capturedHeader = request.headers.get('X-CSRF-Token');
        return HttpResponse.json({ data: 'ok' });
      }),
    );
    await apiPatch('/api/v1/test', {});
    expect(capturedHeader).toBe('test-csrf-value-123');
  });

  it('sends X-CSRF-Token on DELETE requests', async () => {
    let capturedHeader: string | null = null;
    server.use(
      http.delete('http://localhost/api/v1/test', ({ request }) => {
        capturedHeader = request.headers.get('X-CSRF-Token');
        return HttpResponse.json({ data: 'ok' });
      }),
    );
    await apiDelete('/api/v1/test');
    expect(capturedHeader).toBe('test-csrf-value-123');
  });
});
