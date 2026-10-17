import { test, expect, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';

/**
 * Bloque 2: página Indicadores en un destino AISLADO con estudio sintético, modelo activo y alumnos de demo.
 * Variables: DEMO_BASE, DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD. No se ejecuta contra la instalación activa.
 */
const base = process.env.DEMO_BASE;
const email = process.env.DEMO_ADMIN_EMAIL;
const password = process.env.DEMO_ADMIN_PASSWORD;
test.skip(!base || !email || !password, 'Requiere destino aislado y variables DEMO_*');
test.use({ baseURL: base });

async function shot(page: Page, label: string) {
  for (const [w, h] of [[1440, 900], [768, 1024], [390, 844]]) {
    await page.setViewportSize({ width: w, height: h });
    await page.screenshot({ path: `tests/evidence/mejoras-02-e2e-${label}-${w}x${h}.png`, fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}

test('B2: Indicadores muestra tarjetas con numerador/denominador, tabla por sección y CSV sin nombres', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(email!);
  await page.getByLabel('Contraseña', { exact: true }).fill(password!);
  await page.getByRole('button', { name: 'Iniciar sesión', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Cerrar sesión', exact: true })).toBeVisible();
  await page.getByRole('link', { name: /Indicadores/ }).click();
  await expect(page.getByRole('heading', { name: 'Indicadores', exact: true })).toBeVisible();
  for (const name of [/PRV/, /CRA/, /PDER/, /NIA/, /Intervención oportuna/]) await expect(page.getByLabel(name).first()).toBeVisible();
  await expect(page.getByText('Simulación').first()).toBeVisible();
  await expect(page.getByRole('table', { name: /Indicadores por sección/ })).toBeVisible();
  await expect(page.getByText(/de \d+ recibidos/)).toBeVisible();
  await shot(page, 'indicadores');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Descargar CSV', exact: true }).click();
  const file = await download;
  const content = await readFile((await file.path())!, 'utf-8');
  expect(content).toContain('codigo_anonimo');
  expect(content).not.toMatch(/Alumno ficticio/);
});
