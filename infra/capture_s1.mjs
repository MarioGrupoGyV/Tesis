/** Real S1 screenshots only. Private credentials and tokens are never logged. */
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { chromium } from '@playwright/test';

const baseURL = process.env.S1_BASE_URL ?? 'http://localhost:15173';
const privateFile = resolve(process.env.DEMO_CREDENTIALS_FILE ?? '.local/secrets/demo-credentials.json');
const evidenceDir = resolve('tests/evidence');
let credentials;
try {
  credentials = JSON.parse(await readFile(privateFile, 'utf8'));
} catch {
  throw new Error('The private demo credentials file could not be read or parsed; private contents omitted');
}
const account = credentials.tutor;
assert(account?.email && account?.password, 'Private demo file must include the tutor account');
await mkdir(evidenceDir, { recursive: true });

const report = {
  scope: 'S1: login and authorized tutor context; synthetic DEMO data',
  base_url: baseURL,
  created_at_utc: new Date().toISOString(),
  status: 'COMPROBADO',
  captures: [],
};
const viewports = [
  { width: 1440, height: 900 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
];
let phase = 'starting';
let currentViewport = null;

async function layoutMetrics(page) {
  return page.evaluate(() => ({
    viewport_width: window.innerWidth,
    viewport_height: window.innerHeight,
    document_width: document.documentElement.scrollWidth,
    document_height: document.documentElement.scrollHeight,
    horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth,
  }));
}

async function focusTarget(page) {
  return page.evaluate(() => {
    const element = document.activeElement;
    return {
      tag: element?.tagName ?? '',
      id: element?.id ?? '',
      name: element?.getAttribute('aria-label') || element?.textContent?.trim().slice(0, 70) || '',
    };
  });
}

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ baseURL, viewport: viewports[0], locale: 'es-PE', timezoneId: 'America/Lima' });
  const page = await context.newPage();

  for (const viewport of viewports) {
    currentViewport = viewport;
    phase = 'empty login layout and keyboard';
    await page.setViewportSize(viewport);
    await page.goto('/');
    await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).waitFor({ state: 'visible' });
    const email = page.getByLabel('Correo electrónico', { exact: true });
    const password = page.getByLabel('Contraseña', { exact: true });
    assert.equal(await email.inputValue(), '', 'Capture login with an empty email');
    assert.equal(await password.inputValue(), '', 'Capture login with an empty password');
    const loginLayout = await layoutMetrics(page);
    assert.equal(loginLayout.horizontal_overflow, false, 'Login page must not overflow horizontally');

    const suffix = `${viewport.width}x${viewport.height}`;
    const loginPath = resolve(evidenceDir, `s1-ui-login-${suffix}.png`);
    await page.screenshot({ path: loginPath, fullPage: false });
    if (loginLayout.document_height > viewport.height) {
      await page.screenshot({ path: resolve(evidenceDir, `s1-ui-login-${suffix}-full.png`), fullPage: true });
    }

    const loginFocus = [];
    for (let step = 0; step < 4; step += 1) {
      await page.keyboard.press('Tab');
      loginFocus.push(await focusTarget(page));
    }
    assert.deepEqual(loginFocus.map((item) => item.id), ['', 'email', 'password', '']);
    assert.equal(loginFocus[0].tag, 'A');
    assert.equal(loginFocus[3].tag, 'BUTTON');
    report.captures.push({
      viewport,
      login_file: loginPath,
      login_layout: loginLayout,
      login_keyboard_focus: loginFocus,
      labels_verified: ['Correo electrónico', 'Contraseña', 'Selecciona un periodo'],
    });
  }

  // One real tutor login for all authenticated screenshots.
  phase = 'tutor login';
  await page.getByLabel('Correo electrónico', { exact: true }).fill(account.email);
  await page.getByLabel('Contraseña', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await page.getByText('✓ Contexto autorizado cargado.', { exact: true }).waitFor({ state: 'visible' });
  const userResponse = await page.request.get('/api/v1/auth/me');
  assert.equal(userResponse.status(), 200);
  const user = await userResponse.json();
  assert.equal(user.role, 'TUTOR');

  for (const capture of report.captures) {
    const { viewport } = capture;
    currentViewport = viewport;
    phase = 'authorized tutor layout and keyboard';
    await page.setViewportSize(viewport);
    await page.goto('/');
    await page.getByText('✓ Contexto autorizado cargado.', { exact: true }).waitFor({ state: 'visible' });
    assert.equal(await page.getByText('Sesión activa', { exact: true }).count(), 1);
    assert.equal(await page.locator('input[type="password"]').count(), 0, 'Do not capture credentials');
    const period = page.getByLabel('Selecciona un periodo', { exact: true });
    const periodId = await period.inputValue();
    const sectionsResponse = await page.request.get(`/api/v1/sections?period_id=${encodeURIComponent(periodId)}`);
    assert.equal(sectionsResponse.status(), 200);
    const sections = await sectionsResponse.json();
    assert(sections.length > 0 && sections.every((section) => section.tutor_id === user.id), 'Tutor screenshot must show only authorized sections');
    assert.equal(await page.locator('tbody tr').count(), sections.length);
    assert.deepEqual(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })), { local: 0, session: 0 });

    await page.evaluate(() => window.scrollTo(0, 0));
    const tutorLayout = await layoutMetrics(page);
    assert.equal(tutorLayout.horizontal_overflow, false, 'Tutor context must not overflow horizontally');
    const suffix = `${viewport.width}x${viewport.height}`;
    const tutorPath = resolve(evidenceDir, `s1-ui-tutor-${suffix}.png`);
    await page.screenshot({ path: tutorPath, fullPage: false });
    if (tutorLayout.document_height > viewport.height) {
      await page.screenshot({ path: resolve(evidenceDir, `s1-ui-tutor-${suffix}-full.png`), fullPage: true });
    }

    await period.focus();
    assert.equal((await focusTarget(page)).id, 'period');
    await page.keyboard.press('ArrowDown');
    const allowedPeriodIds = await period.locator('option').evaluateAll((options) => options.map((option) => option.value));
    assert(allowedPeriodIds.includes(await period.inputValue()));
    await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).focus();
    const logoutFocus = await focusTarget(page);
    assert.equal(logoutFocus.tag, 'BUTTON');
    Object.assign(capture, {
      tutor_file: tutorPath,
      tutor_layout: tutorLayout,
      tutor_keyboard: { period_select_focused: true, logout_button_focused: true },
      authorized_sections: sections.length,
      browser_storage_empty: true,
    });
  }
  phase = 'logout by keyboard';
  await page.keyboard.press('Enter');
  await page.getByText('Sesión cerrada correctamente.', { exact: true }).waitFor({ state: 'visible' });
  assert.equal((await page.request.get('/api/v1/auth/me')).status(), 401);
  report.logout_by_enter_revoked_session = true;
  await context.close();
} catch {
  // Playwright action errors can include fill arguments. Never print those errors.
  report.status = 'FALLIDO';
  report.failure = { phase, viewport: currentViewport };
  process.exitCode = 1;
} finally {
  await browser.close();
}

const output = resolve(evidenceDir, 's1-ui-checks.json');
await mkdir(dirname(output), { recursive: true });
await writeFile(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
console.log(`S1 UI ${report.status}: ${report.captures.length} viewports; sanitized report in tests/evidence/s1-ui-checks.json.`);
if (report.status === 'FALLIDO') console.error(`Check failed in phase: ${phase}; private action arguments omitted.`);
