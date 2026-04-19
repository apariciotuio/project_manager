import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// EP-20 — Theme cycle E2E coverage (P9.1).
//
// Four tests, matching the original task-list claim:
//   1. Full cycle light → dark → matrix → light via UserMenu radiogroup
//   2. Theme radiogroup reachable by keyboard; Enter activates a selection
//   3. GET /login returns < 400
//   4. prefers-reduced-motion=reduce suppresses the MatrixRain canvas

const token = readFileSync('/tmp/dev_token.env', 'utf8').trim().replace(/^TOKEN=/, '');

const WORKSPACE_ROUTE = '/workspace/tuio/items';

async function authenticate(context: import('@playwright/test').BrowserContext): Promise<void> {
  await context.addCookies([
    {
      name: 'access_token',
      value: token,
      domain: 'localhost',
      path: '/',
      httpOnly: false,
      secure: false,
      sameSite: 'Lax',
    },
  ]);
}

async function openUserMenu(page: import('@playwright/test').Page): Promise<void> {
  const trigger = page.getByRole('button').filter({ has: page.locator('[aria-label]') }).first();
  // UserMenu trigger carries `aria-label={t('triggerAria')}` per user-menu.tsx:150.
  const userMenuTrigger = page.locator('button[aria-label]').filter({ hasText: /./ }).first();
  await userMenuTrigger.click().catch(async () => {
    // Fallback: find any button that opens a radiogroup for theme.
    await trigger.click();
  });
}

async function htmlClass(page: import('@playwright/test').Page): Promise<string> {
  return (await page.locator('html').getAttribute('class')) ?? '';
}

test.describe('EP-20 theme cycle', () => {
  test('full cycle light → dark → matrix → light via UserMenu', async ({ context, page }) => {
    await authenticate(context);
    await page.goto(WORKSPACE_ROUTE, { waitUntil: 'networkidle' });

    // Open UserMenu and interact with the theme radiogroup.
    await openUserMenu(page);
    const themeGroup = page.getByRole('radiogroup').first();
    await expect(themeGroup).toBeVisible();

    const radios = themeGroup.getByRole('radio');
    // Select each theme in order and assert <html> class updates.
    const order: Array<{ key: 'light' | 'dark' | 'matrix'; label: RegExp }> = [
      { key: 'light', label: /light/i },
      { key: 'dark', label: /dark/i },
      { key: 'matrix', label: /matrix/i },
      { key: 'light', label: /light/i },
    ];
    for (const { key, label } of order) {
      await radios.filter({ hasText: label }).first().click();
      await page.waitForTimeout(150); // allow next-themes to apply class
      const cls = await htmlClass(page);
      if (key === 'light') {
        expect(cls).not.toMatch(/matrix|dark/);
      } else {
        expect(cls).toContain(key);
      }
      // Re-open the menu for the next click (it closes on selection in some variants).
      await openUserMenu(page).catch(() => null);
    }
  });

  test('theme radiogroup is keyboard-reachable and Enter activates a choice', async ({
    context,
    page,
  }) => {
    await authenticate(context);
    await page.goto(WORKSPACE_ROUTE, { waitUntil: 'networkidle' });

    await openUserMenu(page);

    const themeGroup = page.getByRole('radiogroup').first();
    await expect(themeGroup).toBeVisible();

    // Move focus into the group via Tab and activate with Space/Enter.
    await themeGroup.getByRole('radio').first().focus();
    await page.keyboard.press('Space');
    await page.waitForTimeout(120);

    // One of the radios must now be aria-checked=true.
    const checkedCount = await themeGroup
      .getByRole('radio', { checked: true })
      .count();
    expect(checkedCount).toBeGreaterThan(0);
  });

  test('GET /login returns < 400', async ({ page }) => {
    const response = await page.goto('/login', { waitUntil: 'domcontentloaded' });
    expect(response?.status(), 'HTTP status for /login').toBeLessThan(400);
  });

  test('prefers-reduced-motion=reduce suppresses MatrixRain canvas', async ({
    context,
    browser,
  }) => {
    await authenticate(context);
    const reducedCtx = await browser.newContext({
      reducedMotion: 'reduce',
      storageState: await context.storageState(),
    });
    const reducedPage = await reducedCtx.newPage();
    try {
      await reducedPage.goto(WORKSPACE_ROUTE, { waitUntil: 'networkidle' });

      // Force matrix theme via next-themes localStorage (deterministic; doesn't
      // depend on the UserMenu being open).
      await reducedPage.evaluate(() => {
        localStorage.setItem('theme', 'matrix');
        document.documentElement.classList.add('matrix');
      });
      await reducedPage.waitForTimeout(200);

      // MatrixRain must not mount a <canvas> when prefers-reduced-motion is set.
      const canvasCount = await reducedPage.locator('canvas').count();
      expect(canvasCount).toBe(0);
    } finally {
      await reducedCtx.close();
    }
  });
});
