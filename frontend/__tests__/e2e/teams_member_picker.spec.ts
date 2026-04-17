import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const token = readFileSync('/tmp/dev_token.env', 'utf8').trim().replace(/^TOKEN=/, '');

test('Add-member dialog shows workspace users, not a UUID input', async ({ context, page }) => {
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

  await page.goto('/workspace/tuio/teams', { waitUntil: 'networkidle' });
  await page.waitForSelector('text=miembro', { timeout: 5000 }).catch(() => {});

  // Expand a team card by clicking its name (aria-label is the team name).
  const teamCard = page.getByRole('button', { name: 'Equipo de Producto' });
  await teamCard.click();

  // Click "Añadir miembro" that expanded inside this team.
  await page.getByRole('button', { name: /añadir miembro/i }).first().click();

  // The dialog should contain a Select trigger, not a UUID input field.
  await expect(page.getByRole('combobox', { name: /usuario/i })).toBeVisible();
  await expect(page.getByPlaceholder(/uuid/i)).toHaveCount(0);
});
