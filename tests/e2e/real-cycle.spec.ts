import { test, expect, type Page } from '@playwright/test';

/**
 * Bloque 3B-2: ciclo REAL local con datos FICTICIOS en un destino AISLADO ya preparado
 * (protocolo confirmado, estudio institucional importado, cierres cargados, modelo REAL activo y dos corridas retrospectivas).
 * Variables: DEMO_BASE, DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, DEMO_PERIOD_CODE. Nunca contra la instalación activa.
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
    await page.screenshot({ path: `tests/evidence/mejoras-03b3-e2e-${label}-${w}x${h}.png`, fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}

async function selectPeriod(page: Page) {
  const option = page.locator('#period option', { hasText: periodCode! });
  await page.locator('#period').selectOption({ value: (await option.getAttribute('value'))! });
}

test('ciclo REAL: protocolo, modelos, alertas, reportes e indicadores con rótulos de origen', async ({ page }) => {
  test.setTimeout(240000);
  await login(page);

  // Protocolo REAL: estado confirmado.
  await page.goto('/protocolo');
  await expect(page.getByRole('heading', { name: 'Protocolo de datos reales' })).toBeVisible();
  await expect(page.getByText('● Confirmado: procesamiento habilitado')).toBeVisible();
  await shot(page, 'protocolo-confirmado');

  // Modelos: modelo REAL activo, exploratorio, con aviso de n pequeño.
  await page.goto('/modelos');
  await expect(page.getByText('Exploratorio local (sin validación externa)')).toBeVisible();
  await expect(page.getByText('⚠ n pequeño: ver detalle')).toBeVisible();
  await shot(page, 'modelos');
  await page.getByRole('link', { name: /Estudio institucional/ }).first().click();
  await expect(page.getByText('Análisis exploratorio local')).toBeVisible();
  await expect(page.getByText(/n = 60 estudiantes/)).toBeVisible();
  await shot(page, 'modelo-detalle');

  // Alertas: etiqueta REAL y simulación retrospectiva.
  await page.goto('/alertas');
  await selectPeriod(page);
  await expect(page.getByText('Datos reales locales — análisis exploratorio, no demuestra eficacia escolar.').first()).toBeVisible();
  await expect(page.getByText('simulación retrospectiva').first()).toBeVisible();
  await shot(page, 'alertas');

  // Reportes: etiqueta REAL.
  await page.goto('/reportes');
  await selectPeriod(page);
  await expect(page.getByText('Datos reales locales — análisis exploratorio, no demuestra eficacia escolar.').first()).toBeVisible();
  await shot(page, 'reportes');

  // Indicadores por bimestre: NIA y oportuna nulos con motivo; PDER calculado.
  await page.goto('/indicadores');
  const indicatorOption = page.locator('#ind-period option', { hasText: periodCode! });
  await page.locator('#ind-period').selectOption({ value: (await indicatorOption.getAttribute('value'))! });
  await page.locator('#ind-bimester').selectOption('B1');
  await expect(page.getByText('Datos reales locales — análisis exploratorio, no demuestra eficacia escolar', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('Todavía no hay intervenciones reales registradas').first()).toBeVisible();
  await expect(page.getByText(/alertas son simulación retrospectiva/)).toBeVisible();
  await expect(page.getByText('Exploratorio local').first()).toBeVisible();
  await expect(page.getByText('validación cruzada (fuera de muestra)').first()).toBeVisible();
  await expect(page.getByText(/Media de 20 repeticiones/)).toBeVisible();
  await shot(page, 'indicadores-B1');
  await page.locator('#ind-bimester').selectOption('B2');
  await expect(page.getByText('Bimestre: B2')).toBeVisible();
  await shot(page, 'indicadores-B2');

  // Revocar: todo REAL se bloquea de inmediato; confirmar restablece.
  await page.goto('/protocolo');
  await page.getByRole('button', { name: 'Revocar protocolo' }).click();
  await page.getByRole('button', { name: 'Sí, revocar' }).click();
  await expect(page.getByText('○ Sin confirmar: procesamiento bloqueado')).toBeVisible();
  await shot(page, 'protocolo-revocado');
  await page.goto('/alertas');
  await selectPeriod(page);
  await expect(page.getByText('Seguimiento institucional bloqueado')).toBeVisible();
  await shot(page, 'alertas-bloqueadas');
  await page.goto('/protocolo');
  await page.getByRole('button', { name: 'Confirmar protocolo' }).click();
  await page.getByRole('button', { name: 'Sí, confirmar' }).click();
  await expect(page.getByText('● Confirmado: procesamiento habilitado')).toBeVisible();
});

test('persistencia tras reiniciar: el estado REAL se conserva', async ({ page }) => {
  await login(page);
  await page.goto('/indicadores');
  const option = page.locator('#ind-period option', { hasText: periodCode! });
  await page.locator('#ind-period').selectOption({ value: (await option.getAttribute('value'))! });
  await page.locator('#ind-bimester').selectOption('B1');
  await expect(page.getByText(/alertas son simulación retrospectiva/)).toBeVisible();
  await shot(page, 'persistencia');
});
