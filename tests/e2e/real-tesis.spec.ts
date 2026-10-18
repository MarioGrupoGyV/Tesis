import { test, expect, type Page } from '@playwright/test';

/**
 * Bloque 5: capturas del destino aislado `real-tesis` (datos reales locales). Solo vistas agregadas: Alertas, Indicadores (B1 y B2) y Modelos.
 * No abre ninguna ficha de alumno y enmascara los códigos de la lista de alertas antes de capturar. Variables: REAL_BASE, REAL_EMAIL,
 * REAL_PASSWORD (las inyecta un lanzador desde el perfil Windows), REAL_PERIOD_CODE. Opcionales: EVIDENCE_PREFIX (por defecto mejoras-05) y
 * REAL_ONLY=indicadores (Bloque 5.1: solo las capturas de Indicadores, con la detección validada).
 */
const base = process.env.REAL_BASE;
const email = process.env.REAL_EMAIL;
const password = process.env.REAL_PASSWORD;
const periodCode = process.env.REAL_PERIOD_CODE;
const prefix = process.env.EVIDENCE_PREFIX ?? 'mejoras-05';
const onlyIndicators = process.env.REAL_ONLY === 'indicadores';
test.skip(!base || !email || !password || !periodCode, 'Requiere el destino real-tesis y variables REAL_*');
test.use({ baseURL: base });

async function login(page: Page) {
  await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(email!);
  await page.getByLabel('Contraseña', { exact: true }).fill(password!);
  await page.getByRole('button', { name: 'Iniciar sesión', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Cerrar sesión', exact: true })).toBeVisible();
}

async function shot(page: Page, label: string, mask?: () => Promise<void>) {
  for (const [w, h] of [[1440, 900], [768, 1024], [390, 844]]) {
    await page.setViewportSize({ width: w, height: h });
    if (mask) await mask();      // el cambio de tamaño vuelve a dibujar la tabla: se enmascara de nuevo antes de cada captura
    await page.screenshot({ path: `tests/evidence/${prefix}-real-${label}-${w}x${h}.png`, fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}

async function selectPeriod(page: Page, selector = '#period') {
  const option = page.locator(`${selector} option`, { hasText: periodCode! });
  await page.locator(selector).selectOption({ value: (await option.getAttribute('value'))! });
}

test('vistas agregadas de real-tesis sin códigos ni nombres', async ({ page }) => {
  test.setTimeout(240000);
  await login(page);

  if (!onlyIndicators) {
    await page.goto('/modelos');
    await expect(page.getByText('Exploratorio local (sin validación externa)')).toBeVisible();
    await expect(page.getByText('Consultando el alcance del sistema')).toHaveCount(0);
    await shot(page, 'modelos');

    await page.goto('/alertas');
    await selectPeriod(page);
    await expect(page.getByText('simulación retrospectiva').first()).toBeVisible();
    const maskCodes = async () => { await page.locator('a.followup-link').first().waitFor(); await page.evaluate(() => document.querySelectorAll('a.followup-link').forEach(item => { item.textContent = '•••'; })); };
    await shot(page, 'alertas', maskCodes);
    await page.setViewportSize({ width: 1440, height: 900 });
  }

  await page.goto('/indicadores');
  await selectPeriod(page, '#ind-period');
  for (const bimester of ['B1', 'B2']) {
    await page.locator('#ind-bimester').selectOption(bimester);
    await expect(page.getByText(`Bimestre: ${bimester}`)).toBeVisible();
    await expect(page.getByText('validación cruzada (fuera de muestra)').first()).toBeVisible();
    // Bloque 5.1: la detección validada y el PDER rotulado «en muestra» aparecen en la pantalla; se verifica antes de capturar.
    await expect(page.getByRole('heading', { name: 'Detección validada (fuera de muestra)' })).toBeVisible();
    await expect(page.getByLabel('Detección validada', { exact: true })).toContainText('±');
    await expect(page.getByText('En muestra · dato de funcionamiento')).toBeVisible();
    await expect(page.getByText('Con n pequeño').first()).toBeVisible();
    await shot(page, `indicadores-${bimester}`);
  }
});
