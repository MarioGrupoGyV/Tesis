import { test, expect, type Page } from '@playwright/test';

/**
 * Bloque 10 (ADR 015): sección «Estudio real» de solo lectura y avisos retirados. Solo consulta: no guarda nada.
 * Variables: REALSET_BASE, REALSET_ADMIN_EMAIL, REALSET_ADMIN_PASSWORD, REALSET_PERIOD_CODE (REAL-2026), REALSET_STUDENTS (60),
 * REALSET_LOCKED (1 si el conjunto debe estar cerrado), REALSET_PREFIX. Las capturas tapan la tabla y los códigos (datos reales).
 */
const base = process.env.REALSET_BASE;
const email = process.env.REALSET_ADMIN_EMAIL;
const password = process.env.REALSET_ADMIN_PASSWORD;
const periodCode = process.env.REALSET_PERIOD_CODE;
const students = process.env.REALSET_STUDENTS ?? '60';
const locked = process.env.REALSET_LOCKED === '1';
const prefix = process.env.REALSET_PREFIX ?? 'mejoras-10';
test.skip(!base || !email || !password || !periodCode, 'Requiere REALSET_*');
test.use({ baseURL: base });

const REMOVED = /no demuestra eficacia escolar|se rotulan como simulación retrospectiva|Concluir un caso registra una decisión humana|Calculado al:|Fin del bimestre considerado|alertas son simulación retrospectiva|El riesgo es una estimación del modelo/;

async function settled(page: Page) {
  await expect(page.locator('.spinner')).toHaveCount(0, { timeout: 30000 });
  await expect(page.locator('#main-content h1').first()).toBeVisible();
}

async function selectPeriod(page: Page) {
  // La aplicación fija su periodo por defecto al cargar: se elige el periodo y se espera a que quede seleccionado.
  const select = page.locator('#period');
  await expect(select).toBeVisible();
  const value = (await select.locator('option', { hasText: periodCode! }).first().getAttribute('value'))!;
  await expect(async () => {
    if (await select.inputValue() !== value) await select.selectOption({ value });
    await page.waitForTimeout(500);
    expect(await select.inputValue()).toBe(value);
  }).toPass({ timeout: 20000 });
  await settled(page);
}

async function noRemovedText(page: Page, name: string) {
  await settled(page);
  await page.waitForTimeout(800);
  expect(await page.locator('body').innerText(), `aviso retirado visible en ${name}`).not.toMatch(REMOVED);
}

test('estudio real de solo lectura y avisos retirados', async ({ page }) => {
  test.setTimeout(240000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(email!);
  await page.getByLabel('Contraseña', { exact: true }).fill(password!);
  await page.getByRole('button', { name: 'Iniciar sesión', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Cerrar sesión', exact: true })).toBeVisible();
  await selectPeriod(page);

  await page.getByRole('link', { name: 'Estudio real' }).first().click();
  await settled(page);
  await expect(page.getByRole('heading', { name: 'Estudio real', level: 1 })).toBeVisible();
  await expect(page.getByText(`${students} de ${students} estudiantes`)).toBeVisible();
  await expect(page.locator('.realset-table tbody tr')).toHaveCount(Number(students));
  await expect(page.getByText(locked ? 'Conjunto cerrado.' : 'Conjunto abierto.')).toBeVisible();
  const mask = [page.locator('.realset-table tbody'), page.locator('.page-header p.muted'), page.locator('select#period')];
  await page.screenshot({ path: `tests/evidence/${prefix}-estudio-real-1440x900.png`, mask });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: `tests/evidence/${prefix}-estudio-real-390x844.png`, mask });
  await page.setViewportSize({ width: 1440, height: 900 });

  for (const [path, name] of [['/estudiantes', 'estudiantes'], ['/alertas', 'alertas'], ['/reportes', 'reportes']]) {
    await page.goto(path); await selectPeriod(page); await noRemovedText(page, name);
  }
  await expect(page.locator('#main-content')).not.toContainText('Concluir un caso');
  await page.goto('/estudiantes'); await selectPeriod(page);
  await expect(page.getByText('Este periodo es el conjunto real del estudio')).toBeVisible();
  if (locked) await expect(page.getByRole('button', { name: 'Nuevo estudiante' })).toBeDisabled();

  await page.goto('/indicadores');
  const option = page.locator('#ind-period option', { hasText: periodCode! });
  await page.locator('#ind-period').selectOption({ value: (await option.getAttribute('value'))! });
  await page.locator('#ind-bimester').selectOption('B1');
  await noRemovedText(page, 'indicadores');
});
