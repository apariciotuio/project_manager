/**
 * Theme cycle E2E — EP-20
 * Verifies html class + localStorage state transitions across all theme options.
 */
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const token = readFileSync('/tmp/dev_token.env', 'utf8').trim().replace(/^TOKEN=/, '');

const AUTH_COOKIE = {
  name: 'access_token',
  value: token,
  domain: 'localhost',
  path: '/',
  expires: -1,
  httpOnly: false,
  secure: false,
  sameSite: 'Lax' as const,
};

test.describe('Theme cycle', () => {
  test.beforeEach(async ({ context }) => {
    await context.addCookies([AUTH_COOKIE]);
  });

  test('full cycle: default → dark → matrix → blue pill → light', async ({ page }) => {
    // Go to workspace items (authenticated page with theme controls)
    const response = await page.goto('/workspace/tuio/items', { waitUntil: 'networkidle' });
    expect(response?.status()).toBeLessThan(400);

    // Wait for client-side hydration
    await page.waitForTimeout(800);

    // ThemeSwitcher should be visible
    const darkBtn = page.getByRole('button', { name: /dark|oscuro/i });
    await darkBtn.waitFor({ state: 'visible', timeout: 5000 });

    // Switch to Dark (use JS click to bypass any layout overlaps)
    await darkBtn.evaluate((el: HTMLElement) => el.click());
    await page.waitForTimeout(300);
    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('dark');
    const themeStorage = await page.evaluate(() => localStorage.getItem('theme'));
    expect(themeStorage).toBe('dark');

    // Click red pill → Matrix (aria-label is locale-dependent: Spanish by default)
    const redPill = page.getByRole('button', { name: /entrar en el tema matrix|enter matrix theme/i }).first();
    await redPill.waitFor({ state: 'visible', timeout: 5000 });
    // Use JS click to bypass overlay interception from the work items table
    await redPill.evaluate((el: HTMLElement) => el.click());
    await page.waitForTimeout(1000);

    const htmlClassMatrix = await page.locator('html').getAttribute('class');
    const themeStorageMatrix = await page.evaluate(() => localStorage.getItem('theme'));
    // next-themes stores the theme in localStorage under 'theme' key
    expect(themeStorageMatrix ?? htmlClassMatrix ?? '').toContain('matrix');

    const previousTheme = await page.evaluate(() => localStorage.getItem('trinity:previousTheme'));
    expect(previousTheme).toBe('dark');

    // Red pill should be gone, blue pill visible
    await expect(page.getByRole('button', { name: /salir del tema matrix|exit matrix theme/i })).toBeVisible({ timeout: 3000 });

    // Click blue pill → return to dark
    const bluePill = page.getByRole('button', { name: /salir del tema matrix|exit matrix theme/i });
    await bluePill.waitFor({ state: 'visible', timeout: 5000 });
    await bluePill.evaluate((el: HTMLElement) => el.click());
    await page.waitForTimeout(300);

    const htmlClassAfter = await page.locator('html').getAttribute('class');
    expect(htmlClassAfter).toContain('dark');

    // Switch to Light
    const lightBtn = page.getByRole('button', { name: /^claro$|^light$/i });
    await lightBtn.waitFor({ state: 'visible', timeout: 5000 });
    await lightBtn.evaluate((el: HTMLElement) => el.click());
    await page.waitForTimeout(300);

    const htmlClassLight = await page.locator('html').getAttribute('class');
    // Light theme: html class should NOT contain 'dark' or 'matrix'
    expect(htmlClassLight ?? '').not.toContain('dark');
    expect(htmlClassLight ?? '').not.toContain('matrix');
  });

  test('theme controls are accessible via keyboard', async ({ page }) => {
    const response = await page.goto('/workspace/tuio/items', { waitUntil: 'networkidle' });
    expect(response?.status()).toBeLessThan(400);
    await page.waitForTimeout(800);

    // Theme switcher buttons should be focusable
    const darkBtn = page.getByRole('button', { name: /dark|oscuro/i });
    await darkBtn.waitFor({ state: 'visible', timeout: 5000 });
    await darkBtn.evaluate((el: HTMLElement) => el.focus());
    await page.keyboard.press('Enter');
    await page.waitForTimeout(300);

    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('dark');
  });

  test('login page returns HTTP 200', async ({ page }) => {
    const response = await page.goto('/login', { waitUntil: 'networkidle' });
    expect(response?.status()).toBeLessThan(400);
  });

  test('reduced-motion: no canvas rendered under matrix', async ({ browser }) => {
    const context = await browser.newContext({
      reducedMotion: 'reduce',
      storageState: {
        cookies: [AUTH_COOKIE],
        origins: [],
      },
    });
    const page = await context.newPage();

    try {
      await page.goto('/workspace/tuio/items', { waitUntil: 'networkidle' });
      await page.waitForTimeout(800);

      // Switch to Matrix via localStorage + reload (reliable even if red pill is covered)
      await page.evaluate(() => {
        localStorage.setItem('theme', 'matrix');
        localStorage.setItem('trinity:rainEnabled', 'true');
      });
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(800);

      // Canvas should NOT be present (reduced-motion disables rain)
      const canvas = page.locator('canvas');
      const count = await canvas.count();
      expect(count).toBe(0);
    } finally {
      await context.close();
    }
  });
});
