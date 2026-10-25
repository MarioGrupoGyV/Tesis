import { test, expect, type Page, type Locator } from '@playwright/test';
import { writeFileSync } from 'node:fs';

/**
 * Bloque 9: revisión de pantallas en una instalación (principal o demo-vivo). En cada pantalla: sin «participación» visible, nombres nuevos donde
 * corresponde y captura 1440 × 900. Variables: SCREENS_BASE, SCREENS_ADMIN_EMAIL, SCREENS_ADMIN_PASSWORD, SCREENS_PERIOD_CODE, SCREENS_PREFIX.
 * SCREENS_MASK=1 (instalación principal, datos reales): tapa en las capturas títulos, tablas y datos de contexto que muestran códigos de estudiantes.
 * Solo consulta: abre el formulario de medición y lo cancela sin guardar.
 */
const base = process.env.SCREENS_BASE;
const email = process.env.SCREENS_ADMIN_EMAIL;
const password = process.env.SCREENS_ADMIN_PASSWORD;
const periodCode = process.env.SCREENS_PERIOD_CODE;
const prefix = process.env.SCREENS_PREFIX ?? 'mejoras-09-pantallas';
const masked = process.env.SCREENS_MASK === '1';
test.skip(!base || !email || !password || !periodCode, 'Requiere SCREENS_*');
test.use({ baseURL: base, viewport: { width: 1440, height: 900 } });

const results: { pantalla: string; participacion_visible: boolean; nombre_antiguo_corte_visible: boolean; nombres_nuevos: string[] }[] = [];

async function settled(page: Page) {
  await expect(page.locator('.spinner')).toHaveCount(0, { timeout: 30000 });
  await expect(page.locator('#main-content h1').first()).toBeVisible();
}

function masks(page: Page): Locator[] {
  return masked ? [page.locator('#main-content h1'), page.locator('.page-header p.muted'), page.locator('table tbody'),
    page.locator('#student-context-title + dl'), page.locator('.followup-fields'), page.locator('select#period')] : [];
}

async function review(page: Page, name: string, expected: string[] = []) {
  await settled(page);
  const text = await page.locator('body').innerText();
  const seen = expected.filter(label => text.includes(label));
  const oldNames = /cortes?|corte intermedio/i.test(text);
  results.push({ pantalla: name, participacion_visible: /particip/i.test(text), nombre_antiguo_corte_visible: oldNames, nombres_nuevos: seen });
  expect(text, `participación en ${name}`).not.toMatch(/particip/i);
  expect(oldNames, `«corte» en ${name}`).toBe(false);
  expect(seen, `nombres nuevos en ${name}`).toEqual(expected);
  await page.screenshot({ path: `tests/evidence/${prefix}-${name}-1440x900.png`, fullPage: false, mask: masks(page) });
}

async function selectPeriod(page: Page) {
  const option = page.locator('#period option', { hasText: periodCode! });
  if (await option.count()) await page.locator('#period').selectOption({ value: (await option.first().getAttribute('value'))! });
}

test('pantallas sin participación y con los nombres nuevos', async ({ page }) => {
  test.setTimeout(300000);
  await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(email!);
  await page.getByLabel('Contraseña', { exact: true }).fill(password!);
  await page.getByRole('button', { name: 'Iniciar sesión', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Cerrar sesión', exact: true })).toBeVisible();
  await selectPeriod(page);
  await review(page, 'inicio');

  await page.goto('/estudiantes'); await selectPeriod(page);
  await review(page, 'estudiantes', ['Última revisión de mitad de bimestre']);
  const first = page.locator('table tbody a').first();
  await first.click();
  await review(page, 'ficha', ['Última revisión de mitad de bimestre', 'Notas obtenidas hasta la fecha', 'Asistencia hasta la fecha (%)',
    'Tareas entregadas hasta la fecha (%)', 'Incidencias hasta la fecha']);
  const newMeasurement = page.getByRole('button', { name: 'Nueva medición', exact: true });
  if (await newMeasurement.isVisible()) {
    await newMeasurement.click();
    await review(page, 'formulario-medicion', ['Fecha y hora de la revisión de mitad de bimestre · Lima', 'Notas obtenidas hasta la fecha · promedio 0–20',
      'Asistencia hasta la fecha (%)', 'Tareas entregadas hasta la fecha (%)', 'Incidencias hasta la fecha · entero ≥ 0']);
    await page.getByRole('button', { name: 'Cancelar', exact: true }).click();               // no se guarda nada
  }

  await page.goto('/alertas'); await selectPeriod(page);
  await review(page, 'alertas');
  const alertLink = page.locator('table tbody a').first();
  if (await alertLink.count()) { await alertLink.click(); await review(page, 'alerta-detalle', ['Revisión de mitad de bimestre que motivó el caso']); }

  await page.goto('/indicadores'); await review(page, 'indicadores');
  await page.goto('/reportes'); await selectPeriod(page); await review(page, 'reportes', ['Última revisión de mitad de bimestre']);
  await page.goto('/datos'); await review(page, 'datos');
  await page.goto('/protocolo'); await review(page, 'protocolo');
  await page.goto('/modelos'); await review(page, 'modelos');
  const modelLink = page.locator('table tbody a').first();
  if (await modelLink.count()) { await modelLink.click(); await review(page, 'modelo-detalle'); }
  writeFileSync(`tests/evidence/${prefix}-revision.json`, JSON.stringify({ periodo: periodCode, enmascarado: masked, pantallas: results }, null, 2) + '\n');
});
