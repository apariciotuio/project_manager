import '@testing-library/jest-dom';
import { server } from './msw/server';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock pointer capture + scrollIntoView APIs (not implemented in jsdom, required by Radix UI)
if (typeof window !== 'undefined') {
  window.Element.prototype.hasPointerCapture = (_id: number) => false;
  window.Element.prototype.setPointerCapture = (_id: number) => {};
  window.Element.prototype.releasePointerCapture = (_id: number) => {};
  window.Element.prototype.scrollIntoView = () => {};
}

// Mock window.matchMedia (not implemented in jsdom)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});
