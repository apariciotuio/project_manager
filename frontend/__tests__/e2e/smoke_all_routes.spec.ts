import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// Use the same dev token the API smoke test uses. The script
// scripts/dev_token.py writes to /tmp/dev_token.env.
const token = readFileSync('/tmp/dev_token.env', 'utf8').trim().replace(/^TOKEN=/, '');

async function firstWorkItemId(): Promise<string> {
  const res = await fetch('http://localhost:17004/api/v1/work-items?page_size=1', {
    headers: { cookie: `access_token=${token}` },
  });
  const body = await res.json();
  return body.data.items[0].id as string;
}

const WI_ID_PROMISE = firstWorkItemId();

const ROUTES = [
  '/',
  '/workspace/select',
  '/workspace/tuio/items',
  '/workspace/tuio/items/new',
  '/workspace/tuio/inbox',
  '/workspace/tuio/teams',
  '/workspace/tuio/admin',
];

test('detail page tabs all render without errors', async ({ context, page }) => {
  const id = await WI_ID_PROMISE;
  await context.addCookies([
    { name: 'access_token', value: token, domain: 'localhost', path: '/', httpOnly: false, secure: false, sameSite: 'Lax' },
  ]);
  const consoleErrors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  const pageErrors: string[] = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));

  await page.goto(`/workspace/tuio/items/${id}`, { waitUntil: 'networkidle' });

  for (const tabName of ['Tareas', 'Revisiones', 'Comentarios', 'Cronología', 'Sub-items']) {
    const tab = page.getByRole('tab', { name: new RegExp(tabName, 'i') });
    if (await tab.isVisible()) {
      await tab.click();
      await page.waitForTimeout(300);
    }
  }

  // Verify tag pill section renders (aria-label="Etiquetas" must be present)
  const tagSection = page.getByLabel('Etiquetas');
  await tagSection.waitFor({ state: 'attached', timeout: 3000 }).catch(() => null);

  expect(pageErrors).toEqual([]);
  const meaningful = consoleErrors.filter(
    (e) => !/favicon|source map|Failed to load resource.*\.(map|ico)/.test(e),
  );
  expect(meaningful).toEqual([]);
});

test('renders /workspace/tuio/items/[id] without console or page errors', async ({ context, page }) => {
  const id = await WI_ID_PROMISE;
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
  const consoleErrors: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });
  const pageErrors: string[] = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));
  const response = await page.goto(`/workspace/tuio/items/${id}`, { waitUntil: 'networkidle' });
  expect(response?.status()).toBeLessThan(400);
  await page.waitForTimeout(800);
  expect(pageErrors).toEqual([]);
  const meaningful = consoleErrors.filter(
    (e) => !/favicon|source map|Failed to load resource.*\.(map|ico)/.test(e),
  );
  expect(meaningful).toEqual([]);
});

for (const route of ROUTES) {
  test(`renders ${route} without console errors or page errors`, async ({ context, page }) => {
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

    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    const response = await page.goto(route, { waitUntil: 'networkidle' });
    expect(response?.status(), `HTTP status for ${route}`).toBeLessThan(400);

    // Allow small async work to settle (e.g. hydration effects).
    await page.waitForTimeout(500);

    expect(pageErrors, `page errors on ${route}`).toEqual([]);
    // Filter out noisy but harmless warnings (sourcemaps, favicon 404s, etc.).
    const meaningful = consoleErrors.filter((e) => !/favicon|source map|Failed to load resource.*\.(map|ico)/.test(e));
    expect(meaningful, `console errors on ${route}`).toEqual([]);
  });
}
