import { test, expect, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';

/**
 * Demostración en vivo (Bloque 1, actualizada en el Bloque 6): medición manual → evaluación → alerta → intervención → reporte en el periodo
 * SYNTHETIC rotulado «Demostración en vivo» (DEMO-VIVO) de una instalación hermana que ADEMÁS tiene la corrida real (REAL-2026).
 * Requiere un destino AISLADO ya preparado (`prepare_demo_period.py`): estudio sintético importado y modelo activo.
 * Variables: DEMO_BASE (URL), DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, DEMO_PERIOD_CODE. Opcionales: DEMO_REAL_PERIOD_CODE (por ejemplo REAL-2026: comprueba
 * que sus números no cambian por lo registrado en la demostración) y DEMO_SHOT_PREFIX (por defecto mejoras-01-e2e). No se ejecuta contra la activa.
 * Las capturas solo muestran el periodo de demostración (registros inventados); REAL-2026 solo se consulta por API, sin abrir listas ni fichas.
 */
const base = process.env.DEMO_BASE;
const email = process.env.DEMO_ADMIN_EMAIL;
const password = process.env.DEMO_ADMIN_PASSWORD;
const periodCode = process.env.DEMO_PERIOD_CODE;
const realCode = process.env.DEMO_REAL_PERIOD_CODE;
const prefix = process.env.DEMO_SHOT_PREFIX ?? 'mejoras-01-e2e';
const DEMO_LABEL = 'Registro de demostración, no es dato del colegio';
test.skip(!base || !email || !password || !periodCode, 'Requiere destino aislado y variables DEMO_*');
test.use({ baseURL: base });

const laps: { step: string; seconds: number }[] = [];
let lapStart = Date.now();
function lap(step: string) {
  const now = Date.now();
  laps.push({ step, seconds: Math.round((now - lapStart) / 100) / 10 });
  lapStart = now;
}

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
    await page.screenshot({ path: `tests/evidence/${prefix}-${label}-${w}x${h}.png`, fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}

async function selectPeriod(page: Page) {
  const option = page.locator('#period option', { hasText: periodCode! });
  await page.locator('#period').selectOption({ value: (await option.getAttribute('value'))! });
  await expect(page.getByText(DEMO_LABEL).first()).toBeVisible();                       // el rótulo del periodo de demostración está siempre a la vista
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
  lap('registrar estudiante ' + (code.endsWith('A') ? '1 (riesgo alto)' : '2 (riesgo bajo)'));
  await page.getByRole('button', { name: 'Nueva medición', exact: true }).click();
  await page.getByLabel('Fecha y hora de corte · Lima', { exact: true }).fill('2025-04-15T18:00');
  await page.getByLabel('Todo lo informado estaba disponible desde · Lima', { exact: true }).fill('2025-04-15T17:00');
  await page.getByLabel('Inicio de la ventana observada').fill('2025-03-16');
  for (const [label, value] of Object.entries(values)) await page.getByLabel(label, { exact: true }).fill(value);
  await page.getByRole('button', { name: 'Guardar medición', exact: true }).click();
  await expect(page.getByText(/Medición guardada en el servidor/)).toBeVisible();
  lap('registrar medición ' + (code.endsWith('A') ? '1' : '2'));
}

/** Números de REAL-2026 por API (solo agregados, sin códigos ni nombres): deben ser idénticos antes y después de la demostración. */
async function realNumbers(page: Page) {
  const periods = await (await page.request.get('/api/v1/periods')).json();
  const real = periods.find((item: { code: string }) => item.code === realCode);
  expect(real, 'el periodo real existe').toBeTruthy();
  const out: Record<string, unknown> = { students: (await (await page.request.get(`/api/v1/students?period_id=${real.id}&page_size=1`)).json()).total };
  for (const bimester of ['B1', 'B2']) {
    const response = await page.request.get(`/api/v1/indicators?period_id=${real.id}&bimester=${bimester}`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    const total = data.total;
    out[bimester] = { eligible: total.eligible_students, pder: total.pder, cra: total.cra, nia: total.nia, opportune: total.opportune, metrics: total.model_metrics,
                      detection: total.validated_detection, alerts: data.retrospective_alerts };
  }
  return out;
}

const HIGH = { 'Promedio · 0–20': '7', 'Asistencia · 0–100 %': '50', 'Entrega de actividades · 0–100 %': '40', 'Participación · 1–3 en la simulación': '1', 'Incidencias · entero ≥ 0': '8' };
const LOW = { 'Promedio · 0–20': '18', 'Asistencia · 0–100 %': '98', 'Entrega de actividades · 0–100 %': '95', 'Participación · 1–3 en la simulación': '3', 'Incidencias · entero ≥ 0': '0' };

test('B1: crear alumno, medir, evaluar, abrir alerta, planificar actividad y ver reporte', async ({ page }) => {
  test.setTimeout(300000);
  const high = 'D' + randomUUID().slice(0, 6).toUpperCase() + 'A';
  const low = 'D' + randomUUID().slice(0, 6).toUpperCase() + 'B';
  await login(page);
  lap('iniciar sesión');
  const before = realCode ? await realNumbers(page) : null;
  lapStart = Date.now();                                                                 // la comprobación de REAL-2026 no es parte del recorrido cronometrado

  await page.goto('/estudiantes');
  await selectPeriod(page);
  await expect(page.getByRole('button', { name: 'Nuevo estudiante', exact: true })).toBeVisible();
  await shot(page, 'periodo-demostracion');
  lapStart = Date.now();

  await register(page, high, HIGH);
  await page.getByRole('button', { name: 'Evaluar riesgo de este estudiante', exact: true }).click();
  await expect(page.getByText('Evaluación registrada.', { exact: true })).toBeVisible();
  await expect(page.getByText(/Modelo que hizo la evaluación:/)).toBeVisible();          // la evaluación dice qué modelo la hizo
  lap('evaluar riesgo (estudiante 1)');
  await shot(page, 'evaluacion-alto');
  const caseLink = page.getByRole('link', { name: /Abrir el caso de seguimiento/ });
  await expect(caseLink).toBeVisible();
  await caseLink.click();
  await expect(page.getByRole('button', { name: 'Planificar actividad', exact: true })).toBeVisible();
  await expect(page.getByText(DEMO_LABEL).first()).toBeVisible();
  await page.getByLabel('Objetivo', { exact: true }).fill('Demostración: tutoría de refuerzo simulada');
  await page.getByLabel('Fecha y hora programadas (Lima)').fill('2025-05-05T14:00');
  await page.getByRole('button', { name: 'Planificar actividad', exact: true }).click();
  await expect(page.getByText('Demostración: tutoría de refuerzo simulada')).toBeVisible();
  lap('abrir el caso y planificar la actividad');
  await shot(page, 'caso-actividad');

  await register(page, low, LOW);
  await page.getByRole('button', { name: 'Evaluar riesgo de este estudiante', exact: true }).click();
  await expect(page.getByText('Evaluación registrada.', { exact: true })).toBeVisible();
  await expect(page.getByText('Riesgo bajo: no se abre un caso.')).toBeVisible();
  lap('evaluar riesgo (estudiante 2, bajo)');

  await page.goto('/reportes');
  await selectPeriod(page);
  await expect(page.getByRole('link', { name: high, exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: low, exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: `Ver caso activo de ${high}` })).toBeVisible();
  lap('abrir el reporte');
  await shot(page, 'reportes');

  if (before) {
    lapStart = Date.now();
    const after = await realNumbers(page);
    expect(after).toEqual(before);                                                      // lo registrado en la demostración no altera REAL-2026
    expect((after.B1 as { nia: { reason: string } }).nia.reason).toBe('NO_REAL_INTERVENTIONS');
    expect((after.B2 as { opportune: { reason: string } }).opportune.reason).toBe('NO_REAL_INTERVENTIONS');
  }
  const total = Math.round(laps.filter(item => item.step !== 'iniciar sesión').reduce((sum, item) => sum + item.seconds, 0) * 10) / 10;
  test.info().annotations.push({ type: 'tiempos-segundos', description: JSON.stringify({ pasos: laps, total_recorrido: total, real_2026_sin_cambios: Boolean(before) }) });
  console.log('TIEMPOS ' + JSON.stringify({ pasos: laps, total_recorrido: total }));
});
