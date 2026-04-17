import { describe, it, expect } from 'vitest';
import { ApiError } from '@/lib/errors/api-error';

describe('ApiError', () => {
  describe('constructor', () => {
    it('is instanceof Error', () => {
      const err = new ApiError(400, { code: 'VALIDATION_ERROR', message: 'bad' });
      expect(err).toBeInstanceOf(Error);
      expect(err).toBeInstanceOf(ApiError);
    });

    it('sets code, message, status', () => {
      const err = new ApiError(422, { code: 'WORK_ITEM_INVALID_TRANSITION', message: 'bad transition' });
      expect(err.code).toBe('WORK_ITEM_INVALID_TRANSITION');
      expect(err.message).toBe('bad transition');
      expect(err.status).toBe(422);
    });

    it('sets field when provided', () => {
      const err = new ApiError(409, { code: 'TAG_NAME_TAKEN', message: 'taken', field: 'name' });
      expect(err.field).toBe('name');
    });

    it('field is undefined when not provided', () => {
      const err = new ApiError(500, { code: 'INTERNAL_ERROR', message: 'oops' });
      expect(err.field).toBeUndefined();
    });

    it('sets details when provided', () => {
      const details = { from: 'done', to: 'inbox' };
      const err = new ApiError(422, { code: 'WORK_ITEM_INVALID_TRANSITION', message: 'bad', details });
      expect(err.details).toEqual(details);
    });

    it('has name ApiError', () => {
      const err = new ApiError(400, { code: 'X', message: 'y' });
      expect(err.name).toBe('ApiError');
    });
  });

  describe('fromResponse — new envelope', () => {
    it('parses { error: { code, message } }', async () => {
      const body = { error: { code: 'NOT_FOUND', message: 'Not found' } };
      const response = new Response(JSON.stringify(body), { status: 404 });
      const err = await ApiError.fromResponse(response, body);
      expect(err.code).toBe('NOT_FOUND');
      expect(err.message).toBe('Not found');
      expect(err.status).toBe(404);
    });

    it('parses field from new envelope', async () => {
      const body = { error: { code: 'TAG_NAME_TAKEN', message: 'taken', field: 'name' } };
      const response = new Response(JSON.stringify(body), { status: 409 });
      const err = await ApiError.fromResponse(response, body);
      expect(err.field).toBe('name');
    });

    it('parses details from new envelope', async () => {
      const details = { from: 'done', to: 'inbox' };
      const body = { error: { code: 'WORK_ITEM_INVALID_TRANSITION', message: 'bad', details } };
      const response = new Response(JSON.stringify(body), { status: 422 });
      const err = await ApiError.fromResponse(response, body);
      expect(err.details).toEqual(details);
    });
  });

  describe('fromResponse — legacy { detail } shape', () => {
    it('produces code UNKNOWN from detail string', async () => {
      const body = { detail: 'Not found' };
      const response = new Response(JSON.stringify(body), { status: 404 });
      const err = await ApiError.fromResponse(response, body);
      expect(err.code).toBe('UNKNOWN');
      expect(err.message).toBe('Not found');
      expect(err.status).toBe(404);
    });

    it('no field on legacy shape', async () => {
      const body = { detail: 'Something failed' };
      const response = new Response(JSON.stringify(body), { status: 400 });
      const err = await ApiError.fromResponse(response, body);
      expect(err.field).toBeUndefined();
    });
  });

  describe('fromResponse — malformed body', () => {
    it('falls back to status text on empty object', async () => {
      const response = new Response('{}', { status: 500, statusText: 'Internal Server Error' });
      const err = await ApiError.fromResponse(response, {});
      expect(err.code).toBe('UNKNOWN');
      expect(err.status).toBe(500);
    });

    it('handles null body', async () => {
      const response = new Response('null', { status: 503 });
      const err = await ApiError.fromResponse(response, null);
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(503);
    });

    it('handles non-object body', async () => {
      const response = new Response('"error string"', { status: 500 });
      const err = await ApiError.fromResponse(response, 'error string');
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(500);
    });
  });

  describe('status preservation', () => {
    it('preserves 400', async () => {
      const body = { error: { code: 'VALIDATION_ERROR', message: 'bad' } };
      const response = new Response(JSON.stringify(body), { status: 400 });
      const err = await ApiError.fromResponse(response, body);
      expect(err.status).toBe(400);
    });

    it('preserves 409', async () => {
      const body = { error: { code: 'TEAM_MEMBER_ALREADY_EXISTS', message: 'already member', field: 'user_id' } };
      const response = new Response(JSON.stringify(body), { status: 409 });
      const err = await ApiError.fromResponse(response, body);
      expect(err.status).toBe(409);
    });
  });
});
