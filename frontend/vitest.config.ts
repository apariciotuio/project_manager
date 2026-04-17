import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['__tests__/setup.ts'],
    include: ['__tests__/**/*.test.{ts,tsx}'],
    exclude: ['__tests__/e2e/**', 'node_modules/**'],
    env: {
      NEXT_PUBLIC_API_BASE_URL: 'http://localhost',
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
    },
  },
});
