import { test, expect, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';

/**
 * Bloque 1: medición manual → evaluación → alerta → intervención → reporte (SYNTHETIC).
 * Requiere un destino AISLADO ya preparado: estudio sintético importado y modelo activo.
 * Variables: DEMO_BASE (URL), DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, DEMO_PERIOD_CODE.
 * No se ejecuta contra la instalación activa.
 */
const base = process.env.DEMO_BASE;
const email = process.env.DEMO_ADMIN_EMAIL;
const password = process.env.DEMO_ADMIN_PASSWORD;
const periodCode = process.env.DEMO_PERIOD_CODE;
test.skip(!base || !email || !password || !periodCode, 'Requiere destino aislado y variables DEMO_*');
test.use({ baseURL: base });

async function login(page: Page) {
  await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(email!);
  await page.getByLabel('Contraseña', { exact: true }).fill(password!);
  await page.getByRole('button', { name: 'Iniciar sesión', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Cerrar sesión', exact: true })).toBeVisible();
}

async function shot(page: Page, label: string) {
  for (const [w, h] of [[1440, 900], [768, 1024], [390, 844]]) {
    await page.setViewportSize({ width: w, height: h });
    await page.screenshot({ path: `tests/evidence/mejoras-01-e2e-${label}-${w}x${h}.png`, fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}

async function selectPeriod(page: Page) {
  const option = page.locator('#period option', { hasText: periodCode! });
  await page.locator('#period').selectOption({ value: (await option.getAttribute('value'))! });
}

async function register(page: Page, code: string, values: Record<string, string>) {
  await page.goto('/estudiantes');
  await selectPeriod(page);
  await page.getByRole('button', { name: 'Nuevo estudiante', exact: true }).click();
  await page.getByLabel('Código del estudiante', { exact: true }).fill(code);
  await page.getByLabel('Nombre completo', { exact: true }).fill('Alumno ficticio ' + code);
  const section = page.getByLabel('Grado / sección', { exact: true });
  await section.selectOption({ index: 1 });
  await page.getByRole('button', { name: 'Guardar estudiante y matrícula' }).click();
  await expect(page.getByRole('heading', { name: 'Alumno ficticio ' + code, exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Nueva medición', exact: true }).click();
  await page.getByLabel('Fecha y hora de corte · Lima', { exact: true }).fill('2025-04-15T18:00');
  await page.getByLabel('Todo lo informado estaba disponible desde · Lima', { exact: true }).fill('2025-04-15T17:00');
  await page.getByLabel('Inicio de la ventana observada').fill('2025-03-16');
  for (const [label, value] of Object.entries(values)) await page.getByLabel(label, { exact: true }).fill(value);
  await page.getByRole('button', { name: 'Guardar medición', exact: true }).click();
  await expect(page.getByText(/Medición guardada en el servidor/)).toBeVisible();
}

const HIGH = { 'Promedio · 0–20': '7', 'Asistencia · 0–100 %': '50', 'Entrega de actividades · 0–100 %': '40', 'Participación · 1–3 en la simulación': '1', 'Incidencias · entero ≥ 0': '8' };
const LOW = { 'Promedio · 0–20': '18', 'Asistencia · 0–100 %': '98', 'Entrega de actividades · 0–100 %': '95', 'Participación · 1–3 en la simulación': '3', 'Incidencias · entero ≥ 0': '0' };

test('B1: crear alumno, medir, evaluar, abrir alerta, planificar actividad y ver reporte', async ({ page }) => {
  const high = 'D' + randomUUID().slice(0, 6).toUpperCase() + 'A';
  const low = 'D' + randomUUID().slice(0, 6).toUpperCase() + 'B';
  await login(page);
  await register(page, high, HIGH);
  await page.getByRole('button', { name: 'Evaluar riesgo de este estudiante', exact: true }).click();
  await expect(page.getByText('Evaluación registrada.', { exact: true })).toBeVisible();
  await shot(page, 'evaluacion-alto');
  const caseLink = page.getByRole('link', { name: /Abrir el caso de seguimiento/ });
  await expect(caseLink).toBeVisible();
  await caseLink.click();
  await expect(page.getByRole('button', { name: 'Planificar actividad', exact: true })).toBeVisible();
  await page.getByLabel('Objetivo', { exact: true }).fill('Demostración: tutoría de refuerzo simulada');
  await page.getByLabel('Fecha y hora programadas (Lima)').fill('2025-05-05T14:00');
  await page.getByRole('button', { name: 'Planificar actividad', exact: true }).click();
  await expect(page.getByText('Demostración: tutoría de refuerzo simulada')).toBeVisible();
  await shot(page, 'caso-actividad');

  await register(page, low, LOW);
  await page.getByRole('button', { name: 'Evaluar riesgo de este estudiante', exact: true }).click();
  await expect(page.getByText('Evaluación registrada.', { exact: true })).toBeVisible();
  await expect(page.getByText('Riesgo bajo: no se abre un caso.')).toBeVisible();

  await page.goto('/reportes');
  await selectPeriod(page);
  await expect(page.getByRole('link', { name: high, exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: low, exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: `Ver caso activo de ${high}` })).toBeVisible();
  await shot(page, 'reportes');
});
