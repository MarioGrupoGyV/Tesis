import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const accounts = JSON.parse(process.env.E2E_ACCOUNTS ?? '{}') as Record<string, { email: string; password: string }>;
if (!accounts.ADMIN?.email || !accounts.ADMIN?.password) throw new Error('Usar runner con credenciales privadas');

test('ADMIN: entrada parcial, SVM congelado, 60 propuestas/predicciones, historial y CSV', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(accounts.ADMIN.email);
  await page.getByLabel('Contraseña', { exact: true }).fill(accounts.ADMIN.password);
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await expect(page.locator('.user-summary').getByText('Administrador', { exact: true })).toBeVisible();
  await page.goto('/modelos');
  const panel = page.locator('.retrospective-panel');
  await expect(panel.getByRole('heading', { name: 'Evaluación retrospectiva B1 → B2' })).toBeVisible();
  const start = await (await page.request.get('/api/v1/retrospective/evaluations')).json();
  await panel.getByRole('button', { name: 'Ejecutar evaluación retrospectiva' }).click();
  await expect(panel.getByText('49 aciertos de 60; exactitud 81.67 %; F1 macro 0.793048.')).toBeVisible();
  await expect(panel.getByText('40 propuestas de alerta · 0 notificaciones enviadas · 0 intervenciones realizadas por esta ejecución.')).toBeVisible();
  const next = await (await page.request.get('/api/v1/retrospective/evaluations')).json();
  expect(next.total).toBe(start.total + 1);
  const id = next.items[0].id;
  const stored = await (await page.request.get(`/api/v1/retrospective/evaluations/${id}`)).json();
  expect(stored.predictions).toHaveLength(60);
  expect(stored.predictions.filter((r: { alert_proposed: boolean }) => r.alert_proposed)).toHaveLength(40);
  expect(stored.source_events_verified).toBe(true);
  expect(stored.b1_support_vectors_verified).toBe(true);
  expect(stored.compatibility).toBe('COMPATIBLE_REFERENCE_RUNTIME');
  expect(stored.versions).toEqual({ python: '3.12.14', scikit_learn: '1.8.0', numpy: '2.3.5', scipy: '1.17.0', joblib: '1.5.3', threadpoolctl: '3.6.0' });
  expect(stored.version_warnings).toEqual([]);
  await expect(panel.getByText(/Compatibilidad: entorno de referencia compatible y aislado/)).toBeVisible();
  const result = panel.locator('[aria-label="Resultado retrospectivo"]');
  for (const [width, height] of [[1440,900],[768,1024],[390,844]]) {
    await page.setViewportSize({ width, height });
    await result.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `tests/evidence/${process.env.RETROSPECTIVE_EVIDENCE_PREFIX ?? 'retro'}-result-${width}x${height}.png` });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}x${height}`).toBe(true);
  }
  const downloadPromise = page.waitForEvent('download');
  await panel.getByRole('button', { name: 'Descargar reporte retrospectivo CSV' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('evaluacion-retrospectiva-B2.csv');
  const path = await download.path();
  expect(path).not.toBeNull();
  const csv = readFileSync(path!, 'utf8');
  expect(csv.charCodeAt(0)).toBe(0xfeff);
  expect(csv.trim().split('\n')).toHaveLength(61);
  expect(csv).not.toContain('codigo_estudiante');
  await download.delete();
  await panel.getByLabel('Promedio parcial (0 a 20)').fill('10');
  await panel.getByLabel('Asistencia parcial (0 a 1)').fill('0.7');
  await panel.getByLabel('Entrega parcial (0 a 1)').fill('0.5');
  await panel.getByLabel('Disponibilidad de los tres valores').fill('2026-06-30');
  await panel.getByRole('button', { name: 'Comprobar entrada parcial', exact: true }).click();
  await expect(panel.getByText(/Propuesta de alerta\. 0 notificaciones enviadas; 0 intervenciones realizadas/)).toBeVisible();
  expect((await (await page.request.get('/api/v1/retrospective/evaluations')).json()).total).toBe(next.total);
  await page.reload();
  await expect(panel.getByRole('heading', { name: 'Evaluación retrospectiva B1 → B2' })).toBeVisible();
  expect((await (await page.request.get('/api/v1/retrospective/evaluations')).json()).items.some((r: { id: string }) => r.id === id)).toBe(true);
  // Historical incompatible executions remain visible with their original warnings.
  const old = next.items.find((r: { compatibility: string }) => r.compatibility === 'CROSS_VERSION_EXPERIMENTAL');
  if (old) {
    const response = await page.request.get(`/api/v1/retrospective/evaluations/${old.id}`);
    const historical = await response.json();
    expect(historical.version_warnings).toHaveLength(3);
    await panel.getByRole('region', { name: 'Historial retrospectivo' }).locator('tbody tr').nth(next.items.findIndex((r: { id: string }) => r.id === old.id)).getByRole('button').click();
    await expect(panel.getByText('Advertencias conservadas de esta ejecución')).toBeVisible();
    for (const warning of historical.version_warnings) await expect(panel.getByText(warning, { exact: true })).toBeVisible();
  }
});

for (const role of ['TUTOR','DIRECTOR','RESEARCHER']) {
  test(`${role}: módulo retrospectivo y reportes restringidos por servidor`, async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('Correo electrónico').fill(accounts[role].email);
    await page.getByLabel('Contraseña', { exact: true }).fill(accounts[role].password);
    await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
    await expect(page.locator('.user-summary')).toBeVisible();
    expect((await page.request.get('/api/v1/retrospective/evaluations')).status()).toBe(403);
    await page.goto('/modelos');
    await expect(page.locator('.retrospective-panel')).toHaveCount(0);
  });
}
