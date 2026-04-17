/**
 * E2E smoke test — Playwright
 *
 * Prerequisites to run manually:
 *   cd frontend && npm run dev   (or have the backend up for health checks)
 *   npx playwright test
 *
 * In CI this is skipped unless PLAYWRIGHT_RUN=true because the backend must be running.
 * Run manually: npm run test:e2e
 */
import { test, expect } from '@playwright/test';

test('home page shows the platform title', async ({ page }) => {
  await page.goto('/');
  const heading = page.getByRole('heading', { level: 1 });
  await expect(heading).toBeVisible();
  await expect(heading).toHaveText('Work Maturation Platform');
});

test('home page has a theme toggle button', async ({ page }) => {
  await page.goto('/');
  const toggle = page.getByRole('button', { name: /tema|theme/i });
  await expect(toggle).toBeVisible();
});
